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
                #req.path = '/index.html' 
                resp.set_cookie = 'auth=true; Path=/' 
                response = resp.build_login_success()
            else:
                # Không hợp lệ: trả về 401, set lại cookie nếu trc đó đã có
                
                resp.set_cookie = 'auth=false; Path=/'
                print(f"check cookie = ", resp.set_cookie)
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

        # Handle request hook
        if req.hook and response is None:
            #if response is None:
            print(f"[HttpAdapter] hook in route-path METHOD {req.hook._route_path} PATH {req.hook._route_methods}")
            #req.hook(headers = "bksysnet",body = "get in touch")
            #
            # TODO: handle for App hook here
            #
            # --- BẮT ĐẦU HOÀN THÀNH TODO ---
            # Code hook (start_sampleapp.py) không trả về gì.
            # Chúng ta sẽ trả về 1 response 200 OK (text/plain)
            # để báo hiệu hook đã được gọi.
            handler_result_json_str = req.hook(headers=req.headers, body=req.body) 
            
            #Ktra nếu handler trả về 1 chuỗi JSON valid
            if isinstance(handler_result_json_str, str):
                resp.prepare_content_type(mime_type='application/json')
                resp.status_code = 200
                resp.reason = "OK"
                resp._content = handler_result_json_str.encode('utf-8') 
                
                print(f"[HttpAdapter] Serving handler result (JSON) for {req.path}")

                resp._header = resp.build_response_header(req)
                response = resp._header + resp._content
                
            else:
                print(f"[HttpAdapter] ERROR: Handler for {req.path} returned non-string/None type. Serving 500.")
                response = resp.build_internal_error()
            # --- KẾT THÚC HOÀN THÀNH TODO ---
        # Build response
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
        # cookies = {}
        # for header in headers:
        #     if header.startswith("Cookie:"):
        #         cookie_str = header.split(":", 1)[1].strip()
        #         for pair in cookie_str.split(";"):
        #             key, value = pair.strip().split("=")
        #             cookies[key] = value
        # return cookies
    
        cookies = {}
        headers = req.headers # Sửa: Lấy từ req.headers (là 1 dict)
        cookie_str = headers.get("cookie", "") # Dùng .get()
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

    # def get_connection(self, url, proxies=None):
        # """Returns a url connection for the given URL. 

        # :param url: The URL to connect to.
        # :param proxies: (optional) A Requests-style dictionary of proxies used on this request.
        # :rtype: int
        # """

        # proxy = select_proxy(url, proxies)

        # if proxy:
            # proxy = prepend_scheme_if_needed(proxy, "http")
            # proxy_url = parse_url(proxy)
            # if not proxy_url.host:
                # raise InvalidProxyURL(
                    # "Please check proxy URL. It is malformed "
                    # "and could be missing the host."
                # )
            # proxy_manager = self.proxy_manager_for(proxy)
            # conn = proxy_manager.connection_from_url(url)
        # else:
            # # Only scheme should be lower case
            # parsed = urlparse(url)
            # url = parsed.geturl()
            # conn = self.poolmanager.connection_from_url(url)

        # return conn


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