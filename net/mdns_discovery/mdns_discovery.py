# -*- coding: utf-8 -*-
"""zeroconf mDNS 服务发现与主机名解析 —— "脚本即插件"重构（一份代码，两种用法）

用法 1：单独运行（行为同旧脚本）
    python mdns_discovery.py                                    # 监听全部服务 10s
    python mdns_discovery.py --resolve myhost.local             # 只解析主机名
    python mdns_discovery.py --service _http._tcp.local. --duration 15 --verbose
    python mdns_discovery.py --resolve myhost.local --iface all # 指定所有网卡
    python mdns_discovery.py --resolve myhost.local --iface 192.168.1.100

用法 2：被测试平台挂载
    test_platform/platform.json 的 "plugins" 列表登记本文件路径，
    平台启动时自动 import 本文件，@register 的类即出现在 UI 测试项列表。
    主机名解析成功后产出 device_ip，下游测试参数填 {device_ip} 即可引用。

约束：平台加载本文件时只做类注册、不执行测试动作（顶层无执行代码）。
"""

import logging
import os
import socket
import sys
import time
from typing import Callable, Dict, List, Optional

from zeroconf import (
    BadTypeInNameException,
    DNSAddress,
    DNSOutgoing,
    DNSQuestion,
    DNSRecord,
    InterfaceChoice,
    IPVersion,
    RecordUpdateListener,
    ServiceBrowser,
    ServiceInfo,
    Zeroconf,
    ZeroconfServiceTypes,
    const,
)

# ---- 独立运行时把 test_platform 根目录加入 sys.path；被平台加载时不触发 ----
if __name__ == "__main__":
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _PLATFORM = os.path.normpath(os.path.join(_HERE, "..", "..", "test_platform"))
    if os.path.isdir(_PLATFORM):
        sys.path.insert(0, _PLATFORM)

from core.base import (  # noqa: E402
    Context, LogFn, ParamDef, TestCase, TestResult, TestStatus,
)
from core.registry import register  # noqa: E402

# 可中断等待函数：等完返回 True，被停止请求打断返回 False
SleepFn = Callable[[float], bool]


# --------------------------------------------------------------------------- #
# 1. 服务发现：监听局域网内的 mDNS 服务广播
# --------------------------------------------------------------------------- #

class ServiceListener:
    """ServiceBrowser 的回调监听器，按服务状态变化输出信息。"""

    def __init__(self, log: Callable[[str], None] = print) -> None:
        self.found: Dict[str, ServiceInfo] = {}
        self.log = log

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return
        self.found[name] = info
        self._print_service(type_, name, info, "ADDED")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.found.pop(name, None)
        self.log(f"[REMOVED] {name} ({type_})")

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return
        self.found[name] = info
        self._print_service(type_, name, info, "UPDATED")

    def _print_service(self, type_: str, name: str,
                       info: ServiceInfo, state: str) -> None:
        addrs = _format_addresses(info)
        port = info.port if info.port is not None else "?"
        self.log(f"[{state}] {name}")
        self.log(f"    type   : {type_}")
        self.log(f"    host   : {info.server or '?'}")
        self.log(f"    port   : {port}")
        self.log(f"    addrs  : {addrs}")
        if info.properties:
            props = {k: _decode(v) for k, v in info.properties.items()}
            self.log(f"    props  : {props}")


def _format_addresses(info: ServiceInfo) -> List[str]:
    addrs: List[str] = []
    # 优先使用 addresses_by_version（新版本 API）
    try:
        for addr in info.addresses_by_version(IPVersion.All):
            addrs.append(socket.inet_ntop(
                addr.version == 6 and socket.AF_INET6 or socket.AF_INET,
                addr.packed))
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


def _parse_interfaces(iface: Optional[str]):
    """把 iface 参数解析为 zeroconf 的 interfaces 值。

    None/空/"all"/"*" -> InterfaceChoice.All（所有网卡，多网卡/多默认路由机器
                          上 Default 模式可能绑错网卡导致收不到组播，故默认 All）
    其他 -> IP 字符串列表（逗号分隔可指定多张网卡）
    """
    if not iface or not iface.strip():
        return InterfaceChoice.All
    text = iface.strip().lower()
    if text in ("all", "*"):
        return InterfaceChoice.All
    return [s.strip() for s in iface.split(",") if s.strip()]


def _make_zeroconf(iface: Optional[str], log: Callable[[str], None]) -> Zeroconf:
    """按 iface 描述创建 Zeroconf 实例，并打印实际使用的网卡便于排障。"""
    interfaces = _parse_interfaces(iface)
    zc = Zeroconf(interfaces=interfaces)
    if interfaces is InterfaceChoice.All:
        log("    网卡: 所有网卡")
    else:
        log(f"    网卡: {interfaces}")
    return zc


