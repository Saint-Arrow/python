# -*- coding: utf-8 -*-
"""NMOS IS-05 对设备写视频 SDP —— "脚本即插件"（一份代码，两种用法）

场景：把视频 SDP 写入 NMOS 设备（如 Blackmagic 2110 IP UpDownCross 12G，
      mDNS: "2110 IP UpDownCross 12G._http._tcp.local."，HTTP 端口 80）。

NMOS 标准 peer-to-peer 发现链（IS-04 Spec）：
  1. mDNS 浏览 _nmos-node._tcp.local. -> TXT: api_proto/api_port/api_ver
  2. GET http://{ip}:{api_port}/x-nmos/node/{ver}/devices/
     -> controls[] 中 type 含 "sr-ctrl"(IS-05) 的 href 即 Connection API 地址
  3. GET {IS-05}/single/receivers/ -> 选 format=video 的 receiver
  4. PATCH {IS-05}/single/receivers/{id}/staged
        {"transport_file": {"data": "<SDP>", "type": "application/sdp"},
         "activation": {"mode": "activate_immediate"}}
  5. GET {IS-05}/single/receivers/{id}/active 校验

用法 1：单独运行
    # mDNS 自动发现设备（按 device name 匹配 _http._tcp）并写 SDP 激活
    python nmos_sdp_write.py --mdns --mdns-name "2110 IP UpDownCross 12G" \
                             --iface 192.168.17.166 --sdp-file video.sdp
    # 已知设备 IP：列出 receivers（只读，同时打印探测到的 NMOS 端点）
    python nmos_sdp_write.py --ip 192.168.17.62 --list
    # 已知设备 IP + SDP 文件 / URL / 指定 receiver
    python nmos_sdp_write.py --ip 192.168.17.62 --iface 192.168.17.166 --sdp-file video.sdp

用法 2：被测试平台挂载
    test_platform/platform.json 的 "plugins" 列表登记本文件路径。
    ip 支持 {device_ip} 占位符（mdns_discovery 产出）；本项产出 {receiver_id}。

约束：平台加载本文件时只做类注册、不执行测试动作（顶层无执行代码）。
依赖：pip install requests zeroconf
"""

import json
import os
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter

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

SleepFn = Callable[[float], bool]


# --------------------------------------------------------------------------- #
# 1. HTTP 基础：可绑定本机源 IP 的 Session（从指定网卡发出请求）
# --------------------------------------------------------------------------- #

class SourceAddressAdapter(HTTPAdapter):
    """把请求绑定到指定本机 IP（源地址），确保走对网卡。"""

    def __init__(self, source_address: str, **kwargs) -> None:
        self._source = (source_address, 0)
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs) -> None:
        kwargs["source_address"] = self._source
        super().init_poolmanager(*args, **kwargs)


def make_session(iface: Optional[str], log: Callable[[str], None]) -> requests.Session:
    session = requests.Session()
    session.trust_env = False  # 忽略系统代理，避免局域网请求被代理拦截
    if iface and iface.strip() and iface.strip().lower() not in ("all", "*"):
        adapter = SourceAddressAdapter(iface.strip())
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        log(f"    HTTP 源地址绑定网卡: {iface.strip()}")
    return session


def _req(session, method: str, url: str, timeout: float,
         log: Callable[[str], None],
         json_body: Optional[dict] = None) -> Tuple[requests.Response, Optional[object]]:
    body = f" body={json.dumps(json_body, ensure_ascii=False)[:200]}" if json_body else ""
    log(f"    {method} {url}{body}")
    r = session.request(method, url, json=json_body, timeout=timeout)
    text = (r.text or "")[:200].replace("\n", "\\n")
    log(f"    -> {r.status_code} {text}")
    try:
        payload = r.json()
    except ValueError:
        payload = None
    return r, payload


def _host_to_ip(url: str, ip: str) -> str:
    """把 URL 里的主机名（可能是 xxx.local）替换为设备 IP，保留端口。"""
    parts = urlsplit(url)
    if not parts.scheme:
        return url
    host, _, port = parts.netloc.partition(":")
    netloc = f"{ip}:{port}" if port else ip
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


