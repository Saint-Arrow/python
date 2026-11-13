# NMOS 虚拟节点被 Blackmagic Converters Setup 发现的调试记录

> 记录时间：2026-11-13
> 环境：虚拟 NMOS 节点 192.168.17.166:8090 / Registry(ConductIP) 192.168.17.68:8235 / Blackmagic Converters Setup 192.168.17.62
> 目标：让一个纯静态的虚拟 NMOS sender 节点在 Blackmagic Converters Setup 中被发现、显示。

---

## 1. 环境拓扑与资源 ID

| 角色 | 地址 | 说明 |
|------|------|------|
| 虚拟 Node API | 192.168.17.166:8090 | 本机静态资源树（`html/`）|
| Registry / ConductIP | 192.168.17.68:8235 | IS-04 注册与 Query |
| Blackmagic Converters Setup | 192.168.17.62 | 待发现端的控制器（验证方）|
| 真机样本 | 192.168.17.167 等 | qx / UpDownCross 12G，用于字段对照 |

| 资源 | ID |
|------|-----|
| node | `6e2a9f10-3b4c-4d5e-8f90-a1b2c3d4e5f6` |
| device | `7f3b8a20-4c5d-4e6f-9a01-b2c3d4e5f6a7` |
| sender | `ac6e1d50-7f8a-4b9c-8d34-e5f6a7b8c9da` |
| flow | `9b5d0c40-6e7f-4a8b-9c23-d4e5f6a7b8c9` |
| source | `8a4c9b30-5d6e-4f7a-8b12-c3d4e5f6a7b8` |

---

## 2. 让设备显示出来的最终修复（逐项）

| # | 修复项 | 要点 |
|---|--------|------|
| 1 | mDNS 广播 host 名 | 与 `self.hostname` 一致（如 `vhd-166.local.`），无旧名残留 |
| 2 | Node API 字段对齐真机 | `self`(hostname/interfaces)、`senders`(transport=`urn:x-nmos:transport:rtp.mcast`、interface_bindings) 对齐 qx 结构 |
| 3 | **完整资源链注册** | 必须注册 `node → device → source → flow → sender` 全套 |
| 4 | **flow 强制字段** | video flow 必须有 `media_type`(`video/raw`)、`bit_depth`、`components`(Y/Cb/Cr) |
| 5 | **全资源心跳** | node/device/flow/source/sender 各自发心跳 |
| 6 | 注册用完整文档 | 注册时 `GET /flows/<id>/` 取完整对象，别用列表摘要 |

---

## 3. 发现设备 Checklist

| # | 项 | 是否必需（实机验证后结论）|
|---|----|------|
| 1 | mDNS 广播 host 名与 `self.hostname` 一致 | ❌ 非必需（见 E1）|
| 2 | Node API 字段对齐真机/qx | ❌ 非必需（见 E2）|
| 3 | 完整资源链注册（含 source/flow）| ✅ **必需**（见 E4/E3）|
| 4 | flow 强制字段完整（media_type 等）| ❌ 非必需（见 E6）|
| 5 | 全资源心跳 | ⚠️ 待 E5 重做确认（机制表明其维持 registry 资源存活，预期为间接必需）|
| 6 | 注册用完整文档（非列表摘要）| ✅ 必需（否则 flow schema 失败）|

---

## 4. 回退实验（每个均经 Blackmagic 实机确认）

> 方法：每次撤销一项修复 → 重启服务 → 请用户在 Converters Setup 实机确认设备是否还在 → 还原再做下一项。
> 注：早期曾假设"Converters Setup 通过 17.68 Registry Query API 发现"，后被抓包推翻（见 §5.1）。所有结论以**用户实机确认 + 抓包**为准。

