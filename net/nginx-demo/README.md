# nginx 反向代理（精简版）

基于 nginx-rtmp-win32 (nginx 1.10.1) 精简而来，仅保留 `nginx.exe` 和一份最小反向代理配置，RTMP/HLS/播放器等无关内容已全部移除。

## 用途

将本机 `8095` 端口反向代理到 `http://192.168.21.191:8095/`：

```
http://localhost:8095/  -->  http://192.168.21.191:8095/
```

## 目录结构（最小文件集）

```
nginx-st2110-license/
├── nginx.exe          # 可执行文件
├── conf/nginx.conf    # 唯一配置（纯反向代理）
├── logs/              # 运行时生成：error.log / access.log / nginx.pid
└── temp/              # 启动时自动创建（proxy 缓存用）
```

## 使用方法

```powershell
cd net/nginx-st2110-license
start nginx              # 启动（或直接双击 nginx.exe）
nginx -s reload          # 修改配置后重载
nginx -s stop            # 停止
nginx -t                 # 检查配置语法
```

## 配置说明（conf/nginx.conf）

- `listen 8095`：本地监听端口，与后端同端口，访问 `http://localhost:8095/` 即可
- `proxy_pass http://192.168.21.191:8095`：后端地址，换目标时改这一行
- `Host / X-Real-IP / X-Forwarded-*`：透传客户端信息，保证后端虚拟主机/鉴权正常
- HTTP/1.1 keepalive + 3600s 长超时：兼容长连接/API 场景

## 来源

原始发行版：nginx-rtmp-win32

- Nginx: 1.10.1
- Nginx-Rtmp-Module: 1.1.7（已编译在 exe 内，当前配置未启用）
- openssl-1.0.2h / pcre-8.38 / zlib-1.2.8

原始 README 与完整配置见项目主页：https://github.com/NodeMedia/nginx-rtmp-win32（www 播放器、1935 RTMP、8080 HTTP 等已删除）