# --------------------------------------------------------------------------- #
# 2. NMOS 端点发现：mDNS api_port -> Node API -> controls 里的 IS-05 href
# --------------------------------------------------------------------------- #

def _probe_node_root(session, base: str, timeout: float, log,
                     retries: int = 4, interval: float = 2.0) -> Optional[str]:
    """GET {base}/x-nmos/node/ 返回最高版本；失败返回 None。

    部分设备（如 BMD 12.1）NMOS 服务存在间歇性连接重置，连接层失败时
    短退避重试；HTTP 层有响应（含 404）则不重试。
    """
    err = None
    for attempt in range(retries + 1):
        try:
            r, payload = _req(session, "GET", f"{base}/x-nmos/node/", timeout, log)
            if r.ok and isinstance(payload, list) and payload:
                return sorted(payload)[-1]
            return None
        except requests.RequestException as e:
            err = e
            if attempt < retries:
                log(f"    -> 连接失败({attempt + 1}/{retries + 1}): "
                    f"{type(e).__name__}，{interval:.0f}s 后重试"
                    "（设备 NMOS 服务可能间歇不可用）")
                time.sleep(interval)
    log(f"    -> 连接失败: {type(err).__name__}: {str(err)[:120]}")
    return None


def resolve_nmos_endpoints(session, ip: str, http_port: int,
                           api_port: Optional[int], timeout: float,
                           log) -> Tuple[Optional[str], Optional[str]]:
    """返回 (node_base, conn_base)。conn_base 形如
    http://{ip}:{port}/x-nmos/connection/{ver}（不带尾斜杠）。

    候选顺序：
      a. mDNS _nmos-node 广播的 api_port
      b. Web 端口上的 NMOS 路径（/x-nmos 与 /api/x-nmos 两种）
    """
    candidates = []
    if api_port:
        candidates.append(f"http://{ip}:{api_port}")
    candidates.append(f"http://{ip}:{http_port}")
    candidates.append(f"http://{ip}:{http_port}/api")

    for nb in candidates:
        ver = _probe_node_root(session, nb, timeout, log)
        if not ver:
            continue
        ver = ver.rstrip("/")  # 版本串可能带尾斜杠，拼路径会变双斜杠
        log(f"    Node API 发现: {nb}/x-nmos/node/{ver}")
        node_base = f"{nb}/x-nmos/node/{ver}"
        # IS-05 地址：device.controls 里 type 含 sr-ctrl 的 href
        try:
            r, devices = _req(session, "GET", f"{node_base}/devices/", timeout, log)
            if r.ok and isinstance(devices, list):
                for dev in devices:
                    for ctl in dev.get("controls") or []:
                        href = ctl.get("href") or ""
                        if "sr-ctrl" in str(ctl.get("type", "")) and href:
                            conn = _host_to_ip(href, ip).rstrip("/")
                            log(f"    IS-05 地址(controls): {conn}")
                            return node_base, conn
        except requests.RequestException:
            pass
        # controls 未提供：尝试与 Node 同服务的 connection 路径
        try:
            r, vers = _req(session, "GET", f"{nb}/x-nmos/connection/", timeout, log)
            if r.ok and isinstance(vers, list) and vers:
                conn = f"{nb}/x-nmos/connection/{sorted(vers)[-1].rstrip('/')}"
                log(f"    IS-05 地址(同级路径): {conn}")
                return node_base, conn
        except requests.RequestException:
            pass
    return None, None


# --------------------------------------------------------------------------- #
# 3. IS-05 receivers：列出 / 选择视频 receiver / 写入激活
# --------------------------------------------------------------------------- #

