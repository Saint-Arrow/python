# Python 测试平台

把散落各处的测试脚本（udp_reboot、reboot_test_hdmi、st2110_synced_test、
telnet_cmd ...）统一成**可勾选、可排序、可组合**的测试平台。

## 快速开始

```powershell
cd test_platform
pip install -r requirements.txt   # PySide6 / zeroconf / requests
python main.py
```

## 架构

```
test_platform/
├── main.py              # 入口
├── core/                # 平台核心（与 UI 无关，可单独 headless 使用）
│   ├── base.py          # TestCase 基类 / Context / TestResult / ParamDef
│   ├── registry.py      # @register + 自动发现（tests/ 包 + platform.json 外部脚本）
│   └── runner.py        # 队列执行引擎（后台线程、循环、失败策略、报告）
├── ui/
│   └── main_window.py   # PySide6 主窗口
├── platform.json        # 外部"脚本即插件"登记（老脚本原地重构、不搬家）
├── logs/                # 运行日志（git 忽略）
├── output/              # 采集产物，如截图（git 忽略）
└── reports/             # 测试报告 report_*.json（git 忽略）
```

## 已接入的测试项

| 测试项 | id | 来源 | 说明 |
|---|---|---|---|
| UDP 指令重启 | `udp_reboot` | `net/udp_reboot_test.py` | 循环发复位/关机指令做重启老化 |
| CGI 接口重启 | `cgi_reboot` | `net/cgi_reboot_test.py` | 循环发 CGI(HTTP) reboot 请求做重启老化（自 st2110_synced_test 抽取，`http_reboot` 亦可作库导入） |
| mDNS 发现/解析 | `mdns_discovery` | `net/mdns_discovery/mdns_discovery.py` | 监听 mDNS 服务广播、解析 xxx.local 为 IP，产出 `{device_ip}` |

待接入的老脚本（原地重构后登记进 `platform.json` 即可）：

- `net/reboot_test_hdmi/hdmi_test.py` — ffmpeg 桌面截图采集
- `net/st2110_synced_test/` — ST2110 reboot 同步性（重启部分已抽出为 `cgi_reboot`，剩 sync 检测主循环）
- telnet 命令执行等

## 核心机制

| 机制 | 说明 |
|---|---|
| 插件化 | 在 `tests/` 下建包放新文件，继承 `TestCase` 并加 `@register` 即自动出现在 UI 左侧 |
| 脚本即插件 | `net/` 下老脚本**原地重构**也能接入：登记进 `platform.json`，单独可跑、平台可挂，一份代码两用 |
| 勾选 | 左侧分类树勾选（或双击）→ "添加所选" 进队列 |
| 排序 | 队列内**拖拽排序**，或上移/下移按钮 |
| 组合 | `run()` 返回的 `TestResult.data` 自动并入 `Context`；后续测试参数填 `{device_ip}` 等占位符即可引用上游产出（运行时才替换） |
| 老化测试 | 工具栏"循环轮数"让整条队列跑 N 遍 |
| 失败策略 | 失败后继续 / 中止整队 |
| 可中断 | 长等待走 `sleep_interruptible`，点停止数秒内退出 |
| 方案 | 队列+参数+轮数保存为 JSON，下次一键复现 |
| 报告 | 每次运行产出 `reports/report_*.json`；日志落盘 `logs/` |

## 组合示例

典型流程（对应原来几个脚本手工接力）：

1. 添加 **mDNS 发现/解析**，hostname 填设备主机名 → 产出 `{device_ip}`
2. 添加 **UDP 指令重启**，参数 `ip` 填 `{device_ip}`（运行时自动替换）
3. 添加 **HDMI 截图采集**（重构接入后），采集重启前后的桌面画面
4. 工具栏"循环轮数"设 50，失败策略"失败后中止" → 运行

## 如何接入一个新脚本

### 方式一：tests/ 包（平台内新建插件）

在 `test_platform/tests/` 下建 `my_case.py`（需保证目录是可导入包）：

```python
# tests/my_case.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import Context, ParamDef, TestCase, TestResult, TestStatus, LogFn
from core.registry import register

@register
class MyCase(TestCase):
    id = "my_case"                 # 唯一
    name = "我的测试"               # UI 显示名
    category = "稳定性"             # UI 分组
    description = "一句话说明"
    params = [ParamDef("ip", "设备IP", "192.168.13.168", hint="支持 {device_ip}")]

    def run(self, ctx: Context, log: LogFn) -> TestResult:
        log("开始...")             # log 会同步打到 UI 与文件
        if not self.sleep_interruptible(60, log, self.stop_requested):
            return TestResult(TestStatus.SKIPPED, "用户中断")
        ctx.set("my_output", 123)  # 可选：给下游测试用
        return TestResult(TestStatus.PASSED, "ok", data={"my_output": 123})
```

保存后重启平台即可见，无需改任何平台代码。

### 方式二：老脚本原地重构（"脚本即插件"，当前主用）

不改路径、不搬家，且单独仍可 `python xxx.py` 直接跑。参考模板 `net/udp_reboot_test.py`：

1. 顶层执行代码（while 循环等）全部搬进 `run()` / `_main()`，模块级只留定义；
2. 文件底部保留 `if __name__ == "__main__":` 独立运行入口；
3. 平台侧 import 路径处理（`sys.path` 加入 `test_platform` 根目录）+ `@register` 注册类；
4. 在 `platform.json` 的 `"plugins"` 里登记该文件相对路径。

## Headless（无 UI 跑队列）

```python
from core import discover_from_config, QueueItem, QueueRunner
discover_from_config()   # 加载 platform.json 登记的外部插件
QueueRunner(
    queue=[QueueItem("udp_reboot", params={"ip": "192.168.13.169", "rounds": 3})],
    loops=10,
).start()   # 需自行 join / 等待
```
