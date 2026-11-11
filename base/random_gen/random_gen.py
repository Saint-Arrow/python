# -*- coding: utf-8 -*-
"""随机数生成器 —— 烤机测试随机值源（"脚本即插件"，一份代码两种用法）

用法 1：单独运行
    python random_gen.py
    python random_gen.py --min 1 --max 100 --count 5 --type float

用法 2：被测试平台挂载
    test_platform/platform.json 的 "plugins" 列表登记本文件路径，
    平台启动时自动 import 本文件，@register 的类即出现在 UI 测试项列表。

烤机组合方式：
    队列 = [随机数生成, <下游测试>]，下游测试参数填 {random_value}，
    平台工具栏"循环轮数"设 N → 每轮循环产生不同的随机参数做老化。

产出（写入 Context，供下游占位符引用）：
    {random_value}   最后一个随机数（count=1 时就是唯一的那个）
    {random_values}  本次生成的全部随机数（逗号分隔字符串，便于整体下发）
"""

import os
import random
import sys

# ---- 独立运行时把 test_platform 根目录加入 sys.path；被平台加载时不触发 ----
if __name__ == "__main__":
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _PLATFORM = os.path.normpath(os.path.join(_HERE, "..", "..", "test_platform"))
    if os.path.isdir(_PLATFORM):
        sys.path.insert(0, _PLATFORM)

from core.base import (  # noqa: E402
    Context, LogFn, ParamDef, TestCase, TestResult, TestStatus,
)
from core.registry import register  # noqa: E402


def gen_random(minimum: float, maximum: float, count: int = 1,
               as_float: bool = False, precision: int = 2,
               unique: bool = False):
    """生成 [minimum, maximum] 内的随机数列表（含两端）。

    - as_float=False：整数，random.randint 语义（含两端）
    - as_float=True ：浮点，random.uniform 后保留 precision 位小数
    - unique=True   ：整数无重复（random.sample），可用数量不足时抛 ValueError；
                      浮点模式下忽略（连续空间去重无意义）
    """
    if minimum > maximum:
        minimum, maximum = maximum, minimum

    if unique and not as_float:
        lo, hi = int(minimum), int(maximum)
        pool = range(lo, hi + 1)
        if count > len(pool):
            raise ValueError(
                f"去重模式下可选值仅 {len(pool)} 个（[{lo},{hi}]），"
                f"不够生成 {count} 个")
        return random.sample(pool, count)

    if as_float:
        return [round(random.uniform(minimum, maximum), precision)
                for _ in range(count)]
    return [random.randint(int(minimum), int(maximum)) for _ in range(count)]


@register
class RandomGenCase(TestCase):
    id = "random_gen"
    name = "随机数生成"
    category = "数据源"
    description = ("生成 [最小值,最大值] 范围内的随机数供下游测试引用 "
                   "（{random_value}），配合循环轮数实现随机参数烤机")
    params = [
        ParamDef("min", "最小值", "0", "float"),
        ParamDef("max", "最大值", "100", "float"),
        ParamDef("count", "生成个数", "1", "int"),
        ParamDef("type", "数值类型(int/float)", "int", "str"),
        ParamDef("precision", "浮点精度(位)", "2", "int",
                 "仅 type=float 时生效"),
        ParamDef("unique", "整数去重(0/1)", "0", "int",
                 "仅 type=int 时生效，范围内数量不足时报错"),
        ParamDef("seed", "随机种子(空=不固定)", "", "str",
                 "填数字可复现同一序列，定位问题时使用"),
    ]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        lo = self.p_float("min", 0.0)
        hi = self.p_float("max", 100.0)
        count = self.p_int("count", 1)
        as_float = self.p_str("type", "int").strip().lower() == "float"
        precision = self.p_int("precision", 2)
        unique = self.p_int("unique", 0) == 1
        seed = self.p_str("seed").strip()

        if count < 1:
            return TestResult(TestStatus.FAILED, f"生成个数须 >= 1，当前 {count}")
        if lo > hi:
            log(f"    提示：最小值({lo}) > 最大值({hi})，已自动交换")
        if unique and as_float:
            log("    提示：float 模式忽略去重")
            unique = False

        if seed:
            try:
                random.seed(int(seed))
                log(f"    随机种子 = {seed}（序列可复现）")
            except ValueError:
                return TestResult(TestStatus.FAILED, f"随机种子须为整数：{seed!r}")
        else:
            random.seed()  # 显式恢复系统熵源，避免上次 seed 残留

        try:
            values = gen_random(lo, hi, count, as_float, precision, unique)
        except ValueError as e:
            return TestResult(TestStatus.FAILED, str(e))

        preview = ", ".join(str(v) for v in values[:10])
        suffix = " ..." if count > 10 else ""
        log(f"    生成 {len(values)} 个：{preview}{suffix}")

        ctx.set("random_value", values[-1])
        ctx.set("random_values", ",".join(str(v) for v in values))
        return TestResult(
            TestStatus.PASSED,
            f"生成 {len(values)} 个随机数，最后一个 = {values[-1]}",
            data={"random_value": values[-1],
                  "random_values": values})


# ---------------- 单独运行入口 ----------------
def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description="随机数生成器（可独立运行，亦可被 test_platform 挂载）")
    ap.add_argument("--min", type=float, default=0, help="最小值（含）")
    ap.add_argument("--max", type=float, default=100, help="最大值（含）")
    ap.add_argument("--count", type=int, default=1, help="生成个数")
    ap.add_argument("--type", choices=["int", "float"], default="int",
                    help="数值类型（默认 int）")
    ap.add_argument("--precision", type=int, default=2, help="浮点精度位")
    ap.add_argument("--unique", action="store_true", help="整数去重")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（复现用）")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
    try:
        values = gen_random(args.min, args.max, args.count,
                            args.type == "float", args.precision, args.unique)
    except ValueError as e:
        print(f"[错误] {e}")
        return
    print(f"[结果] 范围[{args.min}, {args.max}] 类型={args.type} "
          f"个数={args.count}")
    for v in values:
        print(f"    {v}")


if __name__ == "__main__":
    _main()
