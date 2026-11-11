"""
ST2110 Synced Test - 验证设备 reboot 后是否会出现 unsync 的情况

流程（轮次制）:
1. 发送 reboot 请求
2. 等待 40s（可配置）让设备重启完成
3. 发送一次 sync 检测请求
4. 如果 synced(1)：本轮成功，回到步骤 1 进行下一轮 reboot 测试
5. 如果 unsync(0) 或异常：停止测试，打印当前成功轮次数

用法（一份代码，两种用法）:
1. 单独运行: python st2110_synced_test.py --ip 192.168.17.80
2. 被测试平台挂载: test_platform/platform.json 的 "plugins" 登记本文件路径,
   sync 检测部分包装为测试项 st2110_sync_check;
   与 cgi_reboot 组队列 + 工具栏"循环轮数"即可复现本脚本的 reboot→检测 老化流程。

约束: 平台加载本文件时只做类注册、不执行测试动作(顶层无副作用,
     仅幂等追加 sys.path)。fpga_reboot 的导入延迟到 run_test 内,
     避免平台加载时重复执行其 @register（其已单独登记于 platform.json）。
"""

import os
import requests
import time
import sys
import argparse
from datetime import datetime

# ---- sys.path: 独立运行 / 被平台加载 / 被其他脚本导入 三种场景通用 ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_NET = os.path.normpath(os.path.join(_HERE, ".."))
if _NET not in sys.path:
    sys.path.insert(0, _NET)
_PLATFORM = os.path.normpath(os.path.join(_HERE, "..", "..", "test_platform"))
if os.path.isdir(_PLATFORM) and _PLATFORM not in sys.path:
    sys.path.insert(0, _PLATFORM)

from core.base import (  # noqa: E402
    Context, LogFn, ParamDef, TestCase, TestResult, TestStatus,
)
from core.registry import register  # noqa: E402


# ============ 默认配置 ============
DEFAULT_DEVICE_IP = "192.168.17.80"

REBOOT_WAIT_SECONDS = 70       # reboot 之后等待时间（秒）
REBOOT_URL_PATH = ":8080/api/upgrade/reboot"
SYNC_URL_PATH = ":8081/cgi-bin/smpte2059?action=GET%20ST2110_ENC_STREAM_SYNC%2020"
# SYNC_URL_PATH = "/fpga_st2110/cgi-bin/smpte2059?action=GET%20ST2110_ENC_STREAM_SYNC%2020"
EXPECTED_RESPONSE = "RGET ST2110_ENC_STREAM_SYNC 20 1"


def get_sync_status(device_ip: str, url_path: str = SYNC_URL_PATH,
                    timeout: int = 10) -> str:
    """发送 sync 检测请求，返回原始响应文本（异常返回 "ERROR: ..."）"""
    url = f"http://{device_ip}{url_path}"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text.strip()
    except requests.RequestException as e:
        return f"ERROR: {e}"


def is_synced(response_text: str, expected: str = EXPECTED_RESPONSE) -> bool:
    """
    判断返回值是否为 synced 状态
    期望返回: RGET ST2110_ENC_STREAM_SYNC 20 1
    最后一个字段为 1 表示 synced，0 表示 unsync
    """
    return response_text == expected


def wait_for_device(device_ip: str, wait_seconds: int = REBOOT_WAIT_SECONDS):
    """等待设备重启完成"""
    print(f"[{now()}] 等待设备重启，等待 {wait_seconds} 秒...")
    for remaining in range(wait_seconds, 0, -1):
        sys.stdout.write(f"\r  剩余: {remaining}s ")
        sys.stdout.flush()
        time.sleep(1)
    print(f"\n[{now()}] 等待完成，开始检测 sync 状态")


def now() -> str:
    """返回当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============ 测试平台接入（"脚本即插件"） ============
@register
class St2110SyncCheckCase(TestCase):
    """把 get_sync_status / is_synced 包装为平台测试项：发检测请求并判定。

    单独勾选 = 一次性 sync 检测；
    与 "CGI 接口重启"(cgi_reboot) 组队列 + 工具栏"循环轮数" =
    复现本脚本 run_test 的 reboot→等待→检测 老化流程。
    """
    id = "st2110_sync_check"
    name = "ST2110 同步状态检测"
    category = "ST2110"
    description = "发送 ST2110 sync 检测请求，响应末位为 1 判 synced（通过），否则失败"
    params = [
        ParamDef("ip", "设备 IP", DEFAULT_DEVICE_IP, "str"),
        ParamDef("url_path", "检测接口路径", SYNC_URL_PATH),
        ParamDef("expected", "synced 判定响应", EXPECTED_RESPONSE),
        ParamDef("timeout", "HTTP 超时(秒)", "10", "int"),
        ParamDef("retries", "检测次数(含首次)", "1", "int",
                 "配合 cgi_reboot 组队列时可设大些，等设备完全就绪"),
        ParamDef("retry_wait", "重试间隔(秒)", "5", "int"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        ip = self.p_str("ip")
        url_path = self.p_str("url_path")
        expected = self.p_str("expected")
        timeout = self.p_int("timeout", 10)
        retries = max(1, self.p_int("retries", 1))
        wait = self.p_int("retry_wait", 5)

        log(f"目标 {ip}  接口={url_path}")
        log(f"判定响应: {expected!r}")

        response = ""
        for attempt in range(1, retries + 1):
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED, "用户停止")
            log(f"[第 {attempt}/{retries} 次] GET http://{ip}{url_path}")
            response = get_sync_status(ip, url_path=url_path, timeout=timeout)
            if is_synced(response, expected):
                ctx.set("st2110_synced", True)
                ctx.set("st2110_response", response)
                return TestResult(
                    TestStatus.PASSED,
                    f"SYNCED (第 {attempt} 次检测, 响应: {response})",
                    data={"st2110_synced": True, "st2110_response": response},
                )
            log(f"  响应: {response} -> 未同步")
            if attempt < retries and not self.sleep_interruptible(wait, log):
                return TestResult(TestStatus.SKIPPED, "用户停止（重试等待中）")

        ctx.set("st2110_synced", False)
        ctx.set("st2110_response", response)
        return TestResult(
            TestStatus.FAILED,
            f"UNSYNC: {retries} 次检测均未通过，最后一次响应: {response}",
            data={"st2110_synced": False, "st2110_response": response},
        )


def run_test(device_ip: str, reboot_wait: int, do_reboot: bool):
    """
    轮次制测试循环

    每轮: reboot → 等待 → 检测一次 sync → 成功则进入下一轮，失败则停止

    :param device_ip: 设备 IP
    :param reboot_wait: reboot 后等待秒数
    :param do_reboot: 第一轮是否执行 reboot
    """
    # 延迟导入（见文件头）：平台挂载本文件时不触发 fpga_reboot_test 的重复注册
    from fpga_reboot_test import http_reboot  # POST /fpga_upgrade/api/upgrade/reboot

    print("=" * 60)
    print(f"  ST2110 Synced Test")
    print(f"  设备地址: {device_ip}")
    print(f"  Reboot 等待: {reboot_wait}s")
    print(f"  开始时间: {now()}")
    print("=" * 60)

    success_count = 0
    round_num = 0

    try:
        while True:
            round_num += 1
            print(f"\n{'=' * 40}")
            print(f"  第 {round_num} 轮测试")
            print(f"{'=' * 40}")

            # Step 1: Reboot
            if do_reboot:
                print(f"\n[{now()}] 发送 Reboot 请求...")
                http_reboot(device_ip,REBOOT_URL_PATH)
                wait_for_device(device_ip, reboot_wait)
            else:
                print(f"\n[{now()}] 跳过 Reboot（仅首轮）")
                do_reboot = True  # 后续轮次正常 reboot

            # Step 2: 检测一次 sync 状态
            print(f"[{now()}] 检测 sync 状态...")
            response = get_sync_status(device_ip)

            if is_synced(response):
                success_count += 1
                print(f"[{now()}] 第 {round_num} 轮: SYNCED (响应: {response})")
                print(f"  当前成功轮次数: {success_count}")
                # 成功 → 进入下一轮 reboot
            else:
                # 失败 → 停止测试
                print()
                print("!" * 60)
                print(f"  [UNSYNC 检测到!]")
                print(f"  成功轮次数: {success_count}")
                print(f"  第 {round_num} 轮检测返回: {response}")
                print(f"  时间: {now()}")
                print("!" * 60)
                break

    except KeyboardInterrupt:
        # 用户中断时打印当前成功轮次数
        print(f"\n\n[{now()}] 用户中断测试 (Ctrl+C)")
        print(f"  当前成功轮次数: {success_count}")

    print(f"\n[{now()}] 测试结束")


def main():
    parser = argparse.ArgumentParser(description="ST2110 Synced Test - 验证 unsync 情况")
    parser.add_argument(
        "--ip", default=DEFAULT_DEVICE_IP,
        help=f"设备 IP 地址 (默认: {DEFAULT_DEVICE_IP})"
    )
    parser.add_argument(
        "--t", type=int, default=REBOOT_WAIT_SECONDS,
        help=f"Reboot 后等待秒数 (默认: {REBOOT_WAIT_SECONDS})"
    )
    parser.add_argument(
        "--no-reboot", action="store_true",
        help="首轮跳过 reboot，直接检测 sync 状态"
    )
    args = parser.parse_args()

    run_test(
        device_ip=args.ip,
        reboot_wait=args.t,
        do_reboot=not args.no_reboot,
    )


if __name__ == "__main__":
    main()
