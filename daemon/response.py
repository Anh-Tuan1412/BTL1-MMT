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
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a :class: `Response <Response>` object to manage and persist 
response settings (cookies, auth, proxies), and to construct HTTP responses
based on incoming requests. 

The current version supports MIME type detection, content loading and header formatting
"""
import datetime
import os
import mimetypes
from .dictionary import CaseInsensitiveDict

BASE_DIR = ""

class Response():   
    """The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.

    Instances are generated from a :class:`Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    :class:`Response <Response>` object encapsulates headers, content, 
    status code, cookies, and metadata related to the request-response cycle.
    It is used to construct and serve HTTP responses in a custom web server.

    :attrs status_code (int): HTTP status code (e.g., 200, 404).
    :attrs headers (dict): dictionary of response headers.
    :attrs url (str): url of the response.
    :attrsencoding (str): encoding used for decoding response content.
    :attrs history (list): list of previous Response objects (for redirects).
    :attrs reason (str): textual reason for the status code (e.g., "OK", "Not Found").
    :attrs cookies (CaseInsensitiveDict): response cookies.
    :attrs elapsed (datetime.timedelta): time taken to complete the request.
    :attrs request (PreparedRequest): the original request object.

    Usage::

      >>> import Response
      >>> resp = Response()
      >>> resp.build_response(req)
      >>> resp
      <Response>
    """

    __attrs__ = [
        "_content",
        "_header",
        "status_code",
        "method",
        "headers",
        "url",
        "history",
        "encoding",
        "reason",
        "cookies",
        "elapsed",
        "request",
        "body",
        "reason",
    ]


    def __init__(self, request=None):
        """
        Initializes a new :class:`Response <Response>` object.

        : params request : The originating request object.
        """

        self._content = False
        self._content_consumed = False
        self._next = None

        #: Integer Code of responded HTTP Status, e.g. 404 or 200.
        self.status_code = None

        #: Case-insensitive Dictionary of Response Headers.
        #: For example, ``headers['content-type']`` will return the
        #: value of a ``'Content-Type'`` response header.
        self.headers = {}

        #: URL location of Response.
        self.url = None

        #: Encoding to decode with when accessing response text.
        self.encoding = None

        #: A list of :class:`Response <Response>` objects from
        #: the history of the Request.
        self.history = []

        #: Textual reason of responded HTTP Status, e.g. "Not Found" or "OK".
        self.reason = None

        #: A of Cookies the response headers.
        self.cookies = CaseInsensitiveDict()

        #: The amount of time elapsed between sending the request
        self.elapsed = datetime.timedelta(0)

        #: The :class:`PreparedRequest <PreparedRequest>` object to which this
        #: is a response.
        self.request = None

        # Thêm thuộc tính để hỗ trợ Set-Cookie (Task 1A)
        self.set_cookie = None


    def get_mime_type(self, path):
        """
        Determines the MIME type of a file based on its path.

        "params path (str): Path to the file.

        :rtype str: MIME type string (e.g., 'text/html', 'image/png').
        """

        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return 'application/octet-stream'
        if path.endswith('.ico'):
            return 'image/x-icon'
            
        return mime_type or 'application/octet-stream'


    def prepare_content_type(self, mime_type='text/html'):
        """
        Prepares the Content-Type header and determines the base directory
        for serving the file based on its MIME type.

        :params mime_type (str): MIME type of the requested resource.

        :rtype str: Base directory path for locating the resource.

        :raises ValueError: If the MIME type is unsupported.
        """
        
        base_dir = ""

        main_type, sub_type = mime_type.split('/', 1)
        print("[Response] processing MIME main_type={} sub_type={}".format(main_type,sub_type))
        if main_type == 'text':
            self.headers['Content-Type']='text/{}'.format(sub_type)
            if sub_type in ('plain', 'css', 'javascript', 'csv', 'xml'):
                base_dir = os.path.join(BASE_DIR, "static/")
            elif sub_type == 'html':
                base_dir = os.path.join(BASE_DIR, "www/")
            else:
                #handle_text_other(sub_type)
                #pass
                base_dir = os.path.join(BASE_DIR, "static/")

        elif main_type == 'image':
            base_dir = os.path.join(BASE_DIR, "static/")
            self.headers['Content-Type']='image/{}'.format(sub_type)
        #
        #  TODO: process other mime_type
        #        application/xml       
        #        application/zip
        #        ...
        #        text/csv
        #        text/xml
        #        ...
        #        video/mp4 
        #        video/mpeg
        #        ...
        #
        elif main_type in ('audio', 'video'):
            self.headers['Content-Type'] = f"{main_type}/{sub_type}"
            base_dir = os.path.join(BASE_DIR, "static/")
        elif main_type == 'application':
            self.headers['Content-Type'] = f"application/{sub_type}"
            if sub_type in ('json', 'xml', 'zip', 'pdf'):
                base_dir = os.path.join(BASE_DIR, "static/")
            elif sub_type in ('octet-stream', 'x-www-form-urlencoded'):
                base_dir = os.path.join(BASE_DIR, "static/")
            else:
                base_dir = os.path.join(BASE_DIR, "apps/")
        else:
            raise ValueError("Invalid MEME type: main_type={main_type} sub_type={sub_type}")

        if not base_dir.endswith('/'):
            base_dir += '/'
        return base_dir


    def build_content(self, path, base_dir):
        """
        Loads the objects file from storage space.

        :params path (str): relative path to the file.
        :params base_dir (str): base directory where the file is located.

        :rtype tuple: (int, bytes) representing content length and content data.
        """
        # Ngăn chặn Path Traversal
        if path.startswith('/'):
            path = path.lstrip('/')

        # Xử lý path /static/* đúng cách
        # Nếu path đã bắt đầu bằng 'static/', thì dùng trực tiếp từ thư mục gốc
        if path.startswith('static/'):
            # Path đã có 'static/', dùng trực tiếp từ thư mục hiện tại
            # BASE_DIR có thể rỗng, nên dùng path trực tiếp
            if BASE_DIR:
                filepath = os.path.join(BASE_DIR, path)
            else:
                # Nếu BASE_DIR rỗng, dùng path trực tiếp (từ thư mục chạy script)
                filepath = path
        else:
            # Path không có 'static/', dùng base_dir như bình thường
            if BASE_DIR:
                filepath = os.path.join(base_dir, path.lstrip('/'))
            else:
                filepath = os.path.join(base_dir.lstrip('/'), path.lstrip('/'))
        
        # Kiểm tra path traversal
        abs_filepath = os.path.abspath(filepath)
        # Nếu BASE_DIR rỗng, dùng thư mục hiện tại làm base
        if BASE_DIR:
            abs_base = os.path.abspath(BASE_DIR)
        else:
            # Dùng thư mục hiện tại (nơi chạy script) làm base
            abs_base = os.path.abspath(os.getcwd())
        
        # Kiểm tra path traversal - filepath phải nằm trong base directory
        if not abs_filepath.startswith(abs_base):
            print(f"[Response] Path traversal attempt blocked: {path} (filepath: {abs_filepath}, base: {abs_base})")
            return 0, b""
        
        print(f"[Response] serving the object at location {filepath}")
            #
            #  TODO: implement the step of fetch the object file
            #        store in the return value of content
            #
        # --- BẮT ĐẦU HOÀN THÀNH TODO ---
        content = b""
        content_length = 0
        try:
            # Mở file ở chế độ 'rb' (read binary)
            with open(filepath, 'rb') as f:
                content = f.read()
                content_length = len(content)
        except FileNotFoundError:
            print(f"[Response] File not found: {filepath}")
            return 0, b""
        except IOError as e:
            print(f"[Response] Error reading file {filepath}: {e}")
            return 0, b""
            
        return content_length, content
        # --- KẾT THÚC HOÀN THÀNH TODO ---


    def build_response_header(self, request):
        """
        Constructs the HTTP response headers based on the class:`Request <Request>
        and internal attributes.

        :params request (class:`Request <Request>`): incoming request object.

        :rtypes bytes: encoded HTTP response header.
        """
        reqhdr = request.headers
        rsphdr = self.headers

        #Build dynamic headers
        headers = {
                "Accept": "{}".format(reqhdr.get("Accept", "application/json")),
                "Accept-Language": "{}".format(reqhdr.get("Accept-Language", "en-US,en;q=0.9")),
                "Authorization": "{}".format(reqhdr.get("Authorization", "Basic <credentials>")),
                "Cache-Control": "no-cache",
                "Content-Type": "{}".format(self.headers['Content-Type']),
                "Content-Length": "{}".format(len(self._content)),
#                "Cookie": "{}".format(reqhdr.get("Cookie", "sessionid=xyz789")), #dummy cooki
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
                "Date": "{}".format(datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")),
                "Max-Forward": "10",
                "Pragma": "no-cache",
                "Proxy-Authorization": "Basic dXNlcjpwYXNz",  # example base64
                "Warning": "199 Miscellaneous warning",
                "User-Agent": "{}".format(reqhdr.get("User-Agent", "Chrome/123.0.0.0")),
            }
        # --- THÊM LOGIC SET-COOKIE CHO TASK 1A ---
        if self.set_cookie:
            headers["Set-Cookie"] = self.set_cookie
            print(f"[Response] Setting cookie: {self.set_cookie}")
        # --- KẾT THÚC THÊM LOGIC ---

        # Header text alignment
            #
            #  TODO: implement the header building to create formated
            #        header from the provied headers
            #
            # --- BẮT ĐẦU HOÀN THÀNH TODO ---
        # Tạo dòng Status
        status_line = f"HTTP/1.1 {self.status_code} {self.reason}\r\n"
        
        # Tạo các dòng Header
        header_lines = []
        for key, value in headers.items():
            header_lines.append(f"{key}: {value}")
        
        # Kết hợp thành 1 chuỗi header, kết thúc bằng 2 cặp \r\n
        fmt_header = status_line + "\r\n".join(header_lines) + "\r\n\r\n"
        # --- KẾT THÚC HOÀN THÀNH TODO ---
        #
        # TODO prepare the request authentication
        #
	# self.auth = ...
        return str(fmt_header).encode('utf-8')


    def build_notfound(self):
        """
        Constructs a standard 404 Not Found HTTP response.

        :rtype bytes: Encoded 404 response.
        """

        return (
                "HTTP/1.1 404 Not Found\r\n"
                "Accept-Ranges: bytes\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 13\r\n"
                "Cache-Control: max-age=86000\r\n"
                "Connection: close\r\n"
                "\r\n"
                "404 Not Found"
            ).encode('utf-8')

    # --- THÊM HÀM MỚI CHO TASK 1A & 1B ---
    def build_unauthorized(self):
        """
        Constructs a standard 401 Unauthorized HTTP response.
        """
        body = "401 Unauthorized"
        return (
            f"HTTP/1.1 401 Unauthorized\r\n"
            f"Content-Type: text/html\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{body}"
        ).encode('utf-8')
    

    def build_login_success(self):
        # Sử dụng redirect thay vì trả về HTML trực tiếp
        # Điều này đảm bảo cookie được set và URL đúng
        return (
            "HTTP/1.1 302 Found\r\n"
            "Location: /index.html\r\n"
            "Set-Cookie: auth=true; Path=/; SameSite=Lax\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")
    # --- KẾT THÚC THÊM HÀM ---

    def build_response(self, request):
        """
        Builds a full HTTP response including headers and content based on the request.

        :params request (class:`Request <Request>`): incoming request object.

        :rtype bytes: complete HTTP response using prepared headers and content.
        """

        path = request.path

        if path is None:
             return self.build_notfound()
        
        mime_type = self.get_mime_type(path)
        print(f"[Response] {request.method} path {path} mime_type {mime_type}")

        base_dir = ""

        #If HTML, parse and serve embedded objects
        if path.endswith('.html') or mime_type == 'text/html':
            base_dir = self.prepare_content_type(mime_type = 'text/html')
        elif mime_type == 'text/css':
            base_dir = self.prepare_content_type(mime_type = 'text/css')
        #
        # TODO: add support objects
        #
        elif mime_type == 'text/javascript':
            base_dir = self.prepare_content_type(mime_type = 'text/javascript')
        elif mime_type.startswith('image/'):
            base_dir = self.prepare_content_type(mime_type = mime_type)
        else:
            return self.build_notfound()

        c_len, self._content = self.build_content(path, base_dir)

        if c_len == 0 and self._content == b"":
             print(f"[Response] File not found, building 404: {path}")
             return self.build_notfound()
        
        # Nếu file OK, gán 200 OK
        self.status_code = 200
        self.reason = "OK"
        self._header = self.build_response_header(request)

        return self._header + self._content