def list_receivers(session, conn_base: str, node_base: Optional[str],
                   timeout: float, log) -> List[dict]:
    """返回 receivers 概要 [{id,label,format,master_enable,has_sdp}]。"""
    meta: Dict[str, dict] = {}
    if node_base:
        try:
            r, nodes = _req(session, "GET", f"{node_base}/receivers/", timeout, log)
            if r.ok and isinstance(nodes, list):
                meta = {n["id"]: n for n in nodes
                        if isinstance(n, dict) and "id" in n}
        except requests.RequestException:
            pass
    try:
        r, ids = _req(session, "GET", f"{conn_base}/single/receivers/", timeout, log)
        if not r.ok or not isinstance(ids, list):
            raise RuntimeError(f"获取 receiver 列表失败: HTTP {r.status_code}")
    except requests.RequestException as e:
        raise RuntimeError(f"获取 receiver 列表失败: {e}")
    out = []
    for rid in ids:
        rid = str(rid).rstrip("/")  # IS-05 列表元素带尾斜杠，统一去掉
        enabled = has_sdp = None
        try:
            r, act = _req(session, "GET",
                          f"{conn_base}/single/receivers/{rid}/active", timeout, log)
            if r.ok and isinstance(act, dict):
                enabled = bool(act.get("master_enable"))
                has_sdp = bool((act.get("transport_file") or {}).get("data"))
        except requests.RequestException:
            pass
        out.append({"id": rid, "label": meta.get(rid, {}).get("label", ""),
                    "format": meta.get(rid, {}).get("format", "?"),
                    "master_enable": enabled, "has_sdp": has_sdp})
    return out


def pick_video_receiver(session, conn_base: str, node_base: Optional[str],
                        timeout: float, receiver_id: Optional[str], log) -> str:
    """选定 receiver：显式 id 优先；否则按 format=video（或 id/label 含 video）选。"""
    items = list_receivers(session, conn_base, node_base, timeout, log)
    if not items:
        raise RuntimeError("设备未返回任何 receiver")
    for it in items:
        log(f"    receiver: {it['id']}  format={it['format']} "
            f"label={it['label']!r} active={it['master_enable']}")
    if receiver_id:
        for it in items:
            if it["id"] == receiver_id:
                return receiver_id
        raise RuntimeError(f"未找到指定 receiver: {receiver_id}")
    for it in items:  # IS-04 format（URN 全名或短名，如 video / urn:x-nmos:format:video）
        fmt = str(it["format"]).lower()
        if fmt == "video" or fmt.endswith(":video"):
            return it["id"]
    for it in items:  # 兜底：id/label 关键字
        if "video" in (it["id"] + " " + it["label"]).lower():
            return it["id"]
    raise RuntimeError("未能自动识别视频 receiver，请指定 receiver_id")


def _stage_and_activate(session, conn_base: str, rid: str, sdp: str,
                        timeout: float, log) -> None:
    """写 SDP 到 staged 并立即激活；多策略兼容不同设备实现。"""
    staged = f"{conn_base}/single/receivers/{rid}/staged"
    tf = {"transport_file": {"data": sdp, "type": "application/sdp"}}
    act = {"activation": {"mode": "activate_immediate"}}
    # 部分设备（如 BMD）为字面实现：不显式 master_enable=true 则"激活 disabled
    # 状态"；sender_id=null 表示 file 模式（清除残留的 IS-04 路由关联）。
    on = {"master_enable": True, "sender_id": None}

    # 策略 1：一次 PATCH（transport_file + activation）
    r, payload = _req(session, "PATCH", staged, timeout, log,
                      json_body={**on, **tf, **act})
    if r.ok and isinstance(payload, dict):
        if (payload.get("activation") or {}).get("state") != "cancelled":
            return

    # 策略 2：分两步 PATCH（先 SDP 再激活）
    r1, _ = _req(session, "PATCH", staged, timeout, log, json_body={**on, **tf})
    r2, _ = _req(session, "PATCH", staged, timeout, log, json_body=act)
    if r1.ok and r2.ok:
        return

    # 策略 3：GET staged 合并后 PUT 全量
    r0, cur = _req(session, "GET", staged, timeout, log)
    if r0.ok and isinstance(cur, dict):
        cur.update({**tf, **act})
        r3, _ = _req(session, "PUT", staged, timeout, log, json_body=cur)
        if r3.ok:
            return
    raise RuntimeError("写入/激活 SDP 失败，请检查 SDP 内容与设备 IS-05 支持"
                       f"（状态码 {r.status_code}/{r1.status_code}/{r2.status_code}）")


