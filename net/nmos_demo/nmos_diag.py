# -*- coding: utf-8 -*-
"""NMOS 诊断快照工具 —— 自动抓取 mDNS 广播 + 各节点 Node API 结构。

产出：nmos_demo/diags/snapshot_<时间戳>.json
目的：把"当前网络上所有 NMOS 设备的真实状态"固化下来，便于跨时间点对比，
      避免凭记忆/假设推断。每次排查前后各跑一次即可 diff。

用法：
    python nmos_diag.py            # 抓默认 v1.3 的 self/devices/senders/receivers
    python nmos_diag.py --api v1.2 # 指定版本
"""
import json
import os
import time
import datetime
import argparse
import urllib.request

try:
    from zeroconf import Zeroconf, ServiceBrowser
except ImportError:
    Zeroconf = None

DIAG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diags")
MANUAL_NODES = ["192.168.17.62:8090", "192.168.17.68:8870"]  # 已知但可能离线，补进探测


# --------------------------------------------------------------------------- #
# 1) mDNS 快照
# --------------------------------------------------------------------------- #
def snapshot_mdns(wait=8):
    if Zeroconf is None:
        return {"_nmos-node": [], "_nmos-registration": [], "error": "zeroconf not installed"}
    out = {"_nmos-node": [], "_nmos-registration": []}

    class L:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if not info:
                return
            props = {
                (k.decode() if isinstance(k, bytes) else k):
                (v.decode(errors="replace") if isinstance(v, bytes) else v)
                for k, v in (info.properties or {}).items()
            }
            rec = {
                "instance": name,
                "server": info.server,
                "port": info.port,
                "addresses": ["%d.%d.%d.%d" % tuple(a) for a in info.addresses],
                "txt": props,
            }
            out.setdefault(type_.split(".")[0], []).append(rec)

        def update_service(self, *a):
            pass

        def remove_service(self, *a):
            pass

    zc = Zeroconf()
    ServiceBrowser(zc, "_nmos-node._tcp.local.", L())
    ServiceBrowser(zc, "_nmos-registration._tcp.local.", L())
    time.sleep(wait)
    zc.close()
    return out


# --------------------------------------------------------------------------- #
# 2) Node API 快照
# --------------------------------------------------------------------------- #
def get_json(url, timeout=3):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def snapshot_node(host, api_ver):
    base = "http://%s/x-nmos/node/%s" % (host, api_ver)
    rec = {"reachable": False}
    s, err = get_json(base + "/self/")
    if s is None:
        rec["error"] = err
        return rec
    rec["reachable"] = True
    rec["self"] = {
        "id": s.get("id"), "label": s.get("label"),
        "manufacturer": s.get("manufacturer"), "model": s.get("model"),
        "href": s.get("href"), "type": s.get("type"),
    }
    d, _ = get_json(base + "/devices/")
    if d is not None:
        rec["devices"] = [{
            "id": x.get("id"), "type": x.get("type"), "label": x.get("label"),
            "manufacturer": x.get("manufacturer"), "model": x.get("model"),
            "controls_count": len(x.get("controls") or []),
            "senders": x.get("senders"), "receivers": x.get("receivers"),
        } for x in d]
    snd, _ = get_json(base + "/senders/")
    if snd is not None:
        rec["senders_count"] = len(snd)
    rcv, _ = get_json(base + "/receivers/")
    if rcv is not None:
        rec["receivers_count"] = len(rcv)
    return rec


def snapshot_nodes(api_ver):
    hosts = {}
    # 从 mDNS 结果反推 host:port
    for r in snapshot_mdns.__last_result.get("_nmos-node", []):
        for addr in r["addresses"]:
            hosts["%s:%d" % (addr, r["port"])] = True
    for m in MANUAL_NODES:
        hosts[m] = True
    return {h: snapshot_node(h, api_ver) for h in hosts}


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="v1.3")
    ap.add_argument("--wait", type=int, default=8)
    args = ap.parse_args()

    mdns = snapshot_mdns(args.wait)
    snapshot_mdns.__last_result = mdns
    api = snapshot_nodes(args.api)

    out = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "api_ver": args.api,
        "mdns": mdns,
        "nodes_api": api,
    }
    os.makedirs(DIAG_DIR, exist_ok=True)
    fn = os.path.join(DIAG_DIR, "snapshot_%s.json" %
                     datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # 控制台摘要
    print("=== mDNS _nmos-node ===")
    for r in mdns.get("_nmos-node", []):
        print("  %s  server=%s port=%d addr=%s" %
              (r["instance"], r["server"], r["port"], r["addresses"]))
    print("=== mDNS _nmos-registration ===")
    for r in mdns.get("_nmos-registration", []):
        print("  %s  port=%d addr=%s" % (r["instance"], r["port"], r["addresses"]))
    print("=== Node API (%s) ===" % args.api)
    for h, rec in api.items():
        if rec.get("reachable"):
            self_lbl = rec["self"].get("label")
            mfr = rec["self"].get("manufacturer")
            nd = rec.get("devices") or []
            print("  %s  OK  label=%s mfr=%s devices=%d senders=%s" %
                  (h, self_lbl, mfr, len(nd), rec.get("senders_count")))
        else:
            print("  %s  UNREACHABLE (%s)" % (h, rec.get("error", "")[:60]))
    print("WROTE %s" % fn)


if __name__ == "__main__":
    main()
