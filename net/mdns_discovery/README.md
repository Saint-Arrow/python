# mDNS 服务发现与主机名解析 Demo（基于 zeroconf）

使用 [python-zeroconf](https://github.com/python-zeroconf/python-zeroconf) 实现两个核心功能：

1. **服务发现（Service Discovery）**：监听局域网内的 mDNS / DNS-SD 广播，自动发现设备公布的服务（如 `_http._tcp.local.`、`_ipp._tcp.local.`、`_airplay._tcp.local.`、`_ndi._tcp.local.` 等），并打印服务名、主机名、端口、IP 地址与 TXT 属性。
2. **主机名解析**：将 `xxx.local` 形式的主机名通过多播 DNS 解析为 IPv4 / IPv6 地址。

## 环境准备

```bash
pip install -r requirements.txt
```

> 需要 Python 3.7+，且所在网络允许 mDNS 多播（UDP 5353，224.0.0.251 / ff02::fb）。
> Windows 防火墙可能会拦截多播，必要时允许 Python 通过防火墙。

## 运行

```bash
# 默认监听全部已注册服务类型，持续 30 秒
python mdns_discovery.py

# 只监听指定服务类型，持续 15 秒，并顺带解析某个主机名
python mdns_discovery.py --service _http._tcp.local. --resolve myhost.local --duration 15

# 只解析主机名（不打印服务发现）
python mdns_discovery.py --resolve myhost.local --duration 0

# 开启 zeroconf 详细日志
python mdns_discovery.py --verbose
```

## 参数说明

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--service` | 无（监听全部） | 要监听的服务类型，例如 `_http._tcp.local.` |
| `--resolve` | 无 | 要解析的主机名，例如 `myhost.local`（可省略 `.local`） |
| `--duration` | `30` | 服务发现持续时间（秒） |
| `--resolve-timeout` | `5.0` | 主机名解析超时时间（秒） |
| `--verbose` | 关闭 | 输出 zeroconf 内部调试日志 |

## 代码结构

- `ServiceListener`：继承 zeroconf 的回调接口，处理服务的 `add` / `update` / `remove` 事件并打印。
- `discover_services(...)`：创建 `Zeroconf` 实例与 `ServiceBrowser`，阻塞指定时长后返回发现结果。
- `_HostnameResolver`：继承 `RecordUpdateListener`，捕获与目标主机名匹配的 `A` / `AAAA` 地址记录，实现 `.local` 主机名解析。
- `resolve_hostname(...)`：主动发送 mDNS 查询包，并等待响应，返回解析到的地址列表。

## 常见问题

- **解析失败 / 找不到服务**：确认目标设备确实开启了 mDNS（如开启「网络发现」、运行了 Avahi / Bonjour 服务），且本机防火墙未拦截 UDP 5353 多播。
- **控制台中文乱码**：脚本已尝试将 stdout/stderr 重配置为 UTF-8；若仍乱码，请使用支持 UTF-8 的终端（如 Windows Terminal）。
