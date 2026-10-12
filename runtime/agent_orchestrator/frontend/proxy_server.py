#!/usr/bin/env python3
"""
簡單的 CORS 代理服務器
解決前端跨域調用 API 的問題
"""
import json
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError, URLError


class CORSProxyHandler(BaseHTTPRequestHandler):
    API_BASE = 'http://127.0.0.1:8787'

    def do_OPTIONS(self):
        """處理 CORS 預檢請求"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        """處理 GET 請求"""
        if self.path.startswith('/api/'):
            self._proxy_request('GET')
        else:
            # 提供靜態文件
            self._serve_static_file()

    def do_POST(self):
        """處理 POST 請求"""
        if self.path.startswith('/api/'):
            self._proxy_request('POST')
        else:
            self.send_response(404)
            self.end_headers()

    def _set_cors_headers(self):
        """設置 CORS 標頭"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '3600')

    def _proxy_request(self, method):
        """代理 API 請求"""
        try:
            # 構建目標 URL
            target_url = f"{self.API_BASE}{self.path}"

            # 準備請求數據
            if method == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length) if content_length > 0 else None
            else:
                post_data = None

            # 創建請求
            req = urllib.request.Request(target_url, data=post_data, method=method)
            if post_data:
                req.add_header('Content-Type', 'application/json')

            # 發送請求
            with urllib.request.urlopen(req, timeout=30) as response:
                self.send_response(response.getcode())
                self._set_cors_headers()

                # 複製回應標頭
                for header, value in response.headers.items():
                    if header.lower() not in ['access-control-allow-origin', 'access-control-allow-methods']:
                        self.send_header(header, value)

                self.end_headers()

                # 複製回應內容
                self.wfile.write(response.read())

        except (HTTPError, URLError) as e:
            self.send_response(500)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            error_response = {
                'error': 'proxy_error',
                'message': str(e),
                'target_url': f"{self.API_BASE}{self.path}"
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            error_response = {
                'error': 'unexpected_error',
                'message': str(e)
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def _serve_static_file(self):
        """提供靜態文件（主要是 index.html）"""
        if self.path == '/' or self.path == '/index.html':
            try:
                with open('index.html', 'r', encoding='utf-8') as f:
                    content = f.read()

                self.send_response(200)
                self._set_cors_headers()
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content.encode('utf-8'))))
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))

            except FileNotFoundError:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(b'File not found')
        else:
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(b'Not found')

    def log_message(self, format, *args):
        """簡化日誌輸出"""
        print(f"[{self.address_string()}] {format % args}")


def run_proxy_server(port=8789):
    """運行代理服務器"""
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, CORSProxyHandler)

    print(f"""
🔧 CORS 代理服務器啟動！

📍 前端地址: http://127.0.0.1:{port}
🔗 代理目標: http://127.0.0.1:8787
🌐 解決方案: 自動處理 CORS 跨域問題

按 Ctrl+C 停止服務器
""")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服務器已停止")
        httpd.shutdown()


if __name__ == '__main__':
    import os
    import sys

    # 切換到正確的目錄
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    run_proxy_server()