| 实验 | 撤销项 | Blackmagic 实机结果 | 是否关键 |
|------|--------|---------------------|----------|
| **E4/E3** | 不注册 source/flow（制造孤儿 sender）| **消失** | ✅ 关键 |
| **E6** | 注册 flow 但缺 `media_type`/`bit_depth`/`components` | 显示 | ❌ 非关键 |
| **E5** | 心跳只保活 node | 显示 | ❌ 非关键（**保留**，见 §5）|
| **E2** | Node API 字段不对齐真机 | 显示 | ❌ 非关键 |
| **E1** | mDNS `--host` 去掉，广播 host 名 ≠ `self.hostname` | 显示 | ❌ 非关键 |

### 关键推论（E4/E3 vs E6，并结合 §5.1 抓包）
- 抓包证实 Blackmagic **直连 8090 Node API** 读取 self/devices/sources/flows/senders/receivers 结构（UA=BlackmagicDesign）。但 E4/E3（仅改 register 不 POST source/flow，Node API 静态文件本身始终含 flow）仍消失，说明 Blackmagic 显示时**交叉校验 registry 资源链完整性**：要求 `sender.flow_id` 指向的 flow 已在 registry 注册。
- E4/E3：registry 无 flow → 校验失败 → 消失。
- E6：flow 被注册成功（registry 不严校验 media_type 等字段）→ 链完整 → 显示。
- 结论：**硬条件是 registry 中 `sender→flow→source` 链完整可解析**；flow 字段是否完整不影响。读取结构是直连 8090，显示判定依赖 registry 链。

---

## 5. 待确认事项（抓包验证）

### 5.1 Blackmagic 的发现机制（✅ 已通过抓包确认）
重启 Converters Setup 时，nmos_server(8090) 访问日志捕获到来自 **192.168.17.62（UA=BlackmagicDesign）** 的连续请求：
```
13/Nov/2026 10:13:47 | 192.168.17.62 | GET /x-nmos/node/v1.3/self      200 | BlackmagicDesign
13/Nov/2026 10:13:47 | 192.168.17.62 | GET /x-nmos/node/v1.3/devices  200 | BlackmagicDesign
13/Nov/2026 10:13:49 | 192.168.17.62 | GET /x-nmos/node/v1.3/sources  200 | BlackmagicDesign
13/Nov/2026 10:13:51 | 192.168.17.62 | GET /x-nmos/node/v1.3/flows    200 | BlackmagicDesign
13/Nov/2026 10:13:53 | 192.168.17.62 | GET /x-nmos/node/v1.3/senders  200 | BlackmagicDesign
13/Nov/2026 10:13:55 | 192.168.17.62 | GET /x-nmos/node/v1.3/receivers 200 | BlackmagicDesign
```
**结论：Blackmagic 直连 192.168.17.166:8090 的 Node API 读取资源结构**（顺序 self→devices→sources→flows→senders→receivers），并非通过 registry Query API 发现。

但注意：E4/E3（仅停掉 register 对 source/flow 的 POST，Node API 静态文件里 flows/sources 始终存在）仍导致设备消失，说明 Blackmagic **显示时对 registry 资源链做交叉校验**——要求 `sender.flow_id` 指向的 flow 已在 registry 注册。即：
- 读取结构 = 直连 8090 Node API
- 显示判定 = registry 中 sender→flow→source 链完整

> 待补：17.62 是否也访问了 17.68:8235（registry query）用于交叉校验，需看 registry 侧日志或抓包确认。但仅 E4/E3 的消失已足以证明 registry 链完整性是显示前提。

### 5.2 E5 必须重做（重要）
机制已明（§5.1）：Blackmagic 显示依赖 registry 资源链完整。E5 心跳只保活 node → device/flow/source/sender 无心跳 → 必被 registry 超时删除 → 链断裂 → 应消失。先前"仍显示"极可能是 **nmos-cpp health 超时阈值 > 20s，资源尚未被删**（实验等待不足）。
**必须重做 E5**：把等待时间延长到 60s+ 再请用户确认，预期设备消失，从而坐实"全资源心跳为间接必需项"（维持 registry 资源存活）。

---

## 6. 代码/目录改动清单

