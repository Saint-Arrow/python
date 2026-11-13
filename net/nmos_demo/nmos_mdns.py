# -*- coding: utf-8 -*-
"""NMOS IS-04 Node mDNS 广播器 —— 虚拟 NMOS 设备的发现层

镜像文件：../mdns_discovery/mdns_discovery.py（那边是"浏览"，这边是"广播"）

真机样本（Blackmagic 2110 IP Mini BiDirect 12G 实抓，供对照）:
    [ADDED] bmd_nmos_192-168-17-240:8090._nmos-node._tcp.local.
        type   : _nmos-node._tcp.local.
        host   : Blackmagic-2110-IP-Mini-BiDirect-12G.local.
        port   : 8090
        addrs  : ['192.168.17.167']
        props  : {b'txtvers': '1', b'api_auth': 'false',
                  b'api_proto': 'http', b'api_ver': 'v1.0,v1.1,v1.2,v1.3'}

用法 1：单独运行（验证发现链路 / 模拟设备上下线）
    python nmos_mdns.py --iface 192.168.17.166 --port 8090
    python nmos_mdns.py --name virtual-sender-1 --port 8080 --api-ver v1.1,v1.2,v1.3
    python nmos_mdns.py --name bmd_nmos_192-168-17-240:8090   # 复刻 BMD 风格命名
    python nmos_mdns.py --duration 60                         # 60s 后自动下线（观察 REMOVE 事件）

用法 2：被 nmos_virtual_sender.py import（作为虚拟设备的发现层组件）
    adv = NmosNodeAdvertiser(api_port=8080, iface="192.168.17.166")
    adv.start()
    adv.update_txt({"api_ver": "v1.2,v1.3"})   # 动态改 TXT（触发网络上 UPDATE 事件）
    adv.stop()                                  # 主动下线（触发 REMOVE 事件）

约束：被 import 时无任何网络动作（顶层无执行代码）。
依赖：pip install zeroconf
"""

import argparse
import hashlib
import re
import socket
import time
from typing import Callable, Dict, List, Optional, Union

from zeroconf import InterfaceChoice, ServiceInfo, Zeroconf

SERVICE_TYPE = "_nmos-node._tcp.local."
# 真机同款 TXT（Blackmagic 抓包），api_ver 列出全部历史版本兼容性最好
# 注意：IS-04 浏览器（如 ConductIP）只会在"双方共同版本"里选最高的访问，
#       只广播 v1.3 而控制器基线是 v1.2 时，节点会被直接忽略（发现失败）。
DEFAULT_API_VER = "v1.0,v1.1,v1.2,v1.3"

TxtValue = Union[str, bytes, None]
TxtDict = Dict[Union[str, bytes], TxtValue]
LogFn = Callable[[str], None]


def _short_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:6]


def _sanitize_host(name: str) -> str:
    """把 instance name 净化成合法 DNS 主机名（仅字母数字和连字符，<=63）。

    BMD 真机的 instance 名 "bmd_nmos_192-168-17-240:8090" 带冒号，
    但其 host 是 "Blackmagic-2110-IP-Mini-BiDirect-12G.local."（合法）。
    mDNS 主机名带 ":" 等非法字符时，部分解析器（含一些控制器）解析 A 记录会失败。
    """
    host = re.sub(r"[^A-Za-z0-9-]", "-", name).strip("-")
    return (host or "virtual-sender")[:63]


