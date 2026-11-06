"""
基于 zeroconf 的 mDNS 服务发现 (Service Discovery) 演示。

功能：
1. 监听局域网内的 mDNS 服务广播，自动发现支持的服务（如 _http._tcp.local.、
   _ipp._tcp.local.、_airplay._tcp.local. 等），并打印服务信息。
2. 解析某个主机名（例如 "myhost.local"）的 IP 地址（多播 DNS 解析）。

依赖：
    pip install zeroconf

运行：
    # 默认监听常见服务并打印到控制台，持续 30 秒
    python mdns_discovery.py

    # 指定监听的服务类型，并解析某个主机名
    python mdns_discovery.py --service _http._tcp.local. --resolve myhost.local --duration 15
"""

import argparse
import logging
import socket
import sys
import time
from typing import Dict, List, Optional

from zeroconf import (
    IPVersion,
    ServiceBrowser,
    ServiceInfo,
    Zeroconf,
    ZeroconfServiceTypes,
)
from zeroconf import DNSOutgoing, DNSQuestion, DNSAddress, DNSRecord, const
from zeroconf import RecordUpdateListener  # 低层 DNS 记录监听器


# --------------------------------------------------------------------------- #
# 1. 服务发现：监听局域网内的 mDNS 服务广播
# --------------------------------------------------------------------------- #


class ServiceListener:
    """ServiceBrowser 的回调监听器，按服务状态变化打印信息。"""

    def __init__(self) -> None:
        self.found: Dict[str, ServiceInfo] = {}

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return
        self.found[name] = info
        _print_service(type_, name, info, "ADDED")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.found.pop(name, None)
        print(f"[REMOVED] {name} ({type_})")

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return
        self.found[name] = info
        _print_service(type_, name, info, "UPDATED")


def _print_service(type_: str, name: str, info: ServiceInfo, state: str) -> None:
    addrs = _format_addresses(info)
    port = info.port if info.port is not None else "?"
    print(f"[{state}] {name}")
    print(f"    type   : {type_}")
    print(f"    host   : {info.server or '?'}")
    print(f"    port   : {port}")
    print(f"    addrs  : {addrs}")
    if info.properties:
        props = {k: _decode(v) for k, v in info.properties.items()}
        print(f"    props  : {props}")
    print()


def _format_addresses(info: ServiceInfo) -> List[str]:
    addrs: List[str] = []
    # 优先使用 addresses_by_version（新版本 API）
    try:
        for addr in info.addresses_by_version(IPVersion.All):
            addrs.append(socket.inet_ntop(addr.version == 6 and socket.AF_INET6 or socket.AF_INET, addr.packed))
    except Exception:
        pass
    if not addrs and info.addresses:
        addrs = [socket.inet_ntoa(a) for a in info.addresses]
    if not addrs and info.parsed_addresses():
        addrs = info.parsed_addresses()
    return addrs