### 6.1 目录归拢（已完成）
- `net/nginx-demo/html/` → `net/nmos_demo/html/`（37 json + 1 sdp，完整）
- `net/nginx-demo/nmos_server.py` → `net/nmos_demo/nmos_server.py`
- `nmos_all.py` 的 `SERVER_CMD` 与 server 子进程 `cwd` 改为指向 `nmos_demo`（自包含）

### 6.2 修复脚本
- `nmos_register.py`：完整链路注册（node/device/source/flow/sender）+ 全资源心跳 + 逐个拉取完整文档（先列表摘要再 `/<id>/`）
- `html/x-nmos/node/v1.3/flows/.../index.json` 及顶层 `flows/index.json`：补齐 `media_type`/`bit_depth`/`components`
- `nmos_mdns.py`：mDNS 广播 `vhd-166.local.`（与 `self.hostname` 一致）

### 6.3 版本控制
- 已补充 `.gitignore`：`net/nginx-demo/server_out.txt`、`server_err.txt`、`log/`、`net/nmos_demo/diags/`（诊断产物不入库）
- 实验期间的临时脚本（`_exp_stop.ps1`、`_verify.py`）已删除，工作区干净

---

## 7. 当前状态
- `net/nmos_demo/` 已自包含，三件套一键启动（`nmos_all.py`）正常
- 服务运行于完整修复态，设备应在 Converters Setup 正常显示
- **发现机制已确认**（§5.1）：Blackmagic 直连 8090 Node API 读结构 + 交叉校验 registry 资源链
- **待办**：E5 延长等待重做（§5.2），以最终坐实"全资源心跳"的必需性

---

## 8. VX90S 不被 Blackmagic 显示的根因（2026-11-13 闭环）

### 8.1 现象与复现
- VX90S 真机（192.168.17.80:8001）在 Blackmagic 设备列表不显示
- 17.166 逐字节克隆 VX90S 的 self/devices/sources/flows/senders 数据后，**同故障复现**：
  Blackmagic（17.62）对 17.166 的轮询卡死在 `sources` 层——每 2s 重试 GET sources，
  ~20s 后放弃、从 self 重新开始，永远进不到 flows/senders/receivers → 永不显示

### 8.2 二分定位实验（均为单变量、日志实锤）
| sources 内容 | Blackmagic 行为 |
|---|---|
| 仅 video source（grain_rate 30/1） | ✅ 完整链通过 |
| video + audio（channels 8ch + grain_rate 48000/1） | ❌ 卡 sources 层死循环 |
| video + audio（grain_rate 48000/1，去掉 channels） | ❌ 仍卡 sources 层 |
| video + audio（去掉 grain_rate） | ✅ 完整链通过 |
| video + audio（无 grain_rate）+ data source（VX90S 同款） | ✅ 通过，sources 仅 1 次零重试 |

### 8.3 根因
**audio source 的 `grain_rate: {"numerator": 48000, "denominator": 1}` 字段触发
Blackmagic 发现流程在 sources 层死循环**。VX90S 真机 audio source 恰带此字段
（2026-11-13 13:54 抓包 `http://192.168.17.80:8001/x-nmos/node/v1.3/sources/` 证实），
故真机同样卡死、永不显示。

- channels 字段有无不影响（第二行 vs 第三行对照）
- data source（无 grain_rate）完全干净
- video source 的 grain_rate 30/1 正常（Blackmagic 接受视频帧率）
- 规范角度 IS-04 允许 audio source 带 grain_rate=采样率，属 Blackmagic 解析器
  兼容性缺陷；但现实兼容性要求：**面向 BMD 生态时 audio source 应省略 grain_rate**

### 8.4 修复落盘
- `html/x-nmos/node/v1.3/sources/index.json`：audio source（8a4c9b31）已去 grain_rate；
  data source（8a4c9b32）保留；结构 = VX90S 同款 3 sources（video/audio/data）
- 静态服务器无代码改动（`nmos_server.py` 纯托管 html/）
- 验证：2026-11-13 13:57 与 14:00（BMD 重启后冷启动）均完整链
  self→devices→sources→flows→senders→receivers 一次通过，13:57 后 BMD 停止轮询 2.5 分钟（满意态）

