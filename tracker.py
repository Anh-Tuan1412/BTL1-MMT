#
# WeApRous release
#
# PHIÊN BẢN NÂNG CAO cho Task 2: Tracker Server với Quản lý Kênh và Heartbeat.
#

import json
import socket
import argparse
import time
import threading

from daemon.weaprous import WeApRous

# PORT mặc định cho máy chủ tracker
PORT = 8000
# Thời gian (giây) mà một peer được coi là "chết" nếu không gửi heartbeat
HEARTBEAT_TIMEOUT = 60
# Tần suất (giây) luồng dọn dẹp chạy
REAPER_INTERVAL = 30

# Khởi tạo ứng dụng WeApRous
app = WeApRous()

# ----- TRẠNG THÁI TOÀN CỤC PHỨC TẠP CỦA TRACKER -----

# 1. Cơ sở dữ liệu Peers (thay vì list đơn giản)
#    - Dùng username làm key
#    - Lưu trữ IP, port, và thời gian heartbeat cuối cùng
#    - { "username": {"ip": "1.2.3.4", "port": 9001, "last_heartbeat": 1678886400.0} }
peers_db = {}
peers_lock = threading.Lock()

# 2. Cơ sở dữ liệu Kênh (Channels)
#    - Dùng channel_name làm key
#    - Lưu trữ thông tin người tạo (owner) và danh sách thành viên (members)
#    - { "general": {"owner": "admin", "members": ["admin", "user_a", "user_b"]} }
channels_db = {}
channels_lock = threading.Lock()

# ----------------------------------------------------

def peer_reaper():
    """
    Luồng dọn dẹp (Reaper Thread) chạy ngầm.
    Chịu trách nhiệm tìm và xóa các peer đã "chết" (timeout)
    khỏi cả peers_db và các kênh (channels_db).
    """
    print(f"[Reaper] Luồng dọn dẹp bắt đầu với timeout {HEARTBEAT_TIMEOUT}s.")
    while True:
        # Chờ đến chu kỳ dọn dẹp tiếp theo
        time.sleep(REAPER_INTERVAL)
        
        current_time = time.time()
        dead_peers_usernames = [] # Danh sách peer cần xóa
        
        print(f"[Reaper] Đang chạy chu kỳ dọn dẹp...")

        # 1. Khóa và quét peers_db để tìm peer "chết"
        with peers_lock:
            for username, info in peers_db.items():
                if current_time - info.get("last_heartbeat", 0) > HEARTBEAT_TIMEOUT:
                    dead_peers_usernames.append(username)
            
            # Xóa các peer chết khỏi peers_db
            for username in dead_peers_usernames:
                del peers_db[username]
                print(f"[Reaper] Đã xóa peer (timeout): {username}")

        # 2. Nếu có peer chết, khóa và cập nhật channels_db
        if dead_peers_usernames:
            with channels_lock:
                for channel_name, info in channels_db.items():
                    # Lọc ra danh sách thành viên mới (chỉ giữ lại những ai KHÔNG CÓ trong dead_peers)
                    live_members = [member for member in info["members"] if member not in dead_peers_usernames]
                    channels_db[channel_name]["members"] = live_members
            
            print(f"[Reaper] Đã xóa các peer (timeout) khỏi tất cả các kênh.")
        
        print(f"[Reaper] Hoàn tất chu kỳ dọn dẹp. Tổng số peer đang hoạt động: {len(peers_db)}")


# ----- CÁC API CỦA TRACKER SERVER -----

@app.route('/register-peer', methods=['POST'])
def register_peer(headers, body):
    """
    API Đăng ký Peer (thay thế cho /submit-info).
    Peer gửi thông tin username, IP, port của mình.
    
    Body: {"username": "user_a", "ip": "192.168.1.10", "port": 9001}
    """
    print(f"[DEBUG TRACKER] Handler register_peer called. Raw body: {body[:50]}...")
    try:
        data = json.loads(body)
        username = data.get('username')
        ip = data.get('ip')
        port = int(data.get('port'))
        
        if not username or not ip or not port:
            return json.dumps({"status": "error", "message": "Thông tin username, ip, port là bắt buộc."})
        
        peer_info = {
            "ip": ip,
            "port": port,
            "last_heartbeat": time.time() # Ghi nhận heartbeat ngay khi đăng ký
        }
        
        with peers_lock:
            if username in peers_db:
                print(f"[Tracker] Peer {username} đăng ký lại.")
            else:
                print(f"[Tracker] Peer mới đăng ký: {username}")
            peers_db[username] = peer_info
        
        print(f"[DEBUG] message: Peer {username} đã được đăng ký.")
        return json.dumps({
            "status": "success",
            "message": f"Peer {username} đã được đăng ký."
        })
        
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Lỗi máy chủ: {e}"})

@app.route('/heartbeat', methods=['POST'])
def heartbeat(headers, body):
    """
    API Heartbeat.
    Peer phải gọi API này định kỳ để duy trì trạng thái "online".
    
    Body: {"username": "user_a"}
    """
    try:
        data = json.loads(body)
        username = data.get('username')
        
        with peers_lock:
            if username in peers_db:
                peers_db[username]["last_heartbeat"] = time.time()
                return json.dumps({"status": "success", "message": "Heartbeat đã được ghi nhận."})
            else:
                return json.dumps({"status": "error", "message": "Peer không tồn tại. Vui lòng /register-peer."})
                
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Lỗi máy chủ: {e}"})

