#!/usr/bin/env python3
# revprox.py — 反向代理 BMD -> VX90S nmosd
# 作用：补齐 Content-Length（nmosd 缺失），并把 self/base URL 改写为本代理地址
# 用法：在虚拟节点机器（192.168.17.166）上运行，先停掉原 8090 服务
#   python revprox.py > revprox.log 2>&1
# 然后重启 BMD（或等它重扫），观察是否完整枚举出 VX90S 的 senders

import http.server
import re
import urllib.error
import urllib.request

UP = "http://192.168.17.80:8001"    # nmosd 真实地址
MY = "http://192.168.17.166:8090"   # 本代理对外地址（BMD 看到的）
LISTEN_ADDR = "0.0.0.0"
LISTEN_PORT = 8090

# 透传上游的这些响应头（CORS 对浏览器里的 BMD 必须）
PASS_HEADERS = ("Content-Type", "Access-Control-Allow-Origin",
                "Access-Control-Allow-Methods", "Access-Control-Allow-Headers",
                "Access-Control-Max-Age")

# VX90S audio source 的 grain_rate 块（含前导逗号，LF换行，与上游字节精确一致）
AUDIO_GRAIN = (b',\n\t"grain_rate":\t{\n\t\t"numerator":\t48000,'
               b'\n\t\t"denominator":\t1\n\t}')


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    # 对 BMD 用 HTTP/1.1 应答，且必带 Content-Length
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        try:
            req = urllib.request.Request(UP + self.path, method="GET")
            resp = urllib.request.urlopen(req, timeout=5)
            body = resp.read()
            code = resp.getcode()  # py3.8: 无 .status
            headers = resp.headers
        except urllib.error.HTTPError as e:
            # 上游 404/405 等原样透传，不能变 502
            body = e.read()
            code = e.code
            headers = e.headers
        except Exception as e:
            self.send_error(502, str(e))
            print("[PROXY] ERROR %s: %s" % (self.path, e), flush=True)
            return

        # 把资源里的真实地址改写为代理地址，防止 BMD 跟随 href 绕过代理
        body = body.replace(UP.encode(), MY.encode())

        # 修复2：删掉 audio source 的 grain_rate 48000/1（卡 sources 实锤根因）
        if "/sources" in self.path and AUDIO_GRAIN in body:
            body = body.replace(AUDIO_GRAIN, b"")
            print("[PROXY] FIX: removed audio grain_rate 48000/1", flush=True)

        # 修复3(实验A)：删掉 audio 的 channels 数组（通过版 17.166 无此字段）
        if "/sources" in self.path:
            body2 = re.sub(rb',\n\t"channels":\s*\[.*?\]', b"", body, flags=re.S)
            if body2 != body:
                body = body2
                print("[PROXY] FIX-A: removed audio channels", flush=True)
        self.send_response(code)
        for h in PASS_HEADERS:
            v = headers.get(h)
            if v:
                self.send_header(h, v)
        if "Access-Control-Allow-Origin" not in headers:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        cli = self.client_address[0]
        ua = self.headers.get("User-Agent", "?")
        print("[PROXY] %s:%s (%s) GET %s -> %d %d bytes"
              % (cli, self.client_address[1], ua, self.path, code, len(body)),
              flush=True)

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, fmt, *args):
        pass  # 用上面自定义打印


if __name__ == "__main__":
    print("reverse proxy %s -> %s, listen %s:%d" % (MY, UP, LISTEN_ADDR, LISTEN_PORT), flush=True)
    http.server.ThreadingHTTPServer((LISTEN_ADDR, LISTEN_PORT), ProxyHandler).serve_forever()
