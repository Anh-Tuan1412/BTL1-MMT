#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the WeApRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""

import json
import argparse
import threading 
from daemon.weaprous import WeApRous
from daemon.dictionary import CaseInsensitiveDict

PORT = 8000  

app = WeApRous()


db_lock = threading.Lock() 

db = {
    "peers": {
        # "username": {"ip": "1.2.3.4", "port": 5001, "channels": ["general"], "last_heartbeat": time.time()}
    },
    "channels": {
        "general": {"description": "Kênh chat chung"},
        "random": {"description": "Kênh chat ngẫu nhiên"}
    }
}
# ------------------------------------------------

def parse_headers(headers):
    """
    Parse headers whether input is raw string or dict (CaseInsensitiveDict).
    Handles both standalone WeApRous mode (string) and integrated HttpAdapter mode (dict).
    """
    header_dict = CaseInsensitiveDict()
    
    if isinstance(headers, str):
        for line in headers.splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                header_dict[key.strip()] = value.strip()
    elif isinstance(headers, (dict, CaseInsensitiveDict)):
        for key, value in headers.items():
            header_dict[key] = value
    else:
        print(f"[Warning] Invalid headers type: {type(headers)}")
    
    return header_dict

def get_cookie(header_dict):
    cookies = header_dict.get('Cookie', '')
    cookie_dict = {}
    for c in cookies.split(';'):
        if '=' in c:
            k, v = c.split('=', 1)
            cookie_dict[k.strip()] = v.strip()
    return cookie_dict

def is_authenticated(headers):
    h = parse_headers(headers)
    c = get_cookie(h)
    return c.get('auth') == 'true'

@app.route('/login', methods=['POST'])
def login(headers="guest", body="anonymous"):
    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.
    """
    print ("[SampleApp] Logging in {} to {}".format(headers, body))

    form = {}
    for part in body.split('&'):
        if '=' in part:
            k, v = part.split('=', 1)
            form[k] = v

    if form.get('username') == 'admin' and form.get('password') == 'password':
        body_json = json.dumps({"status": "success"})
        return f"HTTP/1.1 200 OK\r\nSet-Cookie: auth=true\r\nContent-Type: application/json\r\nContent-Length: {len(body_json)}\r\n\r\n{body_json}"
    else:
        return "HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n"

# API để unregister peer
@app.route('/unregister', methods=['POST'])
def unregister(headers="guest", body="anonymous"):
    if not is_authenticated(headers):
        return "HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n"
    with db_lock:
        try:
            body_data = json.loads(body)
            username = body_data['username']

            if username in db["peers"]:
                del db["peers"][username]
                print(f"[ChatServer] Unregistered Peer: {username}")
                return {"status": "success", "message": f"{username} unregistered"}
            else:
                return {"status": "error", "message": "Username not found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# API 1: Peer đăng ký (Peer registration)
#
@app.route('/submit-info', methods=['POST'])
def submit_info(headers="guest", body="anonymous"):
    if not is_authenticated(headers):
        return "HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n"
    
    with db_lock:
        try:
            body_data = json.loads(body)
            username = body_data['username']
            p2p_port = int(body_data['p2p_port'])
            
            header_dict = parse_headers(headers)
            
            ip = header_dict.get('x-forwarded-for', None) 
            
            if not ip:
                host_header = header_dict.get('host', '')
                if ':' in host_header:
                    ip = host_header.split(':')[0]
                else:
                    ip = host_header or 'unknown'
            
            
            if username in db["peers"]:
                return {"status": "error", "message": "Username đã tồn tại"}

            db["peers"][username] = {"ip": ip, "port": p2p_port, "channels": []}
            print(f"[ChatServer] Đăng ký Peer: {username} tại {ip}:{p2p_port}")
            
            return {"status": "success", "message": f"Chào mừng {username}"}
        except Exception as e:
            print(f"[ChatServer] Error in submit_info: {e}")
            return {"status": "error", "message": str(e)}

# API 2: Lấy danh sách kênh
@app.route('/get-channel-list', methods=['GET'])
def get_channel_list(headers="guest", body="anonymous"):
    if not is_authenticated(headers):
        return "HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n"
    with db_lock: # <-- 3. Khóa tài nguyên (kể cả khi chỉ đọc)
        return {"status": "success", "channels": list(db["channels"].keys())}

# API 3: Tham gia kênh
@app.route('/add-list', methods=['POST'])
def add_list(headers="guest", body="anonymous"):
    if not is_authenticated(headers):
        return "HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n"
    with db_lock: # <-- 3. Khóa tài nguyên
        try:
            body_data = json.loads(body)
            username = body_data['username']
            channel = body_data['channel']

            if username not in db["peers"]:
                return {"status": "error", "message": "Peer chưa đăng ký"}
            if channel not in db["channels"]:
                db["channels"][channel] = {"description": f"Kênh {channel} được tạo tự động"}
                print(f"[ChatServer] Kênh mới được tạo: {channel}")


            if channel not in db["peers"][username]["channels"]:
                db["peers"][username]["channels"].append(channel)
                
            print(f"[ChatServer] Peer {username} tham gia kênh {channel}")
            return {"status": "success", "message": f"{username} đã tham gia {channel}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# API 4: Lấy danh sách peer trong kênh (Peer discovery)
#
@app.route('/get-list', methods=['POST'])
def get_list(headers="guest", body="anonymous"):
    if not is_authenticated(headers):
        return "HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n"
    with db_lock: # <-- 3. Khóa tài nguyên
        try:
            body_data = json.loads(body)
            channel = body_data['channel']
            my_username = body_data['username'] # Để không lấy chính mình

            if channel not in db["channels"]:
                return {"status": "error", "message": "Kênh không tồn tại"}

            peer_list = []
            # Vòng lặp for cũng cần được bảo vệ
            for username, data in db["peers"].items():
                # Nếu peer có trong kênh VÀ không phải là tôi
                if channel in data["channels"] and username != my_username:
                    peer_list.append({
                        "username": username,
                        "ip": data["ip"],
                        "port": data["port"]
                    })
            
            return {"status": "success", "peers": peer_list}
        except Exception as e:
            return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # Parse command-line arguments to configure server IP and port
    parser = argparse.ArgumentParser(prog='Backend', description='', epilog='Beckend daemon')
    parser.add_argument('--server-ip', default='0.0.0.0')
    parser.add_argument('--server-port', type=int, default=PORT)
 
    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()