# -*- coding: utf-8 -*-
"""CGI(HTTP) 接口重启控制模块 —— "脚本即插件"重构（一份代码，两种用法）

从 net/st2110_synced_test/st2110_synced_test.py 抽取的 CGI 重启控制逻辑:
    POST http://{ip}/fpga_upgrade/api/upgrade/reboot
(旧接口为 :8080/api/upgrade/reboot, 需要时改 url_path 参数即可)

用法 1: 单独运行(CGI 重启老化, 默认无限循环, Ctrl+C 退出)
    python cgi_reboot_test.py
    python cgi_reboot_test.py --ip 192.168.13.168 --rounds 3

用法 2: 被测试平台挂载
    test_platform/platform.json 的 "plugins" 列表登记本文件路径,
    平台启动时自动 import 本文件, @register 的类即出现在 UI 测试项列表。

用法 3: 作为库被其他脚本导入(如 st2110_synced_test.py)
    from cgi_reboot_test import http_reboot

约束: 平台加载本文件时只做类注册、不执行测试动作(顶层无副作用,
     仅幂等追加 sys.path 以保证三种场景下 core 均可导入)。
"""

import os
import sys

import requests

# ---- 保证 core 可导入: 独立运行 / 被其他脚本导入 / 被平台加载 三种场景通用 ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_PLATFORM = os.path.normpath(os.path.join(_HERE, "..", "test_platform"))
if os.path.isdir(_PLATFORM) and _PLATFORM not in sys.path:
    sys.path.insert(0, _PLATFORM)

from core.base import (  # noqa: E402
    Context, LogFn, ParamDef, TestCase, TestResult, TestStatus,
)
from core.registry import register  # noqa: E402


# ============ 默认配置 ============
DEFAULT_DEVICE_IP = "192.168.13.168"
DEFAULT_REBOOT_URL_PATH = "/fpga_upgrade/api/upgrade/reboot"  # 旧: :8080/api/upgrade/reboot
DEFAULT_REBOOT_WAIT_SECONDS = 70


def http_reboot(ip: str, url_path: str = DEFAULT_REBOOT_URL_PATH,
                timeout: int = 10, log=print) -> bool:
    """发送 CGI(HTTP) 重启请求, 成功返回 True。

    :param ip: 设备 IP
    :param url_path: 重启接口路径(默认 /fpga_upgrade/api/upgrade/reboot)
    :param timeout: HTTP 超时秒数
    :param log: 日志函数(默认 print, 平台运行时传入统一 log)
    """
    url = f"http://{ip}{url_path}"
    try:
        resp = requests.post(url, timeout=timeout)
        log(f"Reboot 请求已发送, HTTP 状态码: {resp.status_code}")
        return True
    except requests.RequestException as e:
        log(f"Reboot 请求失败: {e}")
        return False


@register
class CgiRebootCase(TestCase):
    id = "cgi_reboot"
    name = "CGI 接口重启"
    category = "设备控制"
    description = "循环发送 CGI(HTTP) reboot 请求做重启老化，等待期间可被平台停止"
    params = [
        ParamDef("ip", "设备 IP", DEFAULT_DEVICE_IP, "str",
                 "支持 {device_ip} 引用 mDNS 发现结果"),
        ParamDef("url_path", "重启接口路径", DEFAULT_REBOOT_URL_PATH),
        ParamDef("timeout", "HTTP 超时(秒)", "10", "int"),
        ParamDef("reboot_wait", "重启等待(秒)", str(DEFAULT_REBOOT_WAIT_SECONDS), "int"),
        ParamDef("rounds", "循环轮数(0=无限)", "1", "int"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        ip = self.p_str("ip")
        url_path = self.p_str("url_path")
        timeout = self.p_int("timeout", 10)
        wait = self.p_int("reboot_wait", DEFAULT_REBOOT_WAIT_SECONDS)
        rounds = self.p_int("rounds", 1)

        log(f"目标 {ip}  接口={url_path}  超时={timeout}s  重启等待={wait}s  "
            f"轮数={'无限' if rounds == 0 else rounds}")

        done = 0
        while rounds == 0 or done < rounds:
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED, f"用户停止，已完成 {done} 轮")
            done += 1

            log(f"[第 {done} 轮] 发送 CGI 重启请求 POST http://{ip}{url_path}")
            if not http_reboot(ip, url_path, timeout, log=log):
                return TestResult(TestStatus.FAILED,
                                  f"第 {done} 轮 reboot 请求发送失败")
            if not self.sleep_interruptible(wait, log):
                return TestResult(TestStatus.SKIPPED,
                                  f"用户停止（重启等待中），已完成 {done} 轮")

        return TestResult(TestStatus.PASSED, f"完成 {done} 轮重启循环",
                          data={"reboot_rounds": done})


# ---------------- 单独运行入口 ----------------
def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description="CGI(HTTP) 接口重启老化测试（可独立运行，亦可被 test_platform 挂载）")
    ap.add_argument("--ip", default=DEFAULT_DEVICE_IP, help="设备 IP")
    ap.add_argument("--rounds", type=int, default=0,
                    help="循环轮数，0=无限循环（默认，Ctrl+C 退出）")
    args = ap.parse_args()

    case = CgiRebootCase({"ip": args.ip, "rounds": str(args.rounds)})
    print(f"[单独运行] {case.name} -> {args.ip}"
          f"（rounds={'无限' if args.rounds == 0 else args.rounds}，Ctrl+C 退出）")
    try:
        result = case.run(Context(), log=print)
    except KeyboardInterrupt:
        print("\n[中断] 用户 Ctrl+C")
        return
    print(f"[结果] {result.status.value}  {result.message}")


if __name__ == "__main__":
    _main()
