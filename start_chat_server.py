# start_chat_server.py
import json
import socket
import argparse
from daemon.weaprous import WeApRous

PORT = 8000  # Port cho server trung tâm
app = WeApRous()

# ----- Cơ sở dữ liệu "in-memory" (giống file PDF) -----
#
db = {
    "peers": {
        # "username": {"ip": "1.2.3.4", "port": 5001, "channels": ["general"]}
    },
    "channels": {
        "general": {"description": "Kênh chat chung"},
        "random": {"description": "Kênh chat ngẫu nhiên"}
    }
}
# ------------------------------------------------

# API 1: Peer đăng ký (Peer registration)
#
@app.route('/chat/register', methods=['POST'])
def register_peer(request, response):
    try:
        body_data = json.loads(request.body)
        username = body_data['username']
        p2p_port = int(body_data['p2p_port'])
        
        # Lấy IP của client từ connection
        ip = request.connaddr[0] 
        
        if username in db["peers"]:
             return {"status": "error", "message": "Username đã tồn tại"}

        db["peers"][username] = {"ip": ip, "port": p2p_port, "channels": []}
        print(f"[ChatServer] Đăng ký Peer: {username} tại {ip}:{p2p_port}")
        
        return {"status": "success", "message": f"Chào mừng {username}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# API 2: Lấy danh sách kênh
@app.route('/chat/channels', methods=['GET'])
def get_channels(request, response):
    return {"status": "success", "channels": list(db["channels"].keys())}

# API 3: Tham gia kênh
@app.route('/chat/join', methods=['POST'])
def join_channel(request, response):
    try:
        body_data = json.loads(request.body)
        username = body_data['username']
        channel = body_data['channel']

        if username not in db["peers"]:
            return {"status": "error", "message": "Peer chưa đăng ký"}
        if channel not in db["channels"]:
            return {"status": "error", "message": "Kênh không tồn tại"}

        if channel not in db["peers"][username]["channels"]:
            db["peers"][username]["channels"].append(channel)
            
        print(f"[ChatServer] Peer {username} tham gia kênh {channel}")
        return {"status": "success", "message": f"{username} đã tham gia {channel}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# API 4: Lấy danh sách peer trong kênh (Peer discovery)
#
@app.route('/chat/peers', methods=['POST'])
def get_peers(request, response):
    try:
        body_data = json.loads(request.body)
        channel = body_data['channel']
        my_username = body_data['username'] # Để không lấy chính mình

        if channel not in db["channels"]:
            return {"status": "error", "message": "Kênh không tồn tại"}

        peer_list = []
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

# --- Main ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='ChatServer', description='Chat Tracker Server')
    parser.add_argument('--server-ip', default='0.0.0.0')
    parser.add_argument('--server-port', type=int, default=PORT)
    args = parser.parse_args()
    
    app.prepare_address(args.server_ip, args.server_port)
    print(f"[ChatServer] Bắt đầu Tracker Server tại {args.server_ip}:{args.server_port}")
    app.run()