def discover_services(service_type: Optional[str], duration: int,
                      log: Callable[[str], None] = print,
                      sleep_fn: Optional[SleepFn] = None,
                      iface: Optional[str] = None) -> List[str]:
    """启动服务发现，阻塞 duration 秒后返回发现到的服务名列表。

    sleep_fn 提供时可中断等待（平台停止请求时提前返回已发现结果）。
    iface 指定网卡：空=所有网卡；或本机 IP 列表。
    """
    log(f"==> 开始 mDNS 服务发现，监听 {duration} 秒...")
    zeroconf = _make_zeroconf(iface, log)
    listener = ServiceListener(log)

    try:
        if service_type:
            log(f"    监听服务类型: {service_type}")
            ServiceBrowser(zeroconf, service_type, listener)
        else:
            log("    监听所有已注册的服务类型...")
            try:
                # find 返回的是 tuple（元素为服务类型字符串）
                type_list = list(ZeroconfServiceTypes.find(zc=zeroconf, timeout=2))
            except Exception as e:
                log(f"    获取服务类型失败，使用默认类型: {e}")
                type_list = ["_http._tcp.local.", "_ipp._tcp.local."]
            ServiceBrowser(zeroconf, type_list, listener)

        if sleep_fn is not None:
            sleep_fn(duration)   # 被中断则提前结束，返回已发现的
        else:
            time.sleep(duration)
    finally:
        zeroconf.close()

    log(f"<== 服务发现结束，共发现 {len(listener.found)} 个服务。")
    return list(listener.found.keys())


# --------------------------------------------------------------------------- #
# 2. 主机名解析：将 xxx.local 解析为 IP 地址
# --------------------------------------------------------------------------- #

def resolve_hostname(hostname: str, timeout: float = 5.0,
                     log: Callable[[str], None] = print,
                     sleep_fn: Optional[SleepFn] = None,
                     iface: Optional[str] = None) -> List[str]:
    """通过 mDNS 解析主机名（如 "myhost.local"）为 IPv4/IPv6 地址列表。"""
    if not hostname.endswith(".local"):
        hostname = hostname + ".local"

    log(f"==> 正在通过 mDNS 解析主机名: {hostname} (超时 {timeout}s)...")
    zeroconf = _make_zeroconf(iface, log)
    result: List[str] = []
    try:
        resolver = _HostnameResolver(hostname, result, log)
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
            if sleep_fn is not None:
                if not sleep_fn(0.1):
                    log("    解析等待被中断")
                    break
            else:
                time.sleep(0.05)
    finally:
        zeroconf.close()

    if result:
        log(f"<== 解析成功: {hostname} -> {result}")
    else:
        log(f"<== 解析失败: 未找到 {hostname} 的地址记录。")
    return result


class _HostnameResolver(RecordUpdateListener):
    """低层监听器：捕获响应中与目标主机名匹配的 A / AAAA 地址记录。"""

    def __init__(self, target: str, result: List[str],
                 log: Callable[[str], None] = print) -> None:
        self.target = target.lower()
        self.result = result
        self.done = False
        self.log = log

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
                self.log(f"    收到地址记录: {addr}")

    def update_record(self, zc: "Zeroconf", now: float, record: DNSRecord) -> None:
        # 兼容旧版 zeroconf 的同步入口
        self._handle(record)

    def async_update_records(self, zc: "Zeroconf", now: float, records: list) -> None:
        # 新版本 zeroconf 使用异步更新入口（records 为 RecordUpdate 列表）
        for update in records:
            new_record = getattr(update, "new", update)
            self._handle(new_record)


# --------------------------------------------------------------------------- #
# 3. 平台测试项
# --------------------------------------------------------------------------- #