def _default_local_ip() -> str:
    """取默认路由出口 IP（不真正发包）；失败回环。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("223.5.5.5", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _decode(v) -> str:
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else ("" if v is None else str(v))


class NmosNodeAdvertiser:
    """_nmos-node._tcp 服务广播器（IS-04 发现层，可脱离 HTTP API 独立使用）。

    广播层无强校验：api_port 后面没有 HTTP 服务也能注册成功，
    因此可先单独验证发现链路，再接入 Node/Connection API。
    """

    def __init__(
        self,
        api_port: int,
        name: Optional[str] = None,
        iface: Optional[str] = None,
        api_proto: str = "http",
        api_ver: str = DEFAULT_API_VER,
        api_auth: str = "false",
        extra_txt: Optional[TxtDict] = None,
        ttl: int = 30,
        host_name: Optional[str] = None,
        log: LogFn = print,
    ) -> None:
        """
        :param api_port: Node API 的 HTTP 端口（写入 TXT api_port 与 SRV 记录）
        :param name:     instance name；缺省 "virtual-sender-<hash>"
        :param iface:    绑定的本机 IP（多网卡场景）；缺省取默认路由出口 IP
        :param host_name: server 主机名；缺省 "<name>.local."
        :param ttl:      mDNS 记录 TTL（秒），越小下线感知越快
        :param extra_txt: 追加/覆盖 TXT 项（如 ver_snd=v1.2）
        """
        self._port = api_port
        self._iface = iface
        self._ttl = ttl
        self._log = log

        self._instance = name or f"virtual-sender-{_short_hash(f'{api_port}-{time.time()}')}"
        # host 默认由 instance 名净化而来（":8090" 等非法字符转 "-"）
        self._server = host_name or f"{_sanitize_host(self._instance)}.local."

        txt: TxtDict = {
            "api_auth": api_auth,
            "api_proto": api_proto,
            "api_ver": api_ver,
            # ver_* 六件套：各资源集合的版本号。nmos-cpp/BMD 真机 TXT 都带
            # （实抓：qx-022494 与 UpDownCross 12G 均有），控制器据此决定是否
            # 重读资源列表。静态资源不变，固定 "0" 即可。
            "ver_slf": "0", "ver_src": "0", "ver_flw": "0",
            "ver_dvc": "0", "ver_snd": "0", "ver_rcv": "0",
        }
        if extra_txt:
            txt.update(extra_txt)
        self._txt = txt

        self._zc: Optional[Zeroconf] = None
        self._info: Optional[ServiceInfo] = None
        self._ip_cache: Optional[str] = None

    # ------------------------------------------------------------------ #

    def _ip(self) -> str:
        """广播用的本机 IP 字符串（缓存）。"""
        if self._ip_cache is None:
            self._ip_cache = self._iface if self._iface else _default_local_ip()
        return self._ip_cache

    def _addresses(self) -> List[bytes]:
        return [socket.inet_aton(self._ip())]

    def _build_info(self) -> ServiceInfo:
        return ServiceInfo(
            SERVICE_TYPE,
            f"{self._instance}.{SERVICE_TYPE}",
            port=self._port,
            weight=0,
            priority=0,
            properties=self._txt,
            server=self._server,
            host_ttl=self._ttl,
            other_ttl=self._ttl,
            addresses=self._addresses(),
        )

    def _print_service(self, state: str) -> None:
        props = {k if isinstance(k, str) else _decode(k): _decode(v) for k, v in self._txt.items()}
        self._log(f"[{state}] {self._instance}.{SERVICE_TYPE}")
        self._log(f"    type   : {SERVICE_TYPE}")
        self._log(f"    host   : {self._server}")
        self._log(f"    port   : {self._port}")
        self._log(f"    addrs  : ['{self._ip()}']")
        self._log(f"    props  : {props}")

    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """注册 mDNS 服务（网络上出现该 Node）。"""
        if self._zc is not None:
            return
        self._zc = Zeroconf(
            interfaces=[self._iface] if self._iface else InterfaceChoice.All
        )
        self._info = self._build_info()
        self._zc.register_service(self._info, allow_name_change=True)
        self._print_service("ADDED")

    def update_txt(self, extra_txt: TxtDict) -> None:
        """合并更新 TXT 记录（触发网络上 UPDATE 事件）。"""
        if self._zc is None or self._info is None:
            raise RuntimeError("not started")
        self._txt = dict(self._txt, **extra_txt)
        new_info = self._build_info()
        try:
            self._zc.update_service(self._zc, new_info)  # zeroconf >= 0.28
        except TypeError:
            self._zc.update_service(new_info)            # 老版本签名
        self._info = new_info
        self._print_service("UPDATED")

    def stop(self) -> None:
        """注销 mDNS 服务（网络上该 Node 下线，触发 REMOVE 事件）。幂等。"""
        if self._zc is None:
            return
        try:
            if self._info is not None:
                self._zc.unregister_service(self._info)
        finally:
            self._zc.close()
            self._zc = None
            self._info = None
            self._log(f"[REMOVED] {self._instance}.{SERVICE_TYPE} (已注销)")


# --------------------------------------------------------------------------- #
# 单独运行入口
# --------------------------------------------------------------------------- #

def _parse_txt(pairs: List[str]) -> TxtDict:
    txt: TxtDict = {}
    for p in pairs:
        key, _, val = p.partition("=")
        txt[key.strip()] = val.strip()
    return txt


def main() -> int:
    ap = argparse.ArgumentParser(description="NMOS IS-04 Node mDNS 广播器")
    ap.add_argument("--name", help="instance name（缺省 virtual-sender-<hash>）")
    ap.add_argument("--port", type=int, default=8080, help="Node API 端口（默认 8080）")
    ap.add_argument("--iface", help="绑定的本机 IP（多网卡场景）")
    ap.add_argument("--host", help="server 主机名（缺省由 name 净化生成，':' 等非法字符转 '-'）")
    ap.add_argument("--api-proto", default="http", help="TXT api_proto（默认 http）")
    ap.add_argument("--api-ver", default=DEFAULT_API_VER, help=f"TXT api_ver（默认 {DEFAULT_API_VER}）")
    ap.add_argument("--api-auth", default="false", help="TXT api_auth（默认 false）")
    ap.add_argument("--txt", action="append", default=[], metavar="KEY=VALUE",
                    help="追加/覆盖 TXT 项，可多次（如 --txt ver_snd=v1.2）")
    ap.add_argument("--ttl", type=int, default=30, help="mDNS TTL 秒（默认 30）")
    ap.add_argument("--duration", type=float, default=0,
                    help="广播时长秒；0 = 一直广播直到 Ctrl+C")
    args = ap.parse_args()

    adv = NmosNodeAdvertiser(
        api_port=args.port,
        name=args.name,
        iface=args.iface,
        host_name=args.host,
        api_proto=args.api_proto,
        api_ver=args.api_ver,
        api_auth=args.api_auth,
        extra_txt=_parse_txt(args.txt) or None,
        ttl=args.ttl,
    )
    adv.start()
    try:
        if args.duration > 0:
            deadline = time.time() + args.duration
            while time.time() < deadline:
                time.sleep(0.5)
        else:
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        adv.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
