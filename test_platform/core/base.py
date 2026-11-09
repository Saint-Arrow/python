# -*- coding: utf-8 -*-
"""测试平台核心抽象：TestCase 基类、Context、TestResult、ParamDef。

设计要点：
- 每个测试项（原独立脚本）实现为 TestCase 子类，只需实现 run()；
- Context 在一次队列运行内共享，测试 A 产出的数据（如 mDNS 发现的 IP）
  可被测试 B 通过参数占位符 {key} 引用，实现"可组合"；
- 参数通过 ParamDef 声明，UI 据此自动生成表单，彻底去掉硬编码 IP。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TestStatus(Enum):
    PENDING = "待运行"
    RUNNING = "运行中"
    PASSED = "通过"
    FAILED = "失败"
    SKIPPED = "跳过"
    ERROR = "异常"


@dataclass
class ParamDef:
    """测试项参数声明，UI 自动渲染为表单字段。"""
    key: str
    label: str
    default: str = ""
    type: str = "str"          # str / int / float
    hint: str = ""             # 界面提示，可写 "支持 {var} 引用上下文"


@dataclass
class TestResult:
    status: TestStatus
    message: str = ""
    duration: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)  # 产出数据，可写入 ctx


LogFn = Callable[[str], None]


class Context:
    """一次队列运行内的共享上下文。

    - ctx.set / ctx.get：测试项之间传递数据
    - ctx.loops / ctx.current_loop：队列级循环信息（老化测试）
    """

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self.current_loop: int = 1   # 从 1 开始
        self.total_loops: int = 1

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._data)


class TestCase:
    """测试项基类。子类声明元信息 + params，实现 run()。

    用法示例::

        @register
        class MyCase(TestCase):
            id = "my_case"
            name = "我的测试"
            category = "分类"
            params = [ParamDef("ip", "设备IP", "192.168.13.168")]

            def run(self, ctx, log):
                log("开始...")
                return TestResult(TestStatus.PASSED, "ok")
    """

    id: str = ""
    name: str = ""
    category: str = "通用"
    description: str = ""
    params: List[ParamDef] = []

    def __init__(self, params: Optional[Dict[str, str]] = None) -> None:
        # 参数值保持字符串（含 {var} 占位符），取用时通过 p_* 方法转换
        self._raw_params: Dict[str, str] = {}
        defaults = {p.key: str(p.default) for p in self.params}
        defaults.update(params or {})
        self._raw_params = defaults
        self._stop_check: Optional[Callable[[], bool]] = None  # 由 Runner 注入

    def set_stop_check(self, fn: Callable[[], bool]) -> None:
        self._stop_check = fn

    @property
    def stop_requested(self) -> bool:
        """用户是否请求停止（配合 sleep_interruptible 实现长等待可中断）。"""
        return bool(self._stop_check and self._stop_check())

    # ---------- 参数取用（占位符已由 Runner 替换为实际值） ----------
    def p_str(self, key: str, fallback: str = "") -> str:
        v = self._raw_params.get(key, fallback)
        return str(v)

    def p_int(self, key: str, fallback: int = 0) -> int:
        try:
            return int(float(self._raw_params.get(key, fallback)))
        except (TypeError, ValueError):
            return fallback

    def p_float(self, key: str, fallback: float = 0.0) -> float:
        try:
            return float(self._raw_params.get(key, fallback))
        except (TypeError, ValueError):
            return fallback

    # ---------- 生命周期 ----------
    def setup(self, ctx: Context, log: LogFn) -> None:
        """可选：运行前准备。抛异常则本项记 ERROR。"""

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        """必须实现：执行测试并返回 TestResult。"""
        raise NotImplementedError

    def teardown(self, ctx: Context, log: LogFn) -> None:
        """可选：清理。即使 run 失败也会执行。"""

    # ---------- 工具 ----------
    def sleep_interruptible(self, seconds: float, log: LogFn = None,
                            stop_check: Optional[Callable[[], bool]] = None,
                            tick: float = 0.5) -> bool:
        """可中断等待：等待期间每 tick 检查一次停止请求。

        默认使用 self.stop_requested（Runner 注入的检查函数）；
        stop_check 可传额外检查函数（传属性值等非可调用对象会被忽略，见
        self.stop_requested / runner.stop_requested 都是 property 返回 bool）。
        返回 True 表示正常等完，False 表示被用户中断。
        """
        import time
        remain = float(seconds)
        last_report = 0.0
        while remain > 0:
            extra = bool(stop_check()) if callable(stop_check) else False
            if self.stop_requested or extra:
                return False
            d = min(tick, remain)
            time.sleep(d)
            remain -= d
            if log is not None and remain > 0:
                whole = int(remain + 0.999)
                if whole != last_report and whole % 5 == 0:  # 每 5 秒报一次
                    log(f"    等待中，剩余 {whole}s ...")
                    last_report = whole
        return True
