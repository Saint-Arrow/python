# -*- coding: utf-8 -*-
"""
PTP Domain (SMPTE 2059) 设置/查询测试 - 基于 FPGA ST2110 CGI 接口

接口约定（真机 192.168.13.169 实测确认）:
    设置:  http://{ip}/fpga_st2110/cgi-bin/smpte2059?action=SET%20DOMAIN_NBR%20127
           （必须下划线写法 DOMAIN_NBR；空格写法 SET DOMAIN NBR v 固件返回 ERROR；
             URL 中其余空格编码为 %20，不能用 +）
    生效:  http://{ip}/fpga_st2110/cgi-bin/smpte2059?action=SET%20EFFECTUATE（重启 ptp4l）
    查询:  http://{ip}/fpga_st2110/cgi-bin/smpte2059?action=GET%20DOMAIN_NBR（生效后约15s复核）

实测响应格式（HTTP 200，失败时 body 为裸文本 "ERROR"）:
    SET DOMAIN_NBR 127 -> RSET DOMAIN_NBR OK    （不回显值，成功标志 OK）
    SET EFFECTUATE     -> RSET EFFECTUATE OK
    GET DOMAIN_NBR     -> RGET DOMAIN_NBR 127

用法（一份代码，两种用法）:
1. 单独运行:
    python ptp_domain_test.py --ip 192.168.13.169 --query            # 仅查询
    python ptp_domain_test.py --ip 192.168.13.169 --domain 127       # 设置 127 并回读校验
    python ptp_domain_test.py --ip 192.168.13.169 --domain 0,64,127  # 多值依次校验
2. 被测试平台挂载: platform.json 的 "plugins" 登记本文件路径:
    - ptp_domain_query  : 查询当前 domain，产出 {ptp_domain}
    - ptp_domain_set_get: SET -> EFFECTUATE -> 等待 -> GET 回读校验
                          （支持多值、domain 可填 {random_value} 烤机）

约束: 平台加载本文件时只做类注册、不执行测试动作（顶层无副作用）。
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime
from typing import Callable, List, Optional, Tuple

import requests

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
DEFAULT_DEVICE_IP = "192.168.13.169"
CGI_PATH = "/fpga_st2110/cgi-bin/smpte2059"

# 命令模板（空格必须编码为 %20，不能用 +；关键字必须下划线写法 DOMAIN_NBR）
CMD_SET_DOMAIN = "SET%20DOMAIN_NBR%20{value}"    # 空格写法 SET DOMAIN NBR v 固件返回 ERROR
CMD_EFFECTUATE = "SET%20EFFECTUATE"               # 重启 ptp4l 使配置生效
CMD_GET_DOMAIN = "GET%20DOMAIN_NBR"

EFFECTUATE_WAIT = 15                    # EFFECTUATE 后等待秒数再复核
DOMAIN_MIN, DOMAIN_MAX = 0, 255         # IEEE 1588 domainNumber 范围；SMPTE 2059 常用 127
OK_MARK = "OK"                          # SET/EFFECTUATE 成功响应标志（RSET ... OK）

# 兼容 "RGET DOMAIN_NBR 127" / "RSET DOMAIN NBR 127"
_DOMAIN_RE = re.compile(r"DOMAIN[_ ]NBR\D*?(\d+)", re.IGNORECASE)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def cgi_request(ip: str, action: str, cgi_path: str = CGI_PATH,
                timeout: int = 10) -> str:
    """发送 CGI 请求，返回原始响应文本（异常返回 "ERROR: ..."）"""
    url = f"http://{ip}{cgi_path}?action={action}"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text.strip()
    except requests.RequestException as e:
        return f"ERROR: {e}"


def parse_domain_number(text: str) -> Optional[int]:
    """从响应文本解析 domain 值；解析失败返回 None"""
    m = _DOMAIN_RE.search(text)
    if m:
        return int(m.group(1))
    m2 = re.search(r"(-?\d+)\s*$", text.strip())  # 兜底：末尾整数
    return int(m2.group(1)) if m2 else None


def query_domain(ip: str, cgi_path: str = CGI_PATH,
                 timeout: int = 10) -> Tuple[str, Optional[int]]:
    """查询当前 domain。返回 (原始响应, 解析值)"""
    text = cgi_request(ip, CMD_GET_DOMAIN, cgi_path, timeout)
    if text.startswith("ERROR"):
        return text, None
    return text, parse_domain_number(text)


def _sleep(sleep_fn, seconds: float) -> bool:
    """优先用注入的可中断等待，否则裸 sleep。返回 False 表示被中断"""
    if sleep_fn is not None:
        return sleep_fn(seconds)
    time.sleep(seconds)
    return True


def set_and_verify(ip: str, value: int, cgi_path: str = CGI_PATH,
                   timeout: int = 10, verify_wait: int = EFFECTUATE_WAIT,
                   retries: int = 2, retry_wait: int = 5,
                   log: Callable[[str], None] = print, sleep_fn=None,
                   stop_check=None) -> Tuple[str, str]:
    """单个 domain 值完整链: SET -> EFFECTUATE -> 等待 -> GET 回读校验。

    SET/EFFECTUATE 响应不回显值，成功标志为 "RSET ... OK"（失败为裸 "ERROR"）；
    值校验依赖 GET 回读。

    :return: (状态, 说明)  状态: PASS / FAIL / STOP
    """
    if stop_check and stop_check():
        return "STOP", "用户停止"

    # 1. SET DOMAIN_NBR <value>
    log(f"SET domain={value} ...")
    text = cgi_request(ip, CMD_SET_DOMAIN.format(value=value), cgi_path, timeout)
    log(f"  SET 响应: {text}")
    if text.startswith("ERROR"):
        return "FAIL", f"SET 请求失败: {text}"
    if OK_MARK not in text.upper():
        return "FAIL", f"SET 响应无 OK 标志: {text}"

    if stop_check and stop_check():
        return "STOP", "用户停止"

    # 2. SET EFFECTUATE（重启 ptp4l 生效）
    log("SET EFFECTUATE（重启 ptp4l）...")
    text = cgi_request(ip, CMD_EFFECTUATE, cgi_path, timeout)
    log(f"  EFFECTUATE 响应: {text}")
    if text.startswith("ERROR"):
        return "FAIL", f"EFFECTUATE 请求失败: {text}"
    if OK_MARK not in text.upper():
        return "FAIL", f"EFFECTUATE 响应无 OK 标志: {text}"

    # 3. 等待生效
    log(f"  等待生效 {verify_wait}s ...")
    _sleep(sleep_fn, verify_wait)

    # 4. GET DOMAIN_NBR 复核
    last_text, got = "", None
    for attempt in range(1, max(1, retries) + 1):
        if stop_check and stop_check():
            return "STOP", "用户停止"
        log(f"[复核 {attempt}/{retries}] GET DOMAIN_NBR ...")
        last_text, got = query_domain(ip, cgi_path, timeout)
        log(f"  GET 响应: {last_text}")
        if got == value:
            return "PASS", f"domain={value} 设置并回读一致 (响应: {last_text})"
        if attempt < retries:
            _sleep(sleep_fn, retry_wait)
    return "FAIL", f"domain 回读不符: 期望 {value}, 实际 {got} (响应: {last_text})"


def parse_domain_list(domain_list: str) -> Tuple[List[int], str]:
    """解析逗号分隔 domain 序列并校验范围。返回 (值列表, 错误信息)"""
    values: List[int] = []
    for raw in str(domain_list).replace("，", ",").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            v = int(raw)
        except ValueError:
            return [], f"非法 domain 值: {raw!r}（需整数）"
        if not (DOMAIN_MIN <= v <= DOMAIN_MAX):
            return [], f"domain 值 {v} 超出范围 [{DOMAIN_MIN}, {DOMAIN_MAX}]"
        values.append(v)
    if not values:
        return [], "domain 序列为空"
    return values, ""


# ============ 测试平台接入（"脚本即插件"） ============
@register
class PtpDomainQueryCase(TestCase):
    """查询当前 PTP domain，产出 {ptp_domain} 供下游引用。"""
    id = "ptp_domain_query"
    name = "PTP Domain 查询"
    category = "PTP"
    description = "CGI 发送 GET DOMAIN_NBR，解析当前 PTP domain；产出 {ptp_domain}"
    params = [
        ParamDef("ip", "设备 IP", DEFAULT_DEVICE_IP, "str", "支持 {device_ip} 引用上游"),
        ParamDef("cgi_path", "CGI 路径", CGI_PATH),
        ParamDef("timeout", "HTTP 超时(秒)", "10", "int"),
        ParamDef("retries", "查询次数(含首次)", "2", "int"),
        ParamDef("retry_wait", "重试间隔(秒)", "3", "int"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        ip = self.p_str("ip")
        cgi_path = self.p_str("cgi_path")
        timeout = self.p_int("timeout", 10)
        retries = max(1, self.p_int("retries", 2))
        wait = self.p_int("retry_wait", 3)

        log(f"目标 {ip}  GET DOMAIN_NBR")
        text, value = "", None
        for attempt in range(1, retries + 1):
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED, "用户停止")
            text, value = query_domain(ip, cgi_path, timeout)
            log(f"[第 {attempt}/{retries} 次] 响应: {text} -> 解析 {value}")
            if value is not None:
                ctx.set("ptp_domain", value)
                ctx.set("ptp_domain_response", text)
                return TestResult(
                    TestStatus.PASSED,
                    f"当前 domain={value} (响应: {text})",
                    data={"ptp_domain": value, "ptp_domain_response": text},
                )
            if attempt < retries and not self.sleep_interruptible(wait, log):
                return TestResult(TestStatus.SKIPPED, "用户停止（重试等待中）")

        return TestResult(
            TestStatus.FAILED,
            f"{retries} 次查询均无法解析 domain，最后响应: {text}",
            data={"ptp_domain": None, "ptp_domain_response": text},
        )


@register
class PtpDomainSetGetCase(TestCase):
    """SET -> EFFECTUATE -> 等待 -> GET 回读校验，支持多值序列与自动恢复。

    典型组合:
    - 单值校验: domain 填 "127"
    - 边界扫描: domain 填 "0,1,126,127,255"
    - 随机烤机: domain 填 "{random_value}"，前置 random_gen + 循环轮数
    """
    id = "ptp_domain_set_get"
    name = "PTP Domain 设置+生效+回读校验"
    category = "PTP"
    description = ("对每个 domain 值执行 SET DOMAIN NBR -> SET EFFECTUATE(重启 ptp4l) "
                   "-> 等待 -> GET DOMAIN_NBR 回读校验；全部通过判 PASS")
    params = [
        ParamDef("ip", "设备 IP", DEFAULT_DEVICE_IP, "str", "支持 {device_ip} 引用上游"),
        ParamDef("domain", "domain 值(逗号分隔)", "127",
                 "str", "如 127 / 0,64,127 / {random_value}"),
        ParamDef("cgi_path", "CGI 路径", CGI_PATH),
        ParamDef("verify_wait", "EFFECTUATE 后等待(秒)", str(EFFECTUATE_WAIT), "int"),
        ParamDef("timeout", "HTTP 超时(秒)", "10", "int"),
        ParamDef("retries", "回读复核次数(含首次)", "2", "int",
                 "ptp4l 重启后可能未就绪，可适当加大"),
        ParamDef("retry_wait", "复核重试间隔(秒)", "5", "int"),
        ParamDef("stop_on_fail", "失败后中止(1/0)", "1", "int",
                 "1=某值失败即停；0=继续测剩余值"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        ip = self.p_str("ip")
        cgi_path = self.p_str("cgi_path")
        timeout = self.p_int("timeout", 10)
        verify_wait = self.p_int("verify_wait", EFFECTUATE_WAIT)
        retries = max(1, self.p_int("retries", 2))
        retry_wait = self.p_int("retry_wait", 5)
        stop_on_fail = self.p_int("stop_on_fail", 1) == 1

        values, err = parse_domain_list(self.p_str("domain"))
        if err:
            return TestResult(TestStatus.FAILED, f"参数错误: {err}")
        log(f"目标 {ip}  待测 domain 序列: {values}")

        def _stop() -> bool:
            return self.stop_requested

        def _sleep(sec: float) -> bool:
            return self.sleep_interruptible(sec, log)

        results = []          # [(value, status, msg)]
        interrupted = False
        for v in values:
            if self.stop_requested:
                interrupted = True
                break
            log(f"----- 测试 domain={v} -----")
            st, msg = set_and_verify(
                ip, v, cgi_path=cgi_path, timeout=timeout,
                verify_wait=verify_wait, retries=retries,
                retry_wait=retry_wait, log=log,
                sleep_fn=_sleep, stop_check=_stop,
            )
            results.append((v, st, msg))
            log(f"  => {st}: {msg}")
            if st == "STOP":
                interrupted = True
                break
            if st == "FAIL" and stop_on_fail:
                break

        if interrupted:
            return TestResult(TestStatus.SKIPPED, "用户停止", data=self._data(results))

        passed = [r for r in results if r[1] == "PASS"]
        failed = [r for r in results if r[1] == "FAIL"]
        data = self._data(results)
        if not failed and len(passed) == len(values):
            ctx.set("ptp_domain", passed[-1][0])
            return TestResult(
                TestStatus.PASSED,
                f"{len(passed)}/{len(values)} 个 domain 值全部回读一致: "
                f"{[v for v, _, _ in results]}",
                data=data,
            )
        summary = "; ".join(f"{v}:{st}({msg})" for v, st, msg in failed)
        return TestResult(
            TestStatus.FAILED,
            f"通过 {len(passed)}/{len(values)}，失败: {summary}",
            data=data,
        )

    @staticmethod
    def _data(results) -> dict:
        return {
            "ptp_domain_results": [{"domain": v, "status": st, "msg": msg}
                                   for v, st, msg in results],
        }


# ============ 独立运行入口 ============
def run_cli(args):
    print("=" * 60)
    print(f"  PTP Domain Test  设备: {args.ip}  开始: {now()}")
    print("=" * 60)

    if args.query:
        text, value = query_domain(args.ip, args.cgi_path, args.timeout)
        print(f"[{now()}] GET 响应: {text} -> 当前 domain={value}")
        sys.exit(0 if value is not None else 1)

    values, err = parse_domain_list(args.domain)
    if err:
        print(f"参数错误: {err}")
        sys.exit(2)

    print(f"[{now()}] 待测序列: {values}")

    ok = 0
    for i, v in enumerate(values, 1):
        print(f"\n----- [{i}/{len(values)}] domain={v} -----")
        st, msg = set_and_verify(args.ip, v, cgi_path=args.cgi_path,
                                 timeout=args.timeout, verify_wait=args.wait)
        print(f"  [{now()}] => {st}: {msg}")
        if st == "PASS":
            ok += 1
        elif st == "FAIL" and not args.keep_going:
            break

    print(f"\n[{now()}] 结束: 通过 {ok}/{len(values)}")
    sys.exit(0 if ok == len(values) else 1)


def main():
    parser = argparse.ArgumentParser(
        description="PTP Domain (SMPTE 2059) 设置/查询测试（CGI 接口）")
    parser.add_argument("--ip", default=DEFAULT_DEVICE_IP,
                        help=f"设备 IP (默认: {DEFAULT_DEVICE_IP})")
    parser.add_argument("--domain", default="127",
                        help="待测 domain 值，逗号分隔 (默认: 127)")
    parser.add_argument("--query", action="store_true", help="仅查询当前 domain")
    parser.add_argument("--wait", type=int, default=EFFECTUATE_WAIT,
                        help=f"EFFECTUATE 后等待秒数 (默认: {EFFECTUATE_WAIT})")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP 超时秒数")
    parser.add_argument("--cgi_path", default=CGI_PATH, help="CGI 路径")
    parser.add_argument("--keep-going", action="store_true",
                        help="某值失败后继续测剩余值")
    run_cli(parser.parse_args())


if __name__ == "__main__":
    main()
