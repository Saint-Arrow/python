#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键拉起 NMOS 虚拟设备三件套并统一托管（stage A 整合入口）。

  1) Node API 静态服务器  nmos_server.py    (net/nmos_demo)    -> TCP 8090
  2) mDNS 广播            nmos_mdns.py       (net/nmos_demo)    -> _nmos-node._tcp
  3) Registry 注册 + 心跳 nmos_register.py   (net/nmos_demo)    -> 192.168.17.68:8235

特性：
  - 启动前清理同名旧进程，释放 8090 / 避免重复注册
  - mDNS 广播 host 名(--host) 需与 self.hostname 一致，默认 vhd-166.local.
  - server 端口就绪检测后，再起 mdns / register
  - 子进程崩溃自动重启（最多退避 2s）
  - 前台 Ctrl+C 或收到 SIGTERM 时级联停止全部子进程

用法：
    python nmos_all.py
    python nmos_all.py --registry 192.168.17.68:8235 --iface 192.168.17.166 --host vhd-166.local.
"""

import argparse
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
PY = sys.executable
NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

SERVER_CMD = [PY, os.path.join(HERE, "nmos_server.py"), "8090"]


def cleanup_ours():
    """关闭之前遗留的同名 python 进程（仅限本项目脚本），释放 8090。"""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object {$_.CommandLine -match 'nmos_(server|mdns|register).py'} | "
             "ForEach-Object { $_.ProcessId }"],
            text=True, stderr=subprocess.DEVNULL)
        for line in out.split():
            pid = line.strip()
            if pid.isdigit():
                subprocess.run(["taskkill", "/PID", pid, "/F", "/T"],
                               stderr=subprocess.DEVNULL)
        print("[LAUNCH] 已清理遗留同名进程")
    except Exception as e:
        print("[LAUNCH] 清理遗留进程跳过:", e)


def wait_ready(url, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def spawn(cmd, cwd):
    return subprocess.Popen(cmd, cwd=cwd, creationflags=NEW_GROUP)


def build_procs(registry, iface, host):
    mdns = [PY, os.path.join(BASE, "nmos_demo", "nmos_mdns.py"),
            "--name", "nmos-cpp_node_192-168-17-166:8090",
            "--iface", iface, "--port", "8090",
            "--host", host]
    reg = [PY, os.path.join(BASE, "nmos_demo", "nmos_register.py"),
           "--registry", registry]
    return {
        "server": {"cmd": SERVER_CMD,
                   "cwd": HERE,
                   "ready": "http://127.0.0.1:8090/x-nmos/node/v1.2/self/"},
        "mdns":   {"cmd": mdns, "cwd": HERE, "ready": None},
        "reg":    {"cmd": reg,  "cwd": HERE, "ready": None},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="192.168.17.68:8235")
    ap.add_argument("--iface", default="192.168.17.166")
    ap.add_argument("--host", default="vhd-166.local.",
                   help="mDNS 广播 host 名，需与 self.hostname 一致")
    args = ap.parse_args()

    cleanup_ours()
    procs = build_procs(args.registry, args.iface, args.host)

    live = {}
    for name, cfg in procs.items():
        p = spawn(cfg["cmd"], cfg["cwd"])
        live[name] = p
        print("[LAUNCH] %-6s started pid=%d" % (name, p.pid))
        if cfg["ready"]:
            print("[LAUNCH] %-6s ready=%s" % (name, wait_ready(cfg["ready"])))
        else:
            time.sleep(1)

    print("[LAUNCH] 三件套就绪。Ctrl+C 退出会级联停止全部子进程。")
    try:
        while True:
            time.sleep(1)
            for name, cfg in procs.items():
                if live[name].poll() is not None:
                    print("[LAUNCH] %s 退出(code=%s)，2s 后重启" % (name, live[name].returncode))
                    time.sleep(2)
                    live[name] = spawn(cfg["cmd"], cfg["cwd"])
                    print("[LAUNCH] %-6s restarted pid=%d" % (name, live[name].pid))
    except KeyboardInterrupt:
        print("\n[LAUNCH] 收到 Ctrl+C，正在停止子进程...")
    finally:
        for p in live.values():
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        time.sleep(1)
        for p in live.values():
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass
        print("[LAUNCH] 已停止全部子进程")


if __name__ == "__main__":
    main()