def _decode(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def discover_services(service_type: Optional[str], duration: int) -> List[str]:
    """启动服务发现，阻塞 duration 秒后返回发现到的服务名列表。"""
    print(f"==> 开始 mDNS 服务发现，监听 {duration} 秒...")
    zeroconf = Zeroconf()
    listener = ServiceListener()

    if service_type:
        print(f"    监听服务类型: {service_type}\n")
        ServiceBrowser(zeroconf, service_type, listener)
    else:
        # 监听所有已知服务类型
        print("    监听所有已注册的服务类型...\n")
        try:
            # find 返回的是 tuple（元素为服务类型字符串）
            type_list = list(ZeroconfServiceTypes.find(zc=zeroconf, timeout=2))
        except Exception as e:
            print(f"    获取服务类型失败，使用默认类型: {e}")
            type_list = ["_http._tcp.local.", "_ipp._tcp.local."]
        ServiceBrowser(zeroconf, type_list, listener)

    try:
        time.sleep(duration)
    finally:
        zeroconf.close()

    print(f"<== 服务发现结束，共发现 {len(listener.found)} 个服务。")
    return list(listener.found.keys())


# --------------------------------------------------------------------------- #
# 2. 主机名解析：将 xxx.local 解析为 IP 地址
# --------------------------------------------------------------------------- #


def resolve_hostname(hostname: str, timeout: float = 5.0) -> List[str]:
    """通过 mDNS 解析主机名（如 "myhost.local"）为 IPv4/IPv6 地址列表。"""
    if not hostname.endswith(".local"):
        hostname = hostname + ".local"

    print(f"==> 正在通过 mDNS 解析主机名: {hostname} (超时 {timeout}s)...")
    zeroconf = Zeroconf()
    result: List[str] = []
    try:
        resolver = _HostnameResolver(hostname, result)
        zeroconf.add_listener(
            resolver,
            [DNSQuestion(hostname, const._TYPE_A, const._CLASS_IN),
             DNSQuestion(hostname, const._TYPE_AAAA, const._CLASS_IN)],
        )
        # 主动发送一次查询，触发局域网内主机的响应
        out = DNSOutgoing(const._FLAGS_QR_QUERY)
        out.add_question(DNSQuestion(hostname, const._TYPE_A, const._CLASS_IN))
        out.add_question(DNSQuestion(hostname, const._TYPE_AAAA, const._CLASS_IN))
        zeroconf.send(out)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not resolver.done:
            time.sleep(0.05)
    finally:
        zeroconf.close()

    if result:
        print(f"<== 解析成功: {hostname} -> {result}")
    else:
        print(f"<== 解析失败: 未找到 {hostname} 的地址记录。")
    return result


class _HostnameResolver(RecordUpdateListener):
    """低层监听器：捕获响应中与目标主机名匹配的 A / AAAA 地址记录。"""

    def __init__(self, target: str, result: List[str]) -> None:
        self.target = target.lower()
        self.result = result
        self.done = False

    def _handle(self, record: DNSRecord) -> None:
        if not isinstance(record, DNSAddress):
            return
        # mDNS 记录名通常带结尾点（如 "host.local."），统一去除后比较
        name = record.name.rstrip(".").lower()
        if name != self.target:
            return
        if record.type in (const._TYPE_A, const._TYPE_AAAA):
            addr = socket.inet_ntop(
                socket.AF_INET6 if record.type == const._TYPE_AAAA else socket.AF_INET,
                record.address,
            )
            if addr not in self.result:
                self.result.append(addr)
                self.done = True
                print(f"    收到地址记录: {addr}")

    def update_record(self, zc: "Zeroconf", now: float, record: DNSRecord) -> None:
        # 兼容旧版 zeroconf 的同步入口
        self._handle(record)

    def async_update_records(self, zc: "Zeroconf", now: float, records: list) -> None:
        # 新版本 zeroconf 使用异步更新入口（records 为 RecordUpdate 列表）
        for update in records:
            new_record = getattr(update, "new", update)
            self._handle(new_record)


# --------------------------------------------------------------------------- #
# 主程序
# --------------------------------------------------------------------------- #


def main() -> int:
    # Windows 控制台默认 GBK，重配置为 UTF-8 以避免中文乱码（非终端环境忽略）
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # 非交互终端（IDE / 管道）下 stdout 为块缓冲，print 会攒到退出才刷出，
    # 表现为“没有任何输出”。强制每次 print 立即刷新。
    import builtins
    import functools

    builtins.print = functools.partial(builtins.print, flush=True)

    parser = argparse.ArgumentParser(description="zeroconf mDNS 发现与解析演示")
    parser.add_argument("--service", default=None,
                        help="要监听的服务类型，例如 _http._tcp.local.（默认监听全部）")
    parser.add_argument("--resolve", default=None,
                        help="要解析的主机名，例如 myhost.local")
    parser.add_argument("--duration", type=int, default=10,
                        help="服务发现持续时间（秒），默认 10")
    parser.add_argument("--resolve-timeout", type=float, default=5.0,
                        help="主机名解析超时（秒），默认 5.0")
    parser.add_argument("--verbose", action="store_true", help="开启详细日志")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("zeroconf").setLevel(logging.DEBUG)

    # 仅当 duration > 0 时才跑服务发现；否则（只解析主机名时）跳过，
    # 避免 Zeroconf 被立即关闭导致后台异步查询抛出 NotRunningException
    if args.duration > 0:
        discover_services(args.service, args.duration)

    if args.resolve:
        resolve_hostname(args.resolve, args.resolve_timeout)

    return 0


if __name__ == "__main__":
    sys.exit(main())