@register
class MdnsDiscoveryCase(TestCase):
    id = "mdns_discovery"
    name = "mDNS 发现/解析"
    category = "网络发现"
    description = ("监听局域网 mDNS 服务广播，或把 xxx.local 主机名解析为 IP；"
                   "解析成功产出 {device_ip} 供下游测试引用")
    params = [
        ParamDef("mode", "模式", "resolve", "str",
                 "resolve=仅解析主机名 / discover=仅服务发现 / both=都跑"),
        ParamDef("hostname", "主机名", "", "str",
                 "如 myhost.local（resolve/both 必填），产出 {device_ip}"),
        ParamDef("resolve_timeout", "解析超时(秒)", "5", "float"),
        ParamDef("service", "服务类型", "", "str",
                 "如 _http._tcp.local.，留空=监听全部（discover/both 有效）"),
        ParamDef("duration", "发现时长(秒)", "10", "int"),
        ParamDef("iface", "网卡", "", "str",
                 "空=所有网卡；或填本机 IP（逗号分隔多个）"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        mode = (self.p_str("mode", "resolve").strip().lower() or "resolve")
        if mode not in ("resolve", "discover", "both"):
            return TestResult(TestStatus.FAILED, f"未知模式: {mode}")
        hostname = self.p_str("hostname").strip()
        timeout = self.p_float("resolve_timeout", 5.0)
        service = self.p_str("service").strip() or None
        duration = self.p_int("duration", 10)
        iface = self.p_str("iface").strip() or None

        def _sleep(sec: float) -> bool:
            return self.sleep_interruptible(sec)

        data: Dict[str, object] = {}
        msgs: List[str] = []

        # ---- 服务发现 ----
        if mode in ("discover", "both"):
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED, "用户停止")
            # 服务类型形如 _http._tcp.local.；主机名（vx90sndi.local）应走
            # hostname 解析而非服务浏览，提前拦截避免底层抛异常
            if service and not service.startswith("_"):
                return TestResult(TestStatus.FAILED, (
                    f"service 参数 '{service}' 不是服务类型"
                    "（应形如 _http._tcp.local.）；"
                    "解析主机名请把 mode 设为 resolve 并填 hostname"))
            try:
                services = discover_services(service, duration,
                                             log=log, sleep_fn=_sleep, iface=iface)
            except BadTypeInNameException as e:
                return TestResult(TestStatus.FAILED,
                                  f"服务类型无效: '{service}'（{e}）", data=data)
            except OSError as e:
                return TestResult(TestStatus.FAILED,
                                  f"网卡创建失败（iface='{iface}'）: {e}", data=data)
            data["mdns_services"] = services
            data["mdns_service_count"] = len(services)
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED,
                                  f"用户停止（发现阶段），已发现 {len(services)} 个",
                                  data=data)
            msgs.append(f"发现 {len(services)} 个服务")

        # ---- 主机名解析 ----
        if mode in ("resolve", "both"):
            if not hostname:
                return TestResult(TestStatus.FAILED,
                                  "resolve 模式必须填写 hostname", data=data)
            try:
                addresses = resolve_hostname(hostname, timeout,
                                             log=log, sleep_fn=_sleep, iface=iface)
            except OSError as e:
                return TestResult(TestStatus.FAILED,
                                  f"网卡创建失败（iface='{iface}'）: {e}", data=data)
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED, "用户停止（解析阶段）",
                                  data=data)
            if not addresses:
                return TestResult(TestStatus.FAILED,
                                  f"解析 {hostname} 失败（{timeout}s 超时）",
                                  data=data)
            data["mdns_addresses"] = addresses
            # IPv4 优先，供下游 {device_ip} 占位符引用
            device_ip = next((a for a in addresses if ":" not in a), addresses[0])
            data["device_ip"] = device_ip
            extra = f"（共 {len(addresses)} 个地址）" if len(addresses) > 1 else ""
            msgs.append(f"{hostname} -> {device_ip}{extra}")

        return TestResult(TestStatus.PASSED, "；".join(msgs), data=data)


# ---------------- 单独运行入口 ----------------
def _main() -> None:
    # Windows 控制台默认 GBK，重配置为 UTF-8 以避免中文乱码（非终端环境忽略）
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    import argparse
    import builtins
    import functools

    # 非交互终端（IDE / 管道）下 stdout 为块缓冲，print 会攒到退出才刷出，
    # 表现为"没有任何输出"。强制每次 print 立即刷新。
    builtins.print = functools.partial(builtins.print, flush=True)

    ap = argparse.ArgumentParser(
        description="zeroconf mDNS 发现与解析（可独立运行，亦可被 test_platform 挂载）")
    ap.add_argument("--service", default=None,
                    help="要监听的服务类型，例如 _http._tcp.local.（默认监听全部）")
    ap.add_argument("--resolve", default=None,
                    help="要解析的主机名，例如 myhost.local")
    ap.add_argument("--duration", type=int, default=10,
                    help="服务发现持续时间（秒），默认 10；0=跳过发现，不输出其他的")
    ap.add_argument("--resolve-timeout", type=float, default=5.0,
                    help="主机名解析超时（秒），默认 5.0")
    ap.add_argument("--iface", default=None,
                    help="指定网卡：或本机 IP（逗号分隔多个）；"
                         "默认=所有网卡")
    ap.add_argument("--verbose", action="store_true", help="开启详细日志")
    args = ap.parse_args()

    if args.verbose:
        logging.getLogger("zeroconf").setLevel(logging.DEBUG)

    if args.duration <= 0 and not args.resolve:
        print("提示：--duration 0 且未指定 --resolve，无操作。")
        return

    # 语义同旧脚本：duration>0 跑发现，指定 --resolve 跑解析
    if args.resolve and args.duration > 0:
        mode = "both"
    elif args.resolve:
        mode = "resolve"
    else:
        mode = "discover"

    case = MdnsDiscoveryCase({
        "mode": mode,
        "hostname": args.resolve or "",
        "resolve_timeout": str(args.resolve_timeout),
        "service": args.service or "",
        "duration": str(max(args.duration, 0)),
        "iface": args.iface or "",
    })
    print(f"[单独运行] {case.name}  mode={mode}")
    try:
        result = case.run(Context(), log=print)
    except KeyboardInterrupt:
        print("\n[中断] 用户 Ctrl+C")
        return
    print(f"[结果] {result.status.value}  {result.message}")
    if result.data:
        # 长列表截断显示（完整内容仍在 data / 报告里）
        shown = {}
        for k, v in result.data.items():
            if isinstance(v, list) and len(v) > 8:
                shown[k] = v[:8] + [f"...（共 {len(v)} 项）"]
            else:
                shown[k] = v
        print(f"[产出] {shown}")


if __name__ == "__main__":
    _main()
