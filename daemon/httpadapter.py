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

import json 
from .request import Request, read_full_http_request
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

        try:
            msg = read_full_http_request(conn=conn)
            if not msg:
                print(f"Error receiving full request data from {addr}")
                conn.close()
                return
        except Exception as e:
            print(f"Error receiving full request data from {addr}: {e}")
            return
      
        has_xff = False
        for line in msg.split('\r\n'):
            if line.lower().startswith('x-forwarded-for:'):
                has_xff = True
                break
    
        if not has_xff:
            parts = msg.split('\r\n\r\n', 1)
            header_section = parts[0]
            body_section = parts[1] if len(parts) > 1 else ""
        
            lines = header_section.split('\r\n')
            request_line = lines[0]
            other_headers = lines[1:]
        
            new_headers = [request_line, f"X-Forwarded-For: {addr[0]}"] + other_headers
            msg = '\r\n'.join(new_headers) + '\r\n\r\n' + body_section
            #print(f"[HttpAdapter] Added X-Forwarded-For: {addr[0]}")

        #print(f"[HTTPAdapter] DEBUG: {msg}")
        req.prepare(msg, routes)
        response = None 

        if req.hook:
            print(f"[HttpAdapter] hook in route-path METHOD {req.hook._route_path} PATH {req.hook._route_methods}")
            
            try:
                handler_result = req.hook(request=req, response=resp)
            except TypeError: 
                try:
                    handler_result = req.hook(headers=req.headers, body=req.body)
                except Exception as e:
                     print(f"[HttpAdapter] Error executing hook (headers, body): {e}")
                     handler_result = {"status": "error", "message": f"Hook execution error: {e}"}
                     resp.status_code = 500
                     resp.reason = "Internal Server Error"
            except Exception as e:
                print(f"[HttpAdapter] Error executing hook (request, response): {e}")
                handler_result = {"status": "error", "message": f"Hook execution error: {e}"}
                resp.status_code = 500
                resp.reason = "Internal Server Error"

            # Xử lý kết quả trả về từ hook
            if isinstance(handler_result, str):
                # Nếu hook trả về string đầy đủ response (ví dụ cho /login với Set-Cookie)
                response = handler_result.encode('utf-8')
            else:
                try:
                    json_body = json.dumps(handler_result).encode('utf-8') 
                    
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

        
        # Chỉ xử lý nếu không có hook (tức là static request)
        if response is None:
            if req.method == 'POST' and req.path == '/login':
                form_data = {}
                if req.body:
                    pairs = req.body.split('&')
                    for pair in pairs:
                        if '=' in pair:
                            key, val = pair.split('=', 1) 
                            form_data[key.strip()] = val.strip() 
                
                username = form_data.get('username')
                password = form_data.get('password')
                #print(f"[DEBUG]: {username}, {password}")
                if username == 'admin' and password == 'password':
                    print("[HttpAdapter] Login successful for admin")
                    req.path = '/index.html' 
                    resp.set_cookie = 'auth=true; Path=/' 
                    response = resp.build_response(req) 
                else:
                    print(f"[HttpAdapter] Login failed for user: {username}")
                    response = resp.build_unauthorized()
            

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