def write_video_sdp(session, conn_base: str, node_base: Optional[str], sdp: str,
                    receiver_id: Optional[str] = None,
                    timeout: float = 5.0, verify: bool = True,
                    log: Callable[[str], None] = print) -> Dict[str, object]:
    """主流程：选 receiver -> 写 SDP -> 激活 -> 校验。成功返回信息 dict。"""
    rid = pick_video_receiver(session, conn_base, node_base, timeout, receiver_id, log)
    log(f"    目标 receiver: {rid}")
    _stage_and_activate(session, conn_base, rid, sdp, timeout, log)
    info: Dict[str, object] = {"receiver_id": rid, "written": True}
    if verify:
        ok = False
        act: Dict[str, object] = {}
        for i in range(6):  # 激活是异步的：设备需要时间起流，轮询等待
            r, act = _req(session, "GET",
                          f"{conn_base}/single/receivers/{rid}/active",
                          timeout, log)
            if r.ok and isinstance(act, dict) and act.get("master_enable"):
                ok = True
                break
            if i < 5:
                time.sleep(1.0)
        if not ok:
            log("    active 原始返回: "
                + json.dumps(act, ensure_ascii=False)[:600])
            raise RuntimeError(
                "激活校验失败：active.master_enable 不为 true"
                "（设备接受了请求但未能真正起流：检查 SDP 参数 PM/TP/depth"
                " 与 ts-refclk 的 PTP clock/domain 是否合法）")
        tf = (act.get("transport_file") or {}).get("data") or ""
        if not tf:
            raise RuntimeError("激活校验失败：active.transport_file 为空")
        log(f"    active SDP 首行: {tf.splitlines()[0] if tf else ''}")
        info["sdp_active"] = True
    return info


# --------------------------------------------------------------------------- #
# 4. mDNS 设备发现：复用 mdns_discovery 模块的 ServiceListener / 网卡处理
# --------------------------------------------------------------------------- #

def _import_mdns():
    """延迟导入 mdns_discovery（目录加入 sys.path；平台已加载时复用缓存）。"""
    mod = sys.modules.get("mdns_discovery")
    if mod is not None:
        return mod
    here = os.path.dirname(os.path.abspath(__file__))
    mdns_dir = os.path.normpath(os.path.join(here, "..", "mdns_discovery"))
    if os.path.isdir(mdns_dir) and mdns_dir not in sys.path:
        sys.path.insert(0, mdns_dir)
    import mdns_discovery
    return mdns_discovery


