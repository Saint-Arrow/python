# -*- coding: utf-8 -*-
"""队列执行引擎：在后台线程顺序执行勾选的测试项，通过回调通知 UI。

特性：
- 队列级循环（老化测试：整条队列跑 N 遍）
- 失败策略：继续 / 中止整队
- 参数占位符 {key} 在每项运行前用 Context 当前值替换（延迟替换，
  保证引用的是上一步刚产出的数据）
- 运行结束生成 JSON 报告；汇总/报告按"逐次执行记录"累计所有轮次，
  多轮循环不会只统计最后一轮（executions 字段含全部明细）
"""

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from .base import Context, TestCase, TestResult, TestStatus
from . import registry

# ---------------- 回调签名 ----------------
# on_log(line: str)
LogCallback = Callable[[str], None]
# on_item_status(item_index: int, loop: int, status: TestStatus, message: str, duration: float)
StatusCallback = Callable[[int, int, TestStatus, str, float], None]
# on_all_done(summary: dict)
DoneCallback = Callable[[dict], None]

FAIL_CONTINUE = "continue"
FAIL_ABORT = "abort"

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@dataclass
class QueueItem:
    """队列中的一个待运行项（测试项 id + 参数）。"""
    case_id: str
    name: str = ""
    params: Dict[str, str] = field(default_factory=dict)
    # 运行期状态
    status: TestStatus = TestStatus.PENDING
    message: str = ""
    duration: float = 0.0

    def to_dict(self) -> dict:
        return {"case_id": self.case_id, "name": self.name,
                "params": dict(self.params)}

    @staticmethod
    def from_dict(d: dict) -> "QueueItem":
        return QueueItem(case_id=d["case_id"], name=d.get("name", ""),
                         params=d.get("params", {}))


