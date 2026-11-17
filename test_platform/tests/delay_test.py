# -*- coding: utf-8 -*-
"""通用延时等待测试项：在测试序列中插入一段可中断的等待。

特点：
- 同一测试项可多次加入队列（如多处需要不同时长的等待），各实例参数独立；
- 等待秒数支持小数，支持 {var} 占位符（如 {random_value} 配合随机数模块
  做随机间隔烤机，占位符在运行前由 Runner 用 Context 当前值替换）；
- 走 sleep_interruptible，点"停止"可在数秒内中断退出。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import (  # noqa: E402
    Context, LogFn, ParamDef, TestCase, TestResult, TestStatus,
)
from core.registry import register  # noqa: E402


@register
class DelayTest(TestCase):
    id = "delay"
    name = "延时等待"
    category = "通用工具"
    description = ("在序列中插入一段等待时间；可多次加入队列，"
                   "各实例参数独立（如重启后等 60s 再检测、检测完再等 300s）")
    params = [
        ParamDef("seconds", "等待秒数", "10", type="float",
                 hint="支持小数与 {var} 占位符（如 {random_value} 随机延时）"),
        ParamDef("reason", "等待原因(备注)", "", type="str",
                 hint="仅用于日志区分，可留空"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        secs = self.p_float("seconds", 0.0)
        if secs <= 0:
            return TestResult(TestStatus.SKIPPED, f"等待秒数无效: {secs!r}")
        why = self.p_str("reason").strip()
        log(f"等待 {secs}s" + (f"（{why}）" if why else ""))
        if self.sleep_interruptible(secs, log):
            return TestResult(TestStatus.PASSED, f"已等待 {secs}s")
        return TestResult(TestStatus.SKIPPED, "用户中断")
