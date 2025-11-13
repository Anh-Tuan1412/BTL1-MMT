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

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
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

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
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

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        # Handle the request
        try:
            msg = conn.recv(1024).decode()
            if not msg: # Nếu client ngắt kết nối
                return 
        except Exception as e:
            print(f"Error receiving data: {e}")
            return

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
                # Hợp lệ: trả về index.html và set cookie
                print("[HttpAdapter] Login successful for admin")
                # Thay vì gọi build_login_success, chúng ta sửa req.path
                # và để nó tự chạy xuống logic build_response bên dưới
                req.path = '/index.html' 
                resp.set_cookie = 'auth=true; Path=/' 
                response = resp.build_response(req) # Xây dựng response ngay
            else:
                # Không hợp lệ: trả về 401
                print(f"[HttpAdapter] Login failed for user: {username}")
                response = resp.build_unauthorized()
        
        # Task 1B: Xử lý GET (kiểm tra cookie)
        elif req.method == 'GET':
            # Tài nguyên CÔNG KHAI (không cần check cookie)
            # (Trang login.html phải công khai)
            if req.path == '/login.html':
                print(f"[HttpAdapter] Serving public asset: {req.path}")
                response = resp.build_response(req)
            
            # Tài nguyên BẢO VỆ (cần check cookie)
            # PDF nói là "index page" (bao gồm cả css và images của nó)
            else: # Bao gồm /index.html, /css/*, /images/*
                if req.cookies.get('auth') == 'true':
                    # Cookie hợp lệ: Phục vụ trang
                    print(f"[HttpAdapter] Auth cookie valid, serving: {req.path}")
                    response = resp.build_response(req)
                else:
                    # Cookie không hợp lệ: Trả về 401
                    print(f"[HttpAdapter] Auth cookie invalid/missing, serving 401 for: {req.path}")
                    response = resp.build_unauthorized()
        
        # --- KẾT THÚC LOGIC TASK 1 ---

        # Handle request hook (Task 2 - WeApRous)
        if req.hook:
            # Chỉ chạy hook nếu Task 1 không xử lý (response is None)
            if response is None: 
                print(f"[HttpAdapter] hook in route-path METHOD {req.hook._route_path} PATH {req.hook._route_methods}")
                
                # --- BẮT ĐẦU HOÀN THÀNH TODO ---
                # Code hook (start_chat_server.py) dùng signature (request, response)
                # Code hook (start_sampleapp.py) dùng signature (headers, body)
                # Chúng ta cần hỗ trợ cả hai, nhưng ưu tiên (request, response) nếu nó hoạt động
                try:
                    # Thử gọi với (request, response) cho start_chat_server.py
                    # Cần truyền cả req và resp để hàm hook có thể truy cập
                    handler_result_dict = req.hook(request=req, response=resp)
                except TypeError:
                    # Nếu lỗi, thử gọi với (headers, body) cho start_sampleapp.py
                    handler_result_dict = req.hook(headers=req.headers, body=req.body)
                except Exception as e:
                    print(f"[HttpAdapter] Error executing hook: {e}")
                    handler_result_dict = {"status": "error", "message": f"Hook execution error: {e}"}
                    resp.status_code = 500
                    resp.reason = "Internal Server Error"

                # Xử lý kết quả trả về từ hook (thường là một dict)
                try:
                    # Chuyển dict (kết quả) thành chuỗi JSON
                    json_body = json.dumps(handler_result_dict).encode('utf-8') 
                    
                    if resp.status_code is None: # Nếu hook không tự set
                        resp.status_code = 200
                        resp.reason = "OK"
                        
                    resp.headers['Content-Type'] = 'application/json' # Rất quan trọng
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
                # --- KẾT THÚC HOÀN THÀNH TODO ---

        # Build response (nếu chưa có response nào được tạo)
        if response is None:
            response = resp.build_response(req)


        #print(response)
        conn.sendall(response)
        #conn.close()

    @property
    def extract_cookies(self, req, resp):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
    
        cookies = {}
        headers = req.headers 
        cookie_str = headers.get("cookie", "") 
        if cookie_str:
            for pair in cookie_str.split(";"):
                try:
                    key, value = pair.strip().split("=")
                    cookies[key] = value
                except ValueError:
                    pass # Bỏ qua cookie lỗi
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object 

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response()

        # Set encoding.
        #response.encoding = get_encoding_from_headers(response.headers)
        response.raw = resp
        #response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        response.cookies = self.extract_cookies(req, resp)

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.

        
        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        username, password = ("user1", "password")

        if username:
            headers["Proxy-Authorization"] = (username, password)

        return headers