@app.route('/channels/list', methods=['GET'])
def list_channels(headers, body):
    """
    API Lấy danh sách tất cả các kênh (channels) đang có.
    """
    with channels_lock:
        channel_names = list(channels_db.keys())
        
    return json.dumps({
        "status": "success",
        "channels": channel_names
    })

@app.route('/channels/create', methods=['POST'])
def create_channel(headers, body):
    """
    API Tạo một kênh chat mới.
    
    Body: {"username": "user_a", "channel_name": "general"}
    """
    try:
        data = json.loads(body)
        username = data.get('username')
        channel_name = data.get('channel_name')
        
        if not username or not channel_name:
            return json.dumps({"status": "error", "message": "username và channel_name là bắt buộc."})
        
        with channels_lock:
            if channel_name in channels_db:
                return json.dumps({"status": "error", "message": f"Kênh '{channel_name}' đã tồn tại."})
            
            # Tạo kênh mới
            channels_db[channel_name] = {
                "owner": username,
                "members": [username] # Người tạo tự động tham gia kênh
            }
            
        print(f"[Tracker] Kênh mới '{channel_name}' được tạo bởi {username}.")
        return json.dumps({"status": "success", "message": f"Kênh '{channel_name}' đã được tạo."})
        
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Lỗi máy chủ: {e}"})

@app.route('/channels/join', methods=['POST'])
def join_channel(headers, body):
    """
    API Tham gia vào một kênh chat đã có.
    
    Body: {"username": "user_b", "channel_name": "general"}
    """
    try:
        data = json.loads(body)
        username = data.get('username')
        channel_name = data.get('channel_name')
        
        if not username or not channel_name:
            return json.dumps({"status": "error", "message": "username và channel_name là bắt buộc."})
        
        with channels_lock:
            if channel_name not in channels_db:
                return json.dumps({"status": "error", "message": f"Kênh '{channel_name}' không tồn tại."})
            
            # Thêm thành viên vào kênh (đảm bảo không trùng lặp)
            if username not in channels_db[channel_name]["members"]:
                channels_db[channel_name]["members"].append(username)
                print(f"[Tracker] {username} đã tham gia kênh '{channel_name}'.")
                
        return json.dumps({"status": "success", "message": f"Đã tham gia kênh '{channel_name}'."})
        
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Lỗi máy chủ: {e}"})

@app.route('/channels/get-peers', methods=['POST'])
def get_peers_in_channel(headers, body):
    """
    API CỐT LÕI CHO P2P:
    Lấy thông tin (IP, Port) của TẤT CẢ các thành viên
    hiện đang online trong một kênh cụ thể.
    
    Body: {"channel_name": "general"}
    """
    try:
        data = json.loads(body)
        channel_name = data.get('channel_name')
        
        if not channel_name:
            return json.dumps({"status": "error", "message": "channel_name là bắt buộc."})
        
        # 1. Lấy danh sách username của thành viên trong kênh
        with channels_lock:
            if channel_name not in channels_db:
                return json.dumps({"status": "error", "message": f"Kênh '{channel_name}' không tồn tại."})
            member_usernames = list(channels_db[channel_name]["members"]) # Sao chép danh sách
        
        # 2. Lấy thông tin (IP, Port) CỦA NHỮNG PEER ĐANG ONLINE
        peers_info_list = []
        with peers_lock:
            for username in member_usernames:
                if username in peers_db: # Chỉ thêm nếu peer đó đang online (có trong peers_db)
                    peer_info = peers_db[username]
                    peers_info_list.append({
                        "username": username,
                        "ip": peer_info["ip"],
                        "port": peer_info["port"]
                    })
        
        return json.dumps({
            "status": "success",
            "channel": channel_name,
            "peers": peers_info_list
        })
        
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Lỗi máy chủ: {e}"})
    


# ----- KHỞI CHẠY MÁY CHỦ -----

if __name__ == "__main__":
    # 1. Khởi chạy Luồng Dọn dẹp (Reaper Thread)
    #    - Cờ 'daemon=True' đảm bảo luồng này sẽ tự động tắt
    #      khi chương trình chính (máy chủ) tắt.
    reaper_thread = threading.Thread(target=peer_reaper)
    reaper_thread.daemon = True
    reaper_thread.start()

    # 2. Cấu hình và Khởi chạy Máy chủ WeApRous
    parser = argparse.ArgumentParser(
        prog='AdvancedChatTracker',
        description='Khởi chạy máy chủ Tracker Nâng cao (Task 2) với Kênh và Heartbeat',
        epilog='Sử dụng framework WeApRous'
    )
    parser.add_argument('--server-ip',
        type=str,
        default='0.0.0.0',
        help='IP address để bind máy chủ. Default là 0.0.0.0'
    )
    parser.add_argument(
        '--server-port',
        type=int,
        default=PORT,
        help=f'Port để bind máy chủ. Default là {PORT}'
    )
 
    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    # Tạo kênh 'general' mặc định khi khởi động
    channels_db["#general"] = {"owner": "system", "members": []}
    print("[Tracker] Đã tạo kênh mặc định '#general'.")

    # Chuẩn bị địa chỉ và khởi chạy máy chủ
    print(f"[Tracker] Khởi chạy máy chủ Tracker NÂNG CAO tại {ip}:{port}...")
    print(f"[DEBUG] Tracker routes: {list(app.routes.keys())}")
    app.prepare_address(ip, port)
    app.run()