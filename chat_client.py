# chat_client.py
import socket
import threading
import requests # Thư viện để gọi API (dễ hơn socket)
import json
import time

# --- Cấu hình ---
TRACKER_URL = "http://127.0.0.1:8000" # Địa chỉ server trung tâm
MY_USERNAME = ""
MY_P2P_PORT = 0

# --- Biến toàn cục (được bảo vệ bởi Lock) ---
# Danh sách các socket đang kết nối P2P (để broadcast)
#
peer_sockets = {} # Dùng dict để quản lý: {"username": socket}
lock = threading.Lock() # Bảo vệ peer_sockets
# ----------------------------------------------

def p2p_listener():
    """
    Luồng 1: Chạy như một server P2P, lắng nghe kết nối từ peer khác.
    """
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', MY_P2P_PORT))
        server.listen(5)
        print(f"[P2P Server] Đang lắng nghe P2P ở port {MY_P2P_PORT}")
    except OSError as e:
        print(f"[Lỗi] Không thể bind port {MY_P2P_PORT}. Có thể port đang được dùng.")
        print("Hãy thử lại với port khác (ví dụ 5002, 5003).")
        return # Tắt luồng

    while True:
        try:
            conn, addr = server.accept()
            # Yêu cầu peer mới gửi thông tin (TÍNH NĂNG MỞ RỘNG)
            # Peer mới kết nối phải gửi 1 tin JSON đầu tiên để "giới thiệu"
            # {"type": "handshake", "username": "user_B"}
            data = conn.recv(1024).decode('utf-8')
            peer_info = json.loads(data)
            
            if peer_info.get("type") == "handshake":
                peer_username = peer_info.get("username")
                print(f"\n[P2P Server] Chấp nhận kết nối từ {peer_username} ({addr})")
                
                with lock:
                    peer_sockets[peer_username] = conn
                
                # Tạo luồng mới để xử lý tin nhắn từ peer này
                threading.Thread(target=handle_peer_message, args=(conn, peer_username), daemon=True).start()
            else:
                conn.close() # Không đúng giao thức

        except Exception as e:
            print(f"[P2P Server] Lỗi: {e}")
            break

def handle_peer_message(conn, peer_username):
    """
    Luồng 3...N: Xử lý tin nhắn đến từ một peer cụ thể.
    """
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break # Peer ngắt kết nối
            
            message_data = json.loads(data.decode('utf-8'))
            
            # Hiển thị tin nhắn P2P (Notification system)
            #
            print(f"\n[{peer_username}]: {message_data.get('content')}\n> ", end="")
            
        except (json.JSONDecodeError, KeyError):
            pass # Bỏ qua tin nhắn lỗi
        except Exception:
            break
    
    print(f"\n[P2P] Peer {peer_username} đã ngắt kết nối.")
    with lock:
        if peer_username in peer_sockets:
            del peer_sockets[peer_username]
    conn.close()

def broadcast_message(message_content):
    """
    Gửi tin nhắn của mình cho TẤT CẢ các peer đang kết nối (Broadcast).
   
    """
    payload = {
        "type": "chat",
        "username": MY_USERNAME,
        "content": message_content
    }
    json_payload = json.dumps(payload).encode('utf-8')

    with lock:
        # Sao chép danh sách key để tránh lỗi "dictionary changed size during iteration"
        usernames = list(peer_sockets.keys()) 
        for username in usernames:
            try:
                peer_sockets[username].sendall(json_payload)
            except Exception as e:
                print(f"[Broadcast] Lỗi khi gửi cho {username}: {e}. Đang xóa...")
                # Nếu gửi lỗi (peer kia đã tắt), xóa khỏi danh sách
                if username in peer_sockets:
                    peer_sockets[username].close()
                    del peer_sockets[username]

def connect_to_peer(peer_info):
    """
    Chủ động kết nối P2P đến 1 peer
   
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((peer_info['ip'], peer_info['port']))
        
        # Gửi "handshake" ngay lập tức
        handshake_msg = json.dumps({
            "type": "handshake",
            "username": MY_USERNAME
        }).encode('utf-8')
        s.sendall(handshake_msg)
        
        peer_username = peer_info['username']
        with lock:
            peer_sockets[peer_username] = s
            
        # Tạo luồng xử lý tin nhắn từ họ
        threading.Thread(target=handle_peer_message, args=(s, peer_username), daemon=True).start()
        print(f"[P2P Client] Đã kết nối đến {peer_username} ({peer_info['ip']}:{peer_info['port']})")

    except Exception as e:
        print(f"[P2P Client] Lỗi kết nối đến {peer_info['username']}: {e}")

def main_cli():
    """
    Luồng 2: Chạy giao diện dòng lệnh (CLI).
    """
    # ----- 1. ĐĂNG KÝ (Client-Server Phase) -----
    global MY_USERNAME, MY_P2P_PORT
    while not MY_USERNAME:
        MY_USERNAME = input("Nhập username của bạn: ")
    while MY_P2P_PORT == 0:
        try:
            MY_P2P_PORT = int(input(f"Nhập port P2P bạn muốn chạy (ví dụ 5001, 5002...): "))
        except ValueError:
            pass

    try:
        resp = requests.post(f"{TRACKER_URL}/chat/register", json={
            "username": MY_USERNAME,
            "p2p_port": MY_P2P_PORT
        }, timeout=3)
        print(f"[Tracker] Server nói: {resp.json().get('message')}")
        if resp.json().get('status') == 'error':
            return # Dừng nếu không đăng ký được
    except Exception as e:
        print(f"[Tracker] Không thể kết nối Tracker Server: {e}")
        return

    # ----- 2. KHỞI ĐỘNG P2P LISTENER -----
    listener_thread = threading.Thread(target=p2p_listener, daemon=True)
    listener_thread.start()
    time.sleep(0.5) # Chờ luồng server P2P khởi động

    # ----- 3. GIAO DIỆN CHÍNH (Message submission) -----
    #
    print("\n----- CHÀO MỪNG BẠN ĐẾN VỚI HỆ THỐNG CHAT -----")
    print("Các lệnh: /join <channel>, /peers <channel>, /quit")
    
    while True:
        message = input("> ")
        if not message:
            continue
            
        if message.startswith("/quit"):
            break
            
        elif message.startswith("/join "):
            try:
                channel = message.split(" ")[1]
                resp = requests.post(f"{TRACKER_URL}/chat/join", json={
                    "username": MY_USERNAME, "channel": channel
                })
                print(f"[Tracker] {resp.json().get('message')}")
            except Exception as e:
                print(f"[Lỗi] {e}")

        elif message.startswith("/peers "):
            try:
                channel = message.split(" ")[1]
                resp = requests.post(f"{TRACKER_URL}/chat/peers", json={
                    "username": MY_USERNAME, "channel": channel
                })
                peers = resp.json().get("peers", [])
                print(f"[Tracker] Đang có {len(peers)} peer trong kênh '{channel}':")
                for p in peers:
                    print(f"  - {p['username']} ({p['ip']}:{p['port']})")
                    # TÍNH NĂNG MỞ RỘNG: Tự động kết nối P2P
                    with lock:
                        is_connected = p['username'] in peer_sockets
                    if not is_connected:
                        print(f"    Đang tự động kết nối...")
                        connect_to_peer(p)
                        
            except Exception as e:
                print(f"[Lỗi] {e}")
        
        else:
            # Gửi tin nhắn P2P (Broadcast)
            broadcast_message(message)

    print("[Main] Đang tắt...")
    with lock:
        for conn in peer_sockets.values():
            conn.close()

if __name__ == "__main__":
    main_cli()