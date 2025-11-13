#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

import json # Cần import json
from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()
        
        # Gán connaddr cho request để start_chat_server.py có thể lấy IP
        self.request.connaddr = connaddr 

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.
        """

        self.conn = conn        
        self.connaddr = addr
        req = self.request
        resp = self.response

        # --- SỬA LỖI ĐỌC BUFFER TCP ---
        try:
            # 1. Đọc phần header trước (giả định header không quá 4096 bytes)
            header_data = b""
            while b'\r\n\r\n' not in header_data:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                header_data += chunk
            
            if not header_data:
                print(f"Client {addr} disconnected before sending headers.")
                return 
            
            # 2. Tách header và phần body (có thể đã đọc lố)
            parts = header_data.split(b'\r\n\r\n', 1)
            header_text = parts[0].decode('utf-8')
            body_bytes = parts[1] if len(parts) > 1 else b""

            # 3. Phân tích header để tìm Content-Length
            headers_dict = {}
            for line in header_text.split('\r\n')[1:]: # Bỏ dòng đầu (POST /... HTTP/1.1)
                if ': ' in line:
                    key, val = line.split(': ', 1)
                    headers_dict[key.lower()] = val
            
            content_length = int(headers_dict.get('content-length', 0))

            # 4. Đọc phần body còn lại (nếu có)
            while len(body_bytes) < content_length:
                bytes_to_read = content_length - len(body_bytes)
                chunk = conn.recv(min(bytes_to_read, 4096)) # Đọc phần còn thiếu
                if not chunk:
                    print(f"Client {addr} disconnected before sending full body.")
                    break # Client ngắt kết nối
                body_bytes += chunk
                
            # msg = Toàn bộ request
            msg = header_text + '\r\n\r\n' + body_bytes.decode('utf-8')

        except Exception as e:
            print(f"Error receiving full request data from {addr}: {e}")
            return
        # --- KẾT THÚC SỬA LỖI ĐỌC BUFFER ---

        req.prepare(msg, routes)

        response = None # Khởi tạo response

        # --- BẮT ĐẦU LOGIC TASK 1A & 1B (Theo PDF) ---

        # Task 1A: Xử lý POST /login
        if req.method == 'POST' and req.path == '/login':
            form_data = {}
            if req.body:
                pairs = req.body.split('&')
                for pair in pairs:
                    if '=' in pair:
                        key, val = pair.split('=', 1) 
                        form_data[key] = val 
            
            username = form_data.get('username')
            password = form_data.get('password')

            if username == 'admin' and password == 'password':
                print("[HttpAdapter] Login successful for admin")
                req.path = '/index.html' 
                resp.set_cookie = 'auth=true; Path=/' 
                response = resp.build_response(req) # Xây dựng response ngay
            else:
                print(f"[HttpAdapter] Login failed for user: {username}")
                response = resp.build_unauthorized()
        
        # Task 1B: Xử lý GET (kiểm tra cookie)
        elif req.method == 'GET':
            if req.path == '/login.html':
                print(f"[HttpAdapter] Serving public asset: {req.path}")
                response = resp.build_response(req)
            
            else: # Bao gồm /index.html, /css/*, /images/*
                if req.cookies.get('auth') == 'true':
                    print(f"[HttpAdapter] Auth cookie valid, serving: {req.path}")
                    response = resp.build_response(req)
                else:
                    print(f"[HttpAdapter] Auth cookie invalid/missing, serving 401 for: {req.path}")
                    response = resp.build_unauthorized()
        
        # --- KẾT THÚC LOGIC TASK 1 ---

        # Handle request hook (Task 2 - WeApRous)
        if req.hook:
            if response is None: 
                print(f"[HttpAdapter] hook in route-path METHOD {req.hook._route_path} PATH {req.hook._route_methods}")
                
                try:
                    handler_result_dict = req.hook(request=req, response=resp)
                except TypeError: 
                    try:
                        handler_result_dict = req.hook(headers=req.headers, body=req.body)
                    except Exception as e:
                         print(f"[HttpAdapter] Error executing hook (headers, body): {e}")
                         handler_result_dict = {"status": "error", "message": f"Hook execution error: {e}"}
                         resp.status_code = 500
                         resp.reason = "Internal Server Error"
                except Exception as e:
                    print(f"[HttpAdapter] Error executing hook (request, response): {e}")
                    handler_result_dict = {"status": "error", "message": f"Hook execution error: {e}"}
                    resp.status_code = 500
                    resp.reason = "Internal Server Error"

                # Xử lý kết quả trả về từ hook
                try:
                    json_body = json.dumps(handler_result_dict).encode('utf-8') 
                    
                    if resp.status_code is None: 
                        resp.status_code = 200
                        resp.reason = "OK"
                        
                    resp.headers['Content-Type'] = 'application/json' 
                    resp._content = json_body
                        
                    resp._header = resp.build_response_header(req)
                    response = resp._header + resp._content
                    
                except Exception as e:
                    print(f"[HttpAdapter] Error serializing hook response: {e}")
                    resp.status_code = 500
                    resp.reason = "Internal Server Error"
                    resp.headers['Content-Type'] = 'application/json'
                    error_payload = json.dumps({"status": "error", "message": str(e)})
                    resp._content = error_payload.encode('utf-8')
                    resp._header = resp.build_response_header(req)
                    response = resp._header + resp._content

        if response is None:
            response = resp.build_response(req)

        conn.sendall(response)

    @property
    def extract_cookies(self, req, resp):
        cookies = {}
        headers = req.headers 
        cookie_str = headers.get("cookie", "") 
        if cookie_str:
            for pair in cookie_str.split(";"):
                try:
                    key, value = pair.strip().split("=")
                    cookies[key] = value
                except ValueError:
                    pass 
        return cookies

    def build_response(self, req, resp):
        response = Response()
        response.raw = resp

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        response.cookies = self.extract_cookies(req, resp)
        response.request = req
        response.connection = self

        return response

    def add_headers(self, request):
        pass

    def build_proxy_headers(self, proxy):
        headers = {}
        username, password = ("user1", "password")

        if username:
            headers["Proxy-Authorization"] = (username, password)

        return headers