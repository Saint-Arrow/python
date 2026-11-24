"""
ST2110 Synced Test - 验证设备 reboot 后是否会出现 unsync 的情况

流程（轮次制）:
1. 发送 reboot 请求
2. 等待 40s（可配置）让设备重启完成
3. 逐个检测所有流(默认 20/30/40)的 sync 状态
4. 全部 synced(1)：本轮成功，回到步骤 1 进行下一轮 reboot 测试
5. 任一流 unsync(0) 或异常：停止测试，打印当前成功轮次数

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
import re
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

# 需要检测 sync 的流 ID 列表：全部 synced 才算通过，任一 unsync 即失败
SYNC_STREAM_IDS = ("20", "30", "40")

# URL / 期望响应模板：<stream_id> 会被替换为实际流 ID。
# 注意：占位符用 <stream_id> 而非 {stream_id}，避免被平台 Runner 的
# Context {var} 占位符替换机制误处理。
SYNC_URL_TEMPLATE = \
    ":8081/cgi-bin/smpte2059?action=GET%20ST2110_ENC_STREAM_SYNC%20<stream_id>"
# SYNC_URL_TEMPLATE = "/fpga_st2110/cgi-bin/smpte2059?action=GET%20ST2110_ENC_STREAM_SYNC%20<stream_id>"
EXPECTED_TEMPLATE = "RGET ST2110_ENC_STREAM_SYNC <stream_id> 1"


def _ensure_template(val: str) -> str:
    """把各种历史写法统一成带 <stream_id> 占位符的模板。

    新式:        "...SYNC%20<stream_id>"                     -> 原样返回
    {stream_id}: "...SYNC%20{stream_id}"                     -> "...SYNC%20<stream_id>"
    旧 url_path: "...ST2110_ENC_STREAM_SYNC%2020"            -> "...SYNC%20<stream_id>"
    旧 expected: "RGET ST2110_ENC_STREAM_SYNC 20 1"          -> "RGET ... <stream_id> 1"
    """
    val = val.strip()
    if "<stream_id>" in val:
        return val
    if "{stream_id}" in val:
        return val.replace("{stream_id}", "<stream_id>")
    # 旧式 url_path：末尾 %20<数字> 替换为占位符
    head, sep, tail = val.rpartition("%20")
    if sep and tail.isdigit():
        return head + "%20<stream_id>"
    # 旧式 expected：末两字段为 <stream_id> <状态>，把倒数第二段替换为占位符
    return re.sub(r"\s+(\S+)\s+(\S+)$", r" <stream_id> \2", val)


def parse_stream_ids(streams_cfg: str) -> list:
    """解析逗号分隔的流 ID 配置，如 "20,30,40" -> ["20", "30", "40"]"""
    return [s.strip() for s in streams_cfg.split(",") if s.strip()]


def get_sync_status(device_ip: str, stream_id: str,
                    url_template: str = SYNC_URL_TEMPLATE,
                    timeout: int = 10) -> str:
    """发送指定流的 sync 检测请求，返回原始响应文本（异常返回 "ERROR: ..."）"""
    url = f"http://{device_ip}{url_template.replace('<stream_id>', stream_id)}"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text.strip()
    except requests.RequestException as e:
        return f"ERROR: {e}"


def is_synced(response_text: str, stream_id: str,
              expected_template: str = EXPECTED_TEMPLATE) -> bool:
    """
    判断指定流返回值是否为 synced 状态
    期望返回: RGET ST2110_ENC_STREAM_SYNC <stream_id> 1
    最后一个字段为 1 表示 synced，0 表示 unsync
    """
    return response_text == expected_template.replace("<stream_id>", stream_id)


def check_all_streams(device_ip: str, stream_ids=SYNC_STREAM_IDS,
                      url_template: str = SYNC_URL_TEMPLATE,
                      expected_template: str = EXPECTED_TEMPLATE,
                      timeout: int = 10, log=print):
    """逐个检测所有流的 sync 状态。

    :return: (all_synced: bool, responses: dict{stream_id: response})
    """
    responses = {}
    all_synced = True
    for sid in stream_ids:
        resp = get_sync_status(device_ip, sid,
                               url_template=url_template, timeout=timeout)
        responses[sid] = resp
        ok = is_synced(resp, sid, expected_template=expected_template)
        if not ok:
            all_synced = False
        log(f"  流 {sid}: {resp} -> {'SYNCED' if ok else '未同步'}")
    return all_synced, responses


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
    description = ("逐流发送 ST2110 sync 检测请求(默认 20/30/40)，"
                   "全部流末位为 1 判 synced（通过），任一流未同步即失败")
    params = [
        ParamDef("ip", "设备 IP", DEFAULT_DEVICE_IP, "str"),
        ParamDef("streams", "检测流 ID 列表(逗号分隔)", ",".join(SYNC_STREAM_IDS),
                 "str", "全部 synced 才通过，任一 unsync 即失败"),
        ParamDef("url_path", "检测接口路径模板", SYNC_URL_TEMPLATE, "str",
                 "含 <stream_id> 占位符；旧式单流/{stream_id} 写法会自动转换"),
        ParamDef("expected", "synced 判定响应模板", EXPECTED_TEMPLATE, "str",
                 "含 <stream_id> 占位符；旧式单流/{stream_id} 写法会自动转换"),
        ParamDef("timeout", "HTTP 超时(秒)", "10", "int"),
        ParamDef("retries", "检测次数(含首次)", "1", "int",
                 "配合 cgi_reboot 组队列时可设大些，等设备完全就绪"),
        ParamDef("retry_wait", "重试间隔(秒)", "5", "int"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        ip = self.p_str("ip")
        stream_ids = parse_stream_ids(self.p_str("streams")) or list(SYNC_STREAM_IDS)
        url_template = _ensure_template(self.p_str("url_path"))
        expected_template = _ensure_template(self.p_str("expected"))
        timeout = self.p_int("timeout", 10)
        retries = max(1, self.p_int("retries", 1))
        wait = self.p_int("retry_wait", 5)

        log(f"目标 {ip}  检测流: {stream_ids}")
        log(f"接口模板: {url_template}")
        log(f"判定模板: {expected_template!r}")

        responses = {}
        summary = ""
        for attempt in range(1, retries + 1):
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED, "用户停止")
            log(f"[第 {attempt}/{retries} 次] 逐流检测 sync 状态")
            all_synced, responses = check_all_streams(
                ip, stream_ids, url_template=url_template,
                expected_template=expected_template,
                timeout=timeout, log=log)
            summary = "; ".join(f"流{k}: {v}" for k, v in responses.items())
            if all_synced:
                ctx.set("st2110_synced", True)
                ctx.set("st2110_response", summary)
                return TestResult(
                    TestStatus.PASSED,
                    f"SYNCED (第 {attempt} 次检测, {summary})",
                    data={"st2110_synced": True,
                          "st2110_response": summary,
                          "streams": responses},
                )
            bad = [k for k, v in responses.items()
                   if not is_synced(v, k, expected_template=expected_template)]
            log(f"  未同步的流: {bad}，共 {len(bad)}/{len(stream_ids)} 路未通过")
            if attempt < retries and not self.sleep_interruptible(wait, log):
                return TestResult(TestStatus.SKIPPED, "用户停止（重试等待中）")

        ctx.set("st2110_synced", False)
        ctx.set("st2110_response", summary)
        return TestResult(
            TestStatus.FAILED,
            f"UNSYNC: {retries} 次检测均有流未同步，最后响应: {summary}",
            data={"st2110_synced": False,
                  "st2110_response": summary,
                  "streams": responses},
        )


def run_test(device_ip: str, reboot_wait: int, do_reboot: bool):
    """
    轮次制测试循环

    每轮: reboot → 等待 → 逐流检测 sync → 全部成功则进入下一轮，任一失败则停止

    :param device_ip: 设备 IP
    :param reboot_wait: reboot 后等待秒数
    :param do_reboot: 第一轮是否执行 reboot
    """
    # 延迟导入（见文件头）：平台挂载本文件时不触发 fpga_reboot_test 的重复注册
    from fpga_reboot_test import http_reboot  # POST /fpga_upgrade/api/upgrade/reboot

    print("=" * 60)
    print(f"  ST2110 Synced Test")
    print(f"  设备地址: {device_ip}")
    print(f"  检测流: {list(SYNC_STREAM_IDS)}")
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

            # Step 2: 逐流检测 sync 状态（全部 synced 才算本轮成功）
            print(f"[{now()}] 检测 sync 状态（流 {list(SYNC_STREAM_IDS)}）...")
            all_synced, responses = check_all_streams(device_ip, log=print)

            if all_synced:
                success_count += 1
                print(f"[{now()}] 第 {round_num} 轮: SYNCED")
                for sid, resp in responses.items():
                    print(f"  流 {sid}: {resp}")
                print(f"  当前成功轮次数: {success_count}")
                # 成功 → 进入下一轮 reboot
            else:
                # 任一流失败 → 停止测试
                print()
                print("!" * 60)
                print(f"  [UNSYNC 检测到!]")
                print(f"  成功轮次数: {success_count}")
                for sid, resp in responses.items():
                    mark = "OK" if is_synced(resp, sid) else "UNSYNC"
                    print(f"  流 {sid} [{mark}]: {resp}")
                print(f"  第 {round_num} 轮检测时间: {now()}")
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
