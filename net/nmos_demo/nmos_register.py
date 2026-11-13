# -*- coding: utf-8 -*-
"""NMOS IS-04 Registry 注册器（虚拟设备 stage A）

流程（对齐 qx/BMD 真机行为）：
  1. 发现 Registry：_nmos-registration._tcp（mDNS，取 pri 最小），
     也支持 --registry 手动指定（本实验网：ConductIP 192.168.17.68:8235）
  2. POST node / device / sender 资源文档（从本机 Node API 静态树拉取）
  3. 每 5s POST 心跳；连接被拒/心跳 404 时全量重注册

用法：
  python nmos_register.py                          # 自动发现 Registry
  python nmos_register.py --registry 192.168.17.68:8235
依赖：pip install zeroconf
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

NODE_API = "http://192.168.17.166:8090/x-nmos/node/v1.3"
NODE_ID = "6e2a9f10-3b4c-4d5e-8f90-a1b2c3d4e5f6"
DEVICE_ID = "7f3b8a20-4c5d-4e6f-9a01-b2c3d4e5f6a7"
SENDER_ID = "ac6e1d50-7f8a-4b9c-8d34-e5f6a7b8c9da"
HEARTBEAT_INTERVAL = 5


def http(method, url, body=None, content_type="application/json", timeout=5):
    """返回 (status, text)；网络异常返回 (None, str(exc))"""
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else body.encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def get_json(url):
    status, text = http("GET", url)
    if status != 200:
        raise RuntimeError("GET %s -> %s %s" % (url, status, text[:200]))
    return json.loads(text)


def discover_registry(timeout=5):
    """mDNS 找 _nmos-registration._tcp，返回 host:port（pri 最小优先）。"""
    try:
        from zeroconf import ServiceBrowser, Zeroconf

        hits = []

        class L:
            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if not info or not info.addresses:
                    return
                props = info.decoded_properties or {}
                hits.append((int(props.get(b"pri", b"99") or 99),
                             "%s:%d" % (".".join(map(str, info.addresses[0])), info.port)))

            def update_service(self, zc, type_, name):
                pass

            def remove_service(self, zc, type_, name):
                pass

        zc = Zeroconf()
        ServiceBrowser(zc, "_nmos-registration._tcp.local.", L())
        time.sleep(timeout)
        zc.close()
        if hits:
            hits.sort()
            return hits[0][1]
    except ImportError:
        pass
    return None


def register_all(reg_base, ver):
    """POST node/device/source/flow/sender 完整资源链。返回 True/False。

    必须按依赖顺序注册：node -> device -> source -> flow -> sender，
    否则部分 Registry 会校验 sender.flow_id / flow.source_id 引用是否存在。
    """
    flows, sources = [], []
    # 逐个资源拉取完整文档（/flows/<id>/），列表摘要可能缺字段导致 schema 失败
    try:
        for f in get_json("%s/flows/" % NODE_API):
            fid = f.get("id")
            try:
                flows.append(get_json("%s/flows/%s/" % (NODE_API, fid)))
            except Exception:
                flows.append(f)
    except Exception as e:
        print("[REG] 拉取 flows 失败: %s" % e, flush=True)
    try:
        for s in get_json("%s/sources/" % NODE_API):
            sid = s.get("id")
            try:
                sources.append(get_json("%s/sources/%s/" % (NODE_API, sid)))
            except Exception:
                sources.append(s)
    except Exception as e:
        print("[REG] 拉取 sources 失败: %s" % e, flush=True)

    res = [
        ("node", get_json("%s/self/" % NODE_API)),
        ("device", get_json("%s/devices/%s/" % (NODE_API, DEVICE_ID))),
    ]
    for s in sources:
        res.append(("source", s))
    for f in flows:
        res.append(("flow", f))
    res.append(("sender", get_json("%s/senders/%s/" % (NODE_API, SENDER_ID))))

    registered = []
    ok = True
    for rtype, doc in res:
        body = json.dumps({"type": rtype, "data": doc})
        url = "%s/x-nmos/registration/%s/resource" % (reg_base, ver)
        status, text = http("POST", url, body)
        print("[REG] %-6s -> %s %s" % (rtype, status, text[:120]), flush=True)
        if status in (200, 201):
            registered.append((rtype, doc.get("id")))
        else:
            ok = False
    return ok, registered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", help="host:port，缺省 mDNS 自动发现")
    ap.add_argument("--ver", default="v1.3", help="Registration API 版本")
    ap.add_argument("--heartbeat", type=float, default=HEARTBEAT_INTERVAL)
    args = ap.parse_args()

    reg = args.registry
    while True:
        if not reg:
            reg = discover_registry()
        if not reg:
            print("[DISC] 未发现 _nmos-registration._tcp，%ds 后重试" % 10, flush=True)
            time.sleep(10)
            continue
        reg_base = "http://%s" % reg
        print("[DISC] Registry = %s" % reg_base, flush=True)

        ok, registered = register_all(reg_base, args.ver)
        if not ok:
            print("[REG] 注册失败，10s 后重试", flush=True)
            reg = None  # 重新发现
            time.sleep(10)
            continue

        # IS-04 要求每种资源单独发心跳，否则父资源超时被删后子资源注册会报
        # "unknown parent device"。这里对所有已注册资源统一保活。
        plural = {"node": "nodes", "device": "devices", "sender": "senders",
                  "receiver": "receivers", "flow": "flows", "source": "sources"}
        while True:
            time.sleep(args.heartbeat)
            all_ok = True
            for rtype, rid in registered:
                hb_url = "%s/x-nmos/registration/%s/health/%s/%s" % (
                    reg_base, args.ver, plural[rtype], rid)
                status, text = http("POST", hb_url, "health", "text/plain")
                if status != 200:
                    all_ok = False
            if not all_ok:
                print("[HB ] 心跳异常，需要重新注册", flush=True)
                break
        reg = args.registry  # 优先用手动指定的


if __name__ == "__main__":
    main()
