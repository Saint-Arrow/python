# -*- coding: utf-8 -*-
"""UDP 重启老化测试 —— "脚本即插件"重构示范（一份代码，两种用法）

用法 1：单独运行（行为同旧脚本，默认无限循环，Ctrl+C 退出）
    python udp_reboot_test.py
    python udp_reboot_test.py --ip 192.168.13.159 --rounds 3

用法 2：被测试平台挂载
    test_platform/platform.json 的 "plugins" 列表登记本文件路径，
    平台启动时自动 import 本文件，@register 的类即出现在 UI 测试项列表。

约束：平台加载本文件时只做类注册、不执行测试动作（顶层无执行代码），
     所以原脚本顶层的 while 循环必须搬进 run() / _main() 里。
"""

import binascii
import os
import socket
import sys

# ---- 独立运行时把 test_platform 根目录加入 sys.path；被平台加载时不触发 ----
if __name__ == "__main__":
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _PLATFORM = os.path.normpath(os.path.join(_HERE, "..", "test_platform"))
    if os.path.isdir(_PLATFORM):
        sys.path.insert(0, _PLATFORM)

from core.base import (  # noqa: E402
    Context, LogFn, ParamDef, TestCase, TestResult, TestStatus,
)
from core.registry import register  # noqa: E402


def udp_sendmsg(ip, port, hex_msg):
    """向 ip:port 发送一条十六进制字符串形式的 UDP 报文（逻辑同旧脚本）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(binascii.unhexlify(hex_msg), (ip, port))


@register
class UdpRebootCase(TestCase):
    id = "udp_reboot"
    name = "UDP 指令重启"
    category = "设备控制"
    description = "循环发送 复位/关机 UDP 指令做重启老化，等待期间可被平台停止"
    params = [
        ParamDef("ip", "设备 IP", "192.168.13.169", "str",
                 "支持 {device_ip} 引用 mDNS 发现结果"),
        ParamDef("port", "UDP 端口", "1259", "int"),
        ParamDef("on_msg", "复位指令(hex)", "8101040003ff"),
        ParamDef("off_msg", "关机指令(hex)", "8101040002ff"),
        ParamDef("interval", "复位→关机间隔(秒)", "5", "int"),
        ParamDef("reboot_wait", "重启等待(秒)", "30", "int"),
        ParamDef("rounds", "循环轮数(0=无限)", "1", "int"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        ip = self.p_str("ip")
        port = self.p_int("port", 1259)
        on_msg, off_msg = self.p_str("on_msg"), self.p_str("off_msg")
        interval = self.p_int("interval", 5)
        wait = self.p_int("reboot_wait", 30)
        rounds = self.p_int("rounds", 1)

        log(f"目标 {ip}:{port}  复位={on_msg}  关机={off_msg}  "
            f"间隔={interval}s  重启等待={wait}s  "
            f"轮数={'无限' if rounds == 0 else rounds}")

        done = 0
        while rounds == 0 or done < rounds:
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED, f"用户停止，已完成 {done} 轮")
            done += 1

            log(f"[第 {done} 轮] 发送复位指令 {on_msg}")
            udp_sendmsg(ip, port, on_msg)
            if not self.sleep_interruptible(interval, log):
                return TestResult(TestStatus.SKIPPED,
                                  f"用户停止（复位后等待中），已完成 {done - 1} 轮")

            log(f"[第 {done} 轮] 发送关机指令 {off_msg}")
            udp_sendmsg(ip, port, off_msg)
            if not self.sleep_interruptible(wait, log):
                return TestResult(TestStatus.SKIPPED,
                                  f"用户停止（重启等待中），已完成 {done} 轮")

        return TestResult(TestStatus.PASSED, f"完成 {done} 轮重启循环",
                          data={"reboot_rounds": done})


# ---------------- 单独运行入口 ----------------
def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description="UDP 重启老化测试（可独立运行，亦可被 test_platform 挂载）")
    ap.add_argument("--ip", default="192.168.13.169", help="设备 IP")
    ap.add_argument("--port", type=int, default=1259, help="UDP 端口")
    ap.add_argument("--rounds", type=int, default=0,
                    help="循环轮数，0=无限循环（默认，同旧脚本）")
    args = ap.parse_args()

    case = UdpRebootCase({
        "ip": args.ip, "port": str(args.port), "rounds": str(args.rounds)})
    print(f"[单独运行] {case.name} -> {args.ip}:{args.port}"
          f"（rounds={'无限' if args.rounds == 0 else args.rounds}，Ctrl+C 退出）")
    try:
        result = case.run(Context(), log=print)
    except KeyboardInterrupt:
        print("\n[中断] 用户 Ctrl+C")
        return
    print(f"[结果] {result.status.value}  {result.message}")


if __name__ == "__main__":
    _main()