### 8.5 对 VX90S 的处置建议
真机 17.80 的数据我们无法修改，两条路：
1. 反馈厂商固件去掉 audio source 的 grain_rate（或至少提供开关）
2. 若需立即接入 BMD 生态，可用本 demo 的 17.166 虚拟节点顶替其 NMOS 身份
   （self 数据即 VX90S 克隆，sender manifest_href 指向真实 SDP）

### 8.6 更新（2026-11-13 晚间）：真机直连实际卡在更前的 self 层
- §8 的克隆实验是在 17.166 正常 Node API（HTTP 带 `Content-Length`）上复现的，因此只暴露了 sources 层故障。真机 17.80 直连时故障更靠前：**self 层就过不去**。
- 实锤方法：在 17.166 上跑反向代理 `revprox.py`，把 BMD 对 8090 的请求转发到 17.80:8001，并**补齐上游缺失的 `Content-Length`**。代理一上线，BMD（17.62）即对同一台 VX90S 走通 `self→devices→sources→flows→senders→receivers`（代理日志落点：源 IP 17.62，UA=BlackmagicDesign）。
- 根因：**VX90S 的 HTTP/1.1 响应既无 `Content-Length` 也无 `chunked`，仅靠 `Connection: close` 关连接界定 body**；严格客户端（BMD）无法判定 body 完整性、直接丢弃响应 → 卡 self。
- 直连抓包证实（2026-11-13）：`HTTP/1.1 200 OK / Connection: close / Content-Type: application/json` 之后**无 Content-Length 头**。

### 8.7 更新（2026-11-13 晚间）：卡 sources 为双因素，非仅 grain_rate
- §8.3「channels 有无不影响」需修正。revprox 直接代理真机数据做单变量二分：
  - 仅删 audio `grain_rate:48000/1`、保留 8ch `channels` → BMD 仍卡 sources ❌
  - 删 `grain_rate` + 删 `channels` 同时 → BMD 走通 ✅
- 故 sources 层 BMD 不接受 = **audio source 的 `grain_rate:48000/1` 与 `channels` 数组均为触发因素**，二者需同时移除方能走通。

### 8.8 VX90S 真机修改清单（提交厂商）
1. **必改 — HTTP 响应补 `Content-Length`**（所有 Node API 响应）：发 body 前写入长度；或改 `keep-alive` + `chunked`。现状 HTTP/1.1+`Connection:close` 无长度界定，BMD 丢响应、卡 self。
2. **必改 — audio source 删除 `grain_rate:{numerator:48000,denominator:1}`**：BMD 当帧率解析 48000fps 失败、卡 sources。audio 时序本应由 `flow.sample_rate` 承载，source 层不需要 `grain_rate`。
3. **必改 — audio source 删除 `channels` 数组**（或改为 BMD 接受的 label，如 `1L`/`2R`）：与 grain_rate 同为 sources 层触发因素，二者需同时移除。
4. 无需改动：video source 的 `grain_rate:30/1`、`version`(秒:纳秒)、`clock_name` 等均正常。

### 8.9 临时 workaround（revprox.py）
- `revprox.py`：反向代理 `192.168.17.166:8090 → 192.168.17.80:8001`。对 BMD 应答时补齐 `Content-Length`、透传 CORS，改写资源内真实地址为代理地址，并移除 audio 的 `grain_rate`/`channels`。
- 用途：厂商修复前，让 BMD 临时枚举 VX90S 真机（self→…→senders）。**属 workaround 非生产方案**，厂商按 §8.8 修固件后应移除。
- 运行：`python revprox.py`，配合 mDNS 广播 17.166:8090 供 BMD 发现。

### 8.10 代码状态
- `nmos_server.py` / `nmos_all.py` 的 `no-cl` 复现实验分支已还原（上传版本控制前清理）。`no-cl` 复现能力已被 §8.6 的 revprox 实验取代，逻辑更贴近真机。
