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
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""
import socket
import threading
import itertools # Thêm thư viện để hỗ trợ round-robin
from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

#: A dictionary mapping hostnames to backend IP and port tuples.
#: Used to determine routing targets for incoming requests.
PROXY_PASS = {
    "192.168.56.103:8080": ('192.168.56.103', 9000),
    "app1.local": ('192.168.56.103', 9001),
    "app2.local": ('192.168.56.103', 9002),
}

# Biến toàn cục để lưu trữ vòng lặp round-robin cho các host
round_robin_iterators = {}
rr_lock = threading.Lock()

def forward_request(host, port, request):
    """
    Forwards an HTTP request to a backend server and retrieves the response.

    :params host (str): IP address of the backend server.
    :params port (int): port number of the backend server.
    :params request (str): incoming HTTP request.

    :rtype bytes: Raw HTTP response from the backend server. If the connection
                  fails, returns a 404 Not Found response.
    """

    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        backend.connect((host, port))
        backend.sendall(request.encode())
        response = b""
        while True:
            chunk = backend.recv(4096)
            if not chunk:
                break
            response += chunk
        return response
    except socket.error as e:
      print("Socket error: {}".format(e))
      return (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode('utf-8')


def resolve_routing_policy(hostname, routes):
    """
    Handles an routing policy to return the matching proxy_pass.
    It determines the target backend to forward the request to.

    :params host (str): IP address of the request target server.
    :params port (int): port number of the request target server.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    print(f"[Proxy] Resolving hostname: {hostname}")
    # Lấy (proxy_map, policy) từ routes, nếu không thấy thì dùng default
    proxy_map, policy = routes.get(hostname, (['127.0.0.1:9000'], 'round-robin'))
    
    print(f"[Proxy] Map: {proxy_map}")
    print(f"[Proxy] Policy: {policy}")

    proxy_host = '127.0.0.1'
    proxy_port = '9000'
    
    # proxy_map có thể là 1 list (nhiều server) hoặc 1 string (1 server)
    if isinstance(proxy_map, list):
        if len(proxy_map) == 0:
            print(f"[Proxy] Empty resolved routing for hostname {hostname}")
            # --- BẮT ĐẦU HOÀN THÀNH TODO ---
            proxy_host = '127.0.0.1'
            proxy_port = '9000'
            # --- KẾT THÚC HOÀN THÀNH TODO ---
            
        elif len(proxy_map) == 1:
            # Chỉ có 1 server, dùng server đó
            proxy_host, proxy_port = proxy_map[0].split(":", 1)
            
        else:
            # Có nhiều server, áp dụng policy
            # --- BẮT ĐẦU HOÀN THÀNH TODO (round-robin) ---
            if policy == 'round-robin':
                with rr_lock:
                    if hostname not in round_robin_iterators:
                        # Tạo một vòng lặp vô hạn cho host này
                        round_robin_iterators[hostname] = itertools.cycle(proxy_map)
                    # Lấy server tiếp theo trong vòng lặp
                    next_server = next(round_robin_iterators[hostname])
                proxy_host, proxy_port = next_server.split(":", 1)
                print(f"[Proxy] Round-robin selected: {proxy_host}:{proxy_port}")
            else:
                # Policy khác (hoặc mặc định), cứ lấy cái đầu tiên
                proxy_host, proxy_port = proxy_map[0].split(":", 1)
            # --- KẾT THÚC HOÀN THÀNH TODO ---
            
    else:
        # Trường hợp proxy_map là 1 string đơn
        print(f"[Proxy] Resolve route for hostname {hostname} is singular")
        proxy_host, proxy_port = proxy_map.split(":", 1)

    return proxy_host, proxy_port

def handle_client(ip, port, conn, addr, routes):
    """
    Handles an individual client connection by parsing the request,
    determining the target backend, and forwarding the request.

    The handler extracts the Host header from the request to
    matches the hostname against known routes. In the matching
    condition,it forwards the request to the appropriate backend.

    The handler sends the backend response back to the client or
    returns 404 if the hostname is unreachable or is not recognized.

    :params ip (str): IP address of the proxy server.
    :params port (int): port number of the proxy server.
    :params conn (socket.socket): client connection socket.
    :params addr (tuple): client address (IP, port).
    :params routes (dict): dictionary mapping hostnames and location.
    """

    try:
        request = conn.recv(1024).decode()
        if not request:
            conn.close()
            return
            
    except Exception as e:
        print(f"Error receiving from {addr}: {e}")
        conn.close()
        return

    # Extract hostname
    hostname = ""
    try:
        for line in request.splitlines():
            if line.lower().startswith('host:'):
                hostname = line.split(':', 1)[1].strip()
                break # Tìm thấy host rồi thì dừng
    except IndexError:
        print(f"[Proxy] Malformed request from {addr}, no Host header.")
        
    if not hostname:
        # Nếu không có Host header, ta có thể dùng IP:Port của chính proxy
        # (Giả định từ config file)
        hostname = f"{ip}:{port}" 
        print(f"[Proxy] No Host header, defaulting to proxy address: {hostname}")
    else:
        print(f"[Proxy] Request from {addr} for Host: {hostname}")


    # Resolve the matching destination in routes and need conver port
    # to integer value
    resolved_host, resolved_port = resolve_routing_policy(hostname, routes)
    try:
        resolved_port = int(resolved_port)
    except ValueError:
        print(f"Not a valid integer port: {resolved_port}")
        resolved_port = 9000 # Fallback

    if resolved_host:
        print(f"[Proxy] Host {hostname} is forwarded to {resolved_host}:{resolved_port}")
        response = forward_request(resolved_host, resolved_port, request)        
    else:
        response = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode('utf-8')
        
    try:
        conn.sendall(response)
    except Exception as e:
        print(f"Error sending to {addr}: {e}")
    finally:
        conn.close()

def run_proxy(ip, port, routes):
    """
    Starts the proxy server and listens for incoming connections. 

    The process dinds the proxy server to the specified IP and port.
    In each incomping connection, it accepts the connections and
    spawns a new thread for each client using `handle_client`.
 

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.

    """

    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print(f"[Proxy] Listening on IP {ip} port {port}")
        while True:
            conn, addr = proxy.accept()
            #
            #  TODO: implement the step of the client incomping connection
            #        using multi-thread programming with the
            #        provided handle_client routine
            #
            # --- BẮT ĐẦU HOÀN THÀNH TODO ---
            print(f"[Proxy] Accepted connection from {addr}")
            client_thread = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes)
            )
            client_thread.daemon = True
            client_thread.start()
            # --- KẾT THÚC HOÀN THÀNH TODO ---
            
    except socket.error as e:
      print(f"Socket error: {e}")
    except KeyboardInterrupt:
        print("\n[Proxy] Server shutting down.")
    finally:
        proxy.close()


def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    run_proxy(ip, port, routes)