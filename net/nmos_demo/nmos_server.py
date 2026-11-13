#!/usr/bin/env python3
"""
NMOS IS-04 Node API 静态托管（纯 stdlib，Ctrl+C 友好）

等价于 conf/nginx_nmos_node.conf：
  - 监听 8090，root = 同目录 html/
  - v1.0 / v1.1 请求兜底到 v1.2 对应文件（目录不存在，必须回退）
  - 目录默认页 index.json（对应 nginx 的 index index.json + try_files $uri/）
  - 不提供 IS-05（Connection API）

运行：
    cd net/nginx-demo
    python nmos_server.py              # 默认 0.0.0.0:8090
    python nmos_server.py 8080         # 指定端口
Ctrl+C 即可退出（前台 Python 进程，原生支持 KeyboardInterrupt）。

调试：每个请求都会追加写入同目录 access.log（时间|远程IP|请求|UA），
      用于排查"Blackmagic 等控制器到底有没有来 GET、GET 了什么、哪个非 2xx"。
"""

import os
import re
import sys
import mimetypes
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "html")
ACCESS_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "access.log")
_LOG_LOCK = threading.Lock()

# 让 .json / .sdp 返回正确 Content-Type
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("application/sdp", ".sdp")

# 与 nginx 配置一致的版本回退规则
_RE_V01_SELF = re.compile(r"^/x-nmos/node/v1\.[01]/self/?$")
_RE_V01_ANY = re.compile(r"^/x-nmos/node/v1\.[01]/(.*)$")
_RE_V23_SELF = re.compile(r"^/x-nmos/node/(v1\.[23])/self$")


def rewrite(path):
    """返回经 rewrite 处理后的逻辑路径（仍是 URL 形式，用于后续文件系统映射）。"""
    m = _RE_V01_SELF.match(path)
    if m:
        return "/x-nmos/node/v1.2/self/index.json"
    m = _RE_V01_ANY.match(path)
    if m:
        return "/x-nmos/node/v1.2/" + m.group(1)
    m = _RE_V23_SELF.match(path)
    if m:
        return "/x-nmos/node/%s/self/index.json" % m.group(1)
    return path


class NmosHandler(SimpleHTTPRequestHandler):
    def _add_cors(self):
        # 对齐 nmos-cpp(qx) 的响应头，避免 BMD Converters Setup(Web 技术栈)
        # 的跨域 XHR 被浏览器同源策略拦截响应体
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers",
                         "Content-Length, Server-Timing, Timing-Allow-Origin, Vary")
        self.send_header("Timing-Allow-Origin", "*")
        self.send_header("Vary", "Accept")
        self.send_header("Server-Timing", "proc;dur=0.0")

    def end_headers(self):
        self._add_cors()
        super().end_headers()

    def do_OPTIONS(self):
        # 跨域预检：返回 204 + CORS 头
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, Authorization, Accept")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def translate_path(self, path):
        return super().translate_path(rewrite(path))

    def guess_type(self, path):
        # 显式保证 .sdp / .json 的 Content-Type（部分 Python 版 mimetypes 不可靠）
        if path.endswith(".sdp"):
            return "application/sdp"
        if path.endswith(".json"):
            return "application/json"
        return super().guess_type(path)

    def do_GET(self):
        # 目录请求：若含 index.json 则直接返回它（复刻 nginx index index.json）
        fs_path = self.translate_path(self.path)
        if os.path.isdir(fs_path):
            idx = os.path.join(fs_path, "index.json")
            if os.path.isfile(idx):
                rel = os.path.relpath(idx, ROOT).replace(os.sep, "/")
                self.path = "/" + rel
                return super().do_GET()
        return super().do_GET()

    def log_message(self, fmt, *args):
        try:
            line = fmt % args
        except Exception:
            line = str(args)
        ua = self.headers.get("User-Agent", "-")
        ts = self.log_date_time_string()
        rec = "%s | %s | %s | UA=%s\n" % (ts, self.address_string(), line, ua)
        with _LOG_LOCK:
            try:
                with open(ACCESS_LOG, "a", encoding="utf-8") as f:
                    f.write(rec)
            except Exception:
                pass
        sys.stdout.write(rec)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    srv = ThreadingHTTPServer(("0.0.0.0", port), NmosHandler)
    print("NMOS static server: http://0.0.0.0:%d/  root=%s" % (port, ROOT))
    print("Access log -> %s" % ACCESS_LOG)
    print("Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nCaught Ctrl+C, shutting down...")
    finally:
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    main()