def _decode_props(props: Optional[dict]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in (props or {}).items():
        key = k.decode("utf-8", "replace") if isinstance(k, bytes) else str(k)
        val = v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
        out[key.lower()] = val
    return out


def _ipv4s(info) -> List[str]:
    try:
        return [a for a in info.parsed_addresses() if ":" not in a]
    except Exception:
        return []


def _match_device(found: Dict[str, object], keyword: str) -> Optional[dict]:
    """在已发现服务中匹配设备。

    _http._tcp     ：按服务实例名 / TXT 'device name' 匹配关键字 -> 设备 IP + Web 端口
    _nmos-node._tcp：TXT 含 api_port/api_proto/api_ver（IS-04 peer-to-peer），
                     按"与 _http 命中同 IP"归属；无 _http 命中时按名字/api_host 匹配
    """
    kw = keyword.strip().lower()
    http_hit = None
    for name, info in found.items():
        if "_http._tcp.local." not in name:
            continue
        props = _decode_props(getattr(info, "properties", None))
        if kw and kw in f"{name} {props.get('device name', '')}".lower():
            ips = _ipv4s(info)
            if ips:
                http_hit = {"name": name, "ip": ips[0],
                            "port": info.port or 80, "props": props}
            break
    node_hit = None
    for name, info in found.items():
        if "_nmos-node._tcp.local." not in name:
            continue
        props = _decode_props(getattr(info, "properties", None))
        ips = _ipv4s(info)
        if http_hit and http_hit["ip"] in ips:
            node_hit = {"name": name, "ip": ips[0], "port": info.port,
                        "props": props}
            break
        if not http_hit and kw and ips and \
                kw in f"{name} {props.get('api_host', '')}".lower():
            node_hit = {"name": name, "ip": ips[0], "port": info.port,
                        "props": props}
            break
    if not http_hit and not node_hit:
        return None
    dev: Dict[str, object] = {"ip": None, "http_port": 80,
                              "api_port": None, "api_proto": "http"}
    if http_hit:
        dev.update(ip=http_hit["ip"], http_port=http_hit["port"],
                   name=http_hit["name"])
    if node_hit:
        p = node_hit["props"]
        # IS-04: TXT api_port 可选，缺省时 API 端口即 SRV 记录端口
        try:
            dev["api_port"] = int(p.get("api_port") or node_hit["port"] or 0) or None
        except ValueError:
            dev["api_port"] = node_hit["port"] or None
        dev["api_proto"] = p.get("api_proto") or "http"
        dev["api_vers"] = p.get("api_ver", "")
        if not dev["ip"]:
            dev.update(ip=node_hit["ip"], name=node_hit["name"])
    return dev


def discover_device(keyword: str, duration: int = 10,
                    iface: Optional[str] = None,
                    log: Callable[[str], None] = print,
                    sleep_fn: Optional[SleepFn] = None) -> Optional[dict]:
    """mDNS 发现设备：浏览 _http._tcp + _nmos-node._tcp，返回设备信息 dict。

    复用 mdns_discovery.ServiceListener（完整保存 ServiceInfo 含 TXT 记录）
    与 _make_zeroconf（网卡选择），本模块只做"设备匹配"。
    """
    mdns = _import_mdns()
    log(f"==> mDNS 发现设备（关键字 {keyword!r}，监听 {duration}s，"
        "类型 _http._tcp + _nmos-node._tcp）...")
    zc = mdns._make_zeroconf(iface, log)
    listener = mdns.ServiceListener(log)
    dev: Optional[dict] = None
    http_at: Optional[float] = None
    try:
        mdns.ServiceBrowser(zc, ["_http._tcp.local.", "_nmos-node._tcp.local."],
                            listener)
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            dev = _match_device(listener.found, keyword)
            if dev and dev.get("api_port"):
                break  # _http 与 _nmos-node 都命中，齐了
            if dev and dev.get("ip"):
                if http_at is None:
                    http_at = time.monotonic()  # 已有 _http，再宽限 3s 等 nmos-node
                elif time.monotonic() - http_at > 3.0:
                    break
            if sleep_fn is not None:
                if not sleep_fn(0.2):
                    log("    发现等待被中断")
                    break
            else:
                time.sleep(0.1)
    finally:
        zc.close()
    if dev and dev.get("ip"):
        log(f"<== 发现设备: {dev.get('name')} -> {dev['ip']} "
            f"(web:{dev['http_port']} nmos_api:{dev.get('api_port') or '未广播'})")
    else:
        log("<== 未发现匹配设备")
        dev = None
    return dev


# --------------------------------------------------------------------------- #
# 5. SDP 内容获取（file / text / url 三选一）
# --------------------------------------------------------------------------- #

def load_sdp(sdp_file: str = "", sdp_text: str = "", sdp_url: str = "",
             session: Optional[requests.Session] = None, timeout: float = 5.0,
             log: Callable[[str], None] = print) -> str:
    if sdp_file:
        with open(sdp_file, "r", encoding="utf-8-sig") as f:
            sdp = f.read()
        log(f"    SDP 来自文件: {sdp_file}")
    elif sdp_text:
        sdp = sdp_text
        log("    SDP 来自参数文本")
    elif sdp_url:
        r = (session or requests.Session()).get(sdp_url, timeout=timeout)
        r.raise_for_status()
        sdp = r.text
        log(f"    SDP 来自 URL: {sdp_url}（{len(sdp)} 字节）")
    else:
        raise RuntimeError("未提供 SDP：sdp_file / sdp_text / sdp_url 三选一")
    sdp = sdp.strip()
    if not sdp.startswith("v=0"):
        log("    [警告] SDP 不以 v=0 开头，请确认内容有效")
    return sdp


# --------------------------------------------------------------------------- #
# 6. 平台测试项
# --------------------------------------------------------------------------- #

def _truthy(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


@register
class NmosSdpWriteCase(TestCase):
    id = "nmos_sdp_write"
    name = "NMOS 写视频SDP"
    category = "NMOS/2110"
    description = ("按 NMOS 标准发现链（mDNS _nmos-node -> Node API controls -> "
                   "IS-05）把视频 SDP 写入 receiver 并激活校验；"
                   "复用 mdns_discovery 做 mDNS 发现，支持绑定本机源 IP 发送")
    params = [
        ParamDef("ip", "设备IP", "192.168.17.62", "str",
                 "支持 {device_ip} 占位符；留空且 mdns=1 时自动发现"),
        ParamDef("port", "Web端口", "80", "int", "设备 HTTP 端口（兜底探测用）"),
        ParamDef("api_port", "NMOS API端口", "0", "int",
                 "0=自动（mDNS TXT 的 api_port，否则逐候选探测）"),
        ParamDef("iface", "本机源IP", "192.168.17.166", "str",
                 "绑定该 IP 发送（走对应网卡）；空=默认路由"),
        ParamDef("mdns", "mDNS发现设备", "0", "str", "1=ip 为空时按设备名自动发现"),
        ParamDef("mdns_name", "设备名关键字", "2110 IP UpDownCross 12G", "str"),
        ParamDef("mdns_duration", "发现时长(秒)", "10", "int"),
        ParamDef("sdp_file", "SDP文件", "", "str", "与 sdp_text/sdp_url 三选一"),
        ParamDef("sdp_text", "SDP文本", "", "str"),
        ParamDef("sdp_url", "SDP的URL", "", "str"),
        ParamDef("receiver_id", "Receiver ID", "", "str",
                 "留空自动选择 format=video 的 receiver"),
        ParamDef("list_only", "仅列出receivers", "0", "str", "1=只查询不写入"),
        ParamDef("timeout", "HTTP超时(秒)", "5", "float"),
        ParamDef("verify", "写后校验active", "1", "str"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        ip = self.p_str("ip").strip()
        http_port = self.p_int("port", 80)
        api_port = self.p_int("api_port", 0) or None
        iface = self.p_str("iface").strip() or None
        timeout = self.p_float("timeout", 5.0)
        data: Dict[str, object] = {}

        def _sleep(sec: float) -> bool:
            return self.sleep_interruptible(sec)

        # ---- 设备 IP：mDNS 发现（复用 mdns_discovery）或直接指定 ----
        if not ip:
            if not _truthy(self.p_str("mdns")):
                return TestResult(TestStatus.FAILED, "未填 ip，且未开启 mDNS 发现")
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED, "用户停止")
            try:
                dev = discover_device(self.p_str("mdns_name"),
                                      self.p_int("mdns_duration", 10),
                                      iface=iface, log=log, sleep_fn=_sleep)
            except OSError as e:
                return TestResult(TestStatus.FAILED,
                                  f"网卡创建失败（iface='{iface}'）: {e}", data=data)
            if not dev:
                return TestResult(TestStatus.FAILED, "mDNS 未发现匹配设备",
                                  data=data)
            ip = dev["ip"]
            http_port = dev.get("http_port") or http_port
            api_port = api_port or dev.get("api_port")
            if dev.get("api_vers"):
                data["nmos_api_vers"] = dev["api_vers"]
        data["device_ip"] = ip

        # ---- 探测 NMOS 端点（Node API + IS-05 Connection API）----
        session = make_session(iface, log)
        log(f"==> NMOS 设备 http://{ip}（iface={iface or '默认'}，"
            f"api_port={api_port or '自动'}）")
        if self.stop_requested:
            return TestResult(TestStatus.SKIPPED, "用户停止")
        node_base, conn_base = resolve_nmos_endpoints(
            session, ip, http_port, api_port, timeout, log)
        if not conn_base:
            return TestResult(TestStatus.FAILED, (
                "未找到 IS-05 Connection API。请确认设备已开启 NMOS"
                "（BMD 菜单中启用 peer-to-peer / NMOS），或用 --api-port 手动指定"),
                data=data)
        data["is05_base"] = conn_base

        # ---- 仅列出 receivers ----
        if _truthy(self.p_str("list_only")):
            try:
                items = list_receivers(session, conn_base, node_base, timeout, log)
            except (RuntimeError, requests.RequestException) as e:
                return TestResult(TestStatus.FAILED, f"查询失败: {e}", data=data)
            data["receivers"] = items
            return TestResult(TestStatus.PASSED,
                              f"共 {len(items)} 个 receiver", data=data)

        # ---- 写 SDP ----
        try:
            sdp = load_sdp(self.p_str("sdp_file"), self.p_str("sdp_text"),
                           self.p_str("sdp_url"), session, timeout, log)
            info = write_video_sdp(session, conn_base, node_base, sdp,
                                   self.p_str("receiver_id").strip() or None,
                                   timeout, _truthy(self.p_str("verify")), log)
        except (RuntimeError, OSError, requests.RequestException) as e:
            return TestResult(TestStatus.FAILED, f"{e}", data=data)
        data.update(info)
        return TestResult(
            TestStatus.PASSED,
            f"SDP 已写入并激活 receiver {info['receiver_id']}", data=data)


# ---------------- 单独运行入口 ----------------
def _main() -> None:
    import argparse
    import builtins
    import functools
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    builtins.print = functools.partial(builtins.print, flush=True)

    ap = argparse.ArgumentParser(
        description="NMOS IS-05 写视频 SDP（可独立运行，亦可被 test_platform 挂载）")
    ap.add_argument("--ip", default=None, help="设备 IP（缺省且 --mdns 时自动发现）")
    ap.add_argument("--port", type=int, default=80, help="设备 Web 端口（兜底）")
    ap.add_argument("--api-port", type=int, default=0,
                    help="NMOS API 端口；0=自动（mDNS TXT 或逐候选探测）")
    ap.add_argument("--iface", default=None,
                    help="绑定本机源 IP 发送（如 192.168.17.166）；mDNS 亦用该网卡")
    ap.add_argument("--sdp-file", default=None, help="SDP 文件路径")
    ap.add_argument("--sdp-text", default=None, help="SDP 文本")
    ap.add_argument("--sdp-url", default=None, help="SDP 的 URL")
    ap.add_argument("--receiver-id", default=None, help="留空自动选视频 receiver")
    ap.add_argument("--list", action="store_true", help="仅列出 receivers")
    ap.add_argument("--mdns", action="store_true", help="mDNS 按设备名发现设备")
    ap.add_argument("--mdns-name", default="2110 IP UpDownCross 12G")
    ap.add_argument("--mdns-duration", type=int, default=10)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--no-verify", action="store_true", help="跳过写后 active 校验")
    args = ap.parse_args()

    case = NmosSdpWriteCase({
        "ip": args.ip or "", "port": str(args.port), "api_port": str(args.api_port),
        "iface": args.iface or "",
        "mdns": "1" if (args.mdns or not args.ip) else "0",
        "mdns_name": args.mdns_name, "mdns_duration": str(args.mdns_duration),
        "sdp_file": args.sdp_file or "", "sdp_text": args.sdp_text or "",
        "sdp_url": args.sdp_url or "", "receiver_id": args.receiver_id or "",
        "list_only": "1" if args.list else "0", "timeout": str(args.timeout),
        "verify": "0" if args.no_verify else "1",
    })
    print(f"[单独运行] {case.name}  ip={args.ip or '(mDNS 自动发现)'}")
    try:
        result = case.run(Context(), log=print)
    except KeyboardInterrupt:
        print("\n[中断] 用户 Ctrl+C")
        return
    print(f"[结果] {result.status.value}  {result.message}")
    if result.data:
        print(f"[产出] {result.data}")


if __name__ == "__main__":
    _main()