class QueueRunner(threading.Thread):
    """后台执行线程。UI 调 start() 后通过回调收日志与状态。"""

    def __init__(self, queue: List[QueueItem], loops: int = 1,
                 fail_policy: str = FAIL_ABORT,
                 on_log: Optional[LogCallback] = None,
                 on_item_status: Optional[StatusCallback] = None,
                 on_done: Optional[DoneCallback] = None,
                 report_dir: str = "reports") -> None:
        super().__init__(daemon=True)
        self.queue = queue
        # 负数（如 -1）= 无限循环，直到失败中止或用户停止；0 视为 1
        self.loops = int(loops)
        if self.loops == 0:
            self.loops = 1
        self.fail_policy = fail_policy
        self.on_log = on_log or (lambda s: None)
        self.on_item_status = on_item_status or (lambda *a: None)
        self.on_done = on_done or (lambda s: None)
        self.report_dir = report_dir

        self._stop_flag = threading.Event()
        self._ctx = Context()
        self._ctx.total_loops = self.loops

    # ---------- 对外控制 ----------
    def request_stop(self) -> None:
        self._stop_flag.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop_flag.is_set()

    # ---------- 内部 ----------
    def _log(self, line: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        try:
            self.on_log(f"[{stamp}] {line}")
        except Exception:  # noqa: BLE001 日志回调异常不得杀死测试线程（如 GBK 控制台打印 ▶）
            pass

    def _resolve_params(self, case: TestCase) -> None:
        """把参数值中的 {var} 占位符替换为 Context 当前值。"""
        for k, v in case._raw_params.items():
            if isinstance(v, str) and "{" in v:
                def sub(m):
                    val = self._ctx.get(m.group(1))
                    return v if val is None else str(val)
                case._raw_params[k] = _PLACEHOLDER.sub(sub, v)

    def run(self) -> None:  # threading.Thread 入口
        # 逐次执行记录：多轮循环时每轮每项各记一条（统计与报告均基于此，
        # 避免 QueueItem.status 单槽被后一轮覆盖导致只统计最后一轮）
        executions: List[dict] = []
        started = time.time()
        loops_txt = "无限循环" if self.loops < 0 else f"{self.loops} 轮"
        self._log(f"========== 队列启动：{len(self.queue)} 项 × {loops_txt}，"
                  f"失败策略={self.fail_policy} ==========")
        aborted = False

        loop = 0
        while not aborted and not self.stop_requested:
            loop += 1
            if self.loops >= 1 and loop > self.loops:
                break
            self._ctx.current_loop = loop
            if self.loops != 1:
                head = (f"第 {loop}/{self.loops} 轮" if self.loops > 1
                        else f"第 {loop} 轮（无限）")
                self._log(f"—————— {head} ——————")

            for idx, item in enumerate(self.queue):
                if self.stop_requested:
                    aborted = True
                    break

                case = registry.create(item.case_id, item.params)
                if case is None:
                    item.status = TestStatus.ERROR
                    item.message = f"未注册的测试项: {item.case_id}"
                    self.on_item_status(idx, loop, item.status, item.message, 0.0)
                    executions.append(
                        {"loop": loop, "index": idx, "case_id": item.case_id,
                         "name": item.name or item.case_id,
                         "status": item.status.value,
                         "message": item.message, "duration": 0.0})
                    continue

                display = case.name or item.name or item.case_id
                self._log(f"▶ [{idx + 1}/{len(self.queue)}] {display} 参数={case._raw_params}")
                item.status = TestStatus.RUNNING
                self.on_item_status(idx, loop, item.status, "", 0.0)

                t0 = time.time()
                result: Optional[TestResult] = None
                try:
                    case.set_stop_check(self._stop_flag.is_set)  # 注意：注入可调用对象，而非 stop_requested 属性的 bool 值
                    case.setup(self._ctx, self._log)
                    # 占位符在 setup 之后、run 之前替换，setup 可先写入 ctx
                    self._resolve_params(case)
                    result = case.run(self._ctx, self._log)
                except Exception as e:  # noqa: BLE001 平台需兜住一切异常
                    result = TestResult(TestStatus.ERROR, f"{type(e).__name__}: {e}")
                finally:
                    try:
                        case.teardown(self._ctx, self._log)
                    except Exception as e:  # noqa: BLE001
                        self._log(f"    teardown 异常: {e}")

                duration = round(time.time() - t0, 2)
                if result is None:
                    result = TestResult(TestStatus.ERROR, "run() 未返回 TestResult")

                item.status = result.status
                item.message = result.message
                item.duration = duration
                # 测试产出数据并入 ctx，供后续测试引用
                for k, v in result.data.items():
                    self._ctx.set(k, v)

                self.on_item_status(idx, loop, item.status, result.message, duration)
                self._log(f"  ◀ {display} -> {result.status.value}"
                          f"（{duration}s）{result.message}")
                executions.append(
                    {"loop": loop, "index": idx, "case_id": item.case_id,
                     "name": display, "status": result.status.value,
                     "message": result.message, "duration": duration})

                if result.status in (TestStatus.FAILED, TestStatus.ERROR):
                    if self.fail_policy == FAIL_ABORT:
                        self._log("失败策略=中止，停止整条队列。")
                        aborted = True
                        break

        total = round(time.time() - started, 2)
        # 统计基于逐次执行记录（所有轮次累计），而非 QueueItem 最后一轮状态
        passed = sum(1 for e in executions
                     if e["status"] == TestStatus.PASSED.value)
        failed = sum(1 for e in executions
                     if e["status"] in (TestStatus.FAILED.value, TestStatus.ERROR.value))
        skipped = sum(1 for e in executions
                      if e["status"] == TestStatus.SKIPPED.value)
        executed_loops = executions[-1]["loop"] if executions else 0
        summary = {
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "total_seconds": total,
            "loops": self.loops,
            "executed_loops": executed_loops,
            "item_count": len(self.queue),
            "total_executions": len(executions),
            "passed_items": passed,
            "failed_items": failed,
            "skipped_items": skipped,
            "aborted": aborted or self.stop_requested,
        }
        self._log(f"========== 队列结束：通过 {passed} / 失败 {failed}"
                  + (f" / 跳过 {skipped}" if skipped else "")
                  + f"，累计 {len(executions)} 次执行 / {executed_loops} 轮"
                  f"，耗时 {total}s ==========")
        self._save_report(summary, executions)
        self.on_done(summary)

    def _save_report(self, summary: dict, executions: List[dict]) -> None:
        try:
            os.makedirs(self.report_dir, exist_ok=True)
            fname = datetime.now().strftime("report_%Y%m%d_%H%M%S.json")
            path = os.path.join(self.report_dir, fname)
            payload = {
                "summary": summary,
                "context": {k: repr(v) for k, v in self._ctx.snapshot().items()},
                # items: 各队列项最后一轮的状态（UI 表格口径）
                "items": [dict(i.to_dict(),
                               status=i.status.value,
                               message=i.message,
                               duration=i.duration)
                          for i in self.queue],
                # executions: 全部轮次的逐次执行明细（多轮烤机统计口径）
                "executions": executions,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self._log(f"报告已保存: {path}")
        except Exception as e:  # noqa: BLE001
            self._log(f"保存报告失败: {e}")
