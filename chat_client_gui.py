import socket
import threading
import json
import time
import requests  # Sử dụng requests để gọi API tracker
import queue
import tkinter as tk
from tkinter import simpledialog, scrolledtext, messagebox, Listbox, END, Toplevel

# Cấu hình cơ bản
BUFFER = 4096
DEFAULT_TRACKER_URL = "http://127.0.0.1:8000"

class ChatClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("P2P Chat Client (Task 2)")
        self.root.geometry("800x600")

        # Biến trạng thái
        self.username = ""
        self.p2p_port = 0
        self.tracker_url = ""
        self.server_socket = None
        self.running = True
        self.peer_sockets = {}  # {"username": socket}
        self.lock = threading.Lock()
        
        # Queue để giao tiếp thread-safe với GUI
        self.message_queue = queue.Queue()

        # Biến theo dõi kênh
        self.joined_channels = set() # Xóa #general mặc định, để logic đăng ký xử lý
        self.current_channel = tk.StringVar(root, value="#general")

        # Bắt đầu với cửa sổ Login
        self.show_login_dialog()
        
        if not self.running: # Nếu người dùng đóng cửa sổ login
            self.root.destroy()
            return
            
        # Thiết lập GUI chính
        self.setup_main_gui()
        
        # ==================================================================
        # PHẦN ĐÃ SỬA LỖI
        # ==================================================================
        
        self.log_message(f"Chào mừng {self.username}! Đang khởi động...")

        # Chạy P2P listener trong một thread riêng
        threading.Thread(target=self.start_p2p_listener, daemon=True).start()

        # Chạy đăng ký tracker trong một thread riêng để không block GUI
        threading.Thread(target=self.register_with_tracker, daemon=True).start()
        
        # Bắt đầu vòng lặp xử lý queue của GUI (chạy trên main thread)
        self.start_queue_processor()
        
        # ==================================================================
        
        # Xử lý khi đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def show_login_dialog(self):
        """Hiển thị cửa sổ dialog modal để nhập thông tin."""
        dialog = Toplevel(self.root)
        dialog.title("Login")
        dialog.geometry("300x200")
        dialog.transient(self.root) # Giữ dialog ở trên cửa sổ chính
        dialog.grab_set() # Chặn tương tác với cửa sổ chính
        dialog.update_idletasks() # Đảm bảo dialog được vẽ
        
        # Canh giữa dialog
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text="Username:").pack(pady=5)
        user_entry = tk.Entry(dialog)
        user_entry.pack(padx=10, fill="x")

        tk.Label(dialog, text="P2P Port:").pack(pady=5)
        port_entry = tk.Entry(dialog)
        port_entry.pack(padx=10, fill="x")

        tk.Label(dialog, text="Tracker URL:").pack(pady=5)
        tracker_entry = tk.Entry(dialog)
        tracker_entry.insert(0, DEFAULT_TRACKER_URL)
        tracker_entry.pack(padx=10, fill="x")

        def on_submit():
            self.username = user_entry.get().strip()
            port_str = port_entry.get().strip()
            self.tracker_url = tracker_entry.get().strip()

            if not self.username or not port_str:
                messagebox.showerror("Lỗi", "Username và P2P Port là bắt buộc.", parent=dialog)
                return
            
            try:
                self.p2p_port = int(port_str)
            except ValueError:
                messagebox.showerror("Lỗi", "P2P Port phải là một con số.", parent=dialog)
                return
            
            if not self.tracker_url.startswith("http"):
                 messagebox.showerror("Lỗi", "Tracker URL phải bắt đầu bằng http://", parent=dialog)
                 return
                 
            self.running = True
            dialog.grab_release()
            dialog.destroy()

        submit_btn = tk.Button(dialog, text="Connect", command=on_submit)
        submit_btn.pack(pady=10)
        
        def on_dialog_close():
            self.running = False # Dừng ứng dụng nếu đóng dialog
            dialog.grab_release()
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
        
        # Chờ cho đến khi dialog bị đóng
        self.root.wait_window(dialog)


    def setup_main_gui(self):
        """Thiết lập giao diện chat chính."""
        # --- Khung bên trái (Kênh và Peers) ---
        left_frame = tk.Frame(self.root, width=200, bg="lightgrey")
        left_frame.pack(side="left", fill="y", padx=5, pady=5)

        tk.Label(left_frame, text="KÊNH CHAT", font=("Arial", 12, "bold"), bg="lightgrey").pack(pady=5)
        
        self.channel_list = Listbox(left_frame, height=10)
        self.channel_list.pack(fill="x", padx=5)
        self.update_channel_list_ui()
        self.channel_list.bind('<<ListboxSelect>>', self.on_channel_select)
        # Tự động chọn #general
        self.channel_list.insert(END, "#general")
        self.channel_list.selection_set(0)


        join_frame = tk.Frame(left_frame, bg="lightgrey")
        join_frame.pack(fill="x", pady=5)
        self.join_entry = tk.Entry(join_frame, width=15)
        self.join_entry.pack(side="left", fill="x", expand=True, padx=(5,0))
        self.join_btn = tk.Button(join_frame, text="Join", command=self.join_channel_callback)
        self.join_btn.pack(side="right", padx=(2,5))

        self.sync_btn = tk.Button(left_frame, text="Sync Peers", command=self.sync_peers_callback)
        self.sync_btn.pack(fill="x", padx=5, pady=5)
        
        tk.Label(left_frame, text="PEERS ĐÃ KẾT NỐI", font=("Arial", 12, "bold"), bg="lightgrey").pack(pady=10)
        self.peer_list = Listbox(left_frame, height=15)
        self.peer_list.pack(fill="both", expand=True, padx=5, pady=(0,5))

        # --- Khung bên phải (Chat) ---
        right_frame = tk.Frame(self.root)
        right_frame.pack(side="right", fill="both", expand=True)

        self.chat_display = scrolledtext.ScrolledText(right_frame, state="disabled", wrap="word", font=("Arial", 10))
        self.chat_display.pack(fill="both", expand=True, padx=5, pady=5)

        msg_frame = tk.Frame(right_frame, height=40)
        msg_frame.pack(fill="x", padx=5, pady=(0,5))
        
        self.msg_entry = tk.Entry(msg_frame, font=("Arial", 10))
        self.msg_entry.pack(side="left", fill="x", expand=True)
        self.msg_entry.bind("<Return>", self.send_message_callback) # Gửi bằng Enter

        self.send_btn = tk.Button(msg_frame, text="Send", command=self.send_message_callback)
        self.send_btn.pack(side="right", padx=5)

    def log_message(self, msg):
        """Thêm tin nhắn vào GUI (thread-safe)."""
        self.message_queue.put(msg)

    def start_queue_processor(self):
        """Bắt đầu vòng lặp kiểm tra queue và cập nhật GUI."""
        try:
            while True:
                msg = self.message_queue.get_nowait()
                
                self.chat_display.config(state="normal")
                self.chat_display.insert(END, f"{msg}\n")
                self.chat_display.config(state="disabled")
                self.chat_display.see(END) # Tự cuộn xuống
                
        except queue.Empty:
            pass # Không có gì trong queue, tiếp tục
        finally:
            # Lên lịch chạy lại sau 100ms
            if self.running:
                self.root.after(100, self.start_queue_processor)

    # --- Xử lý sự kiện GUI ---

    def on_channel_select(self, event):
        """Khi người dùng click vào một kênh trong danh sách."""
        try:
            selected_indices = self.channel_list.curselection()
            if not selected_indices:
                return
            selected_channel = self.channel_list.get(selected_indices[0])
            self.current_channel.set(selected_channel)
            self.log_message(f"--- Đã chuyển sang kênh: {selected_channel} ---")
        except Exception as e:
            self.log_message(f"[GUI Error] Lỗi chọn kênh: {e}")

    def send_message_callback(self, event=None):
        """Gửi tin nhắn từ ô input."""
        msg = self.msg_entry.get()
        if msg:
            channel = self.current_channel.get()
            # Gửi tin nhắn trong một thread riêng để không làm đơ GUI
            threading.Thread(target=self.broadcast_message, args=(channel, msg), daemon=True).start()
            self.msg_entry.delete(0, END)

    def join_channel_callback(self):
        """Tham gia một kênh mới."""
        channel_name = self.join_entry.get().strip()
        if not channel_name:
            return
        if not channel_name.startswith("#"):
            channel_name = f"#{channel_name}"
        
        self.join_entry.delete(0, END)
        # Chạy trong thread để không block GUI
        threading.Thread(target=self.join_channel, args=(channel_name,), daemon=True).start()

    def sync_peers_callback(self):
        """Đồng bộ peer từ tracker cho kênh hiện tại."""
        channel = self.current_channel.get()
        self.log_message(f"[{channel}] Đang đồng bộ peers...")
        # Chạy trong thread để không block GUI
        threading.Thread(target=self.sync_peers, args=(channel,), daemon=True).start()

    def on_closing(self):
        """Xử lý khi đóng cửa sổ."""
        if self.running and not messagebox.askokcancel("Thoát", "Bạn có chắc muốn thoát?"):
            return
            
        self.running = False
        self.log_message("...Đang tắt kết nối...")
        
        # Đóng server socket (nếu có)
        if self.server_socket:
            self.server_socket.close()

        # Đóng tất cả peer socket
        with self.lock:
            for sock in self.peer_sockets.values():
                sock.close()
        
        self.root.destroy()
            
    def update_channel_list_ui(self):
        """Cập nhật Listbox kênh."""
        current_selection = self.current_channel.get()
        self.channel_list.delete(0, END)
        
        found_selection = False
        sorted_channels = sorted(list(self.joined_channels))
        
        for i, ch in enumerate(sorted_channels):
            self.channel_list.insert(END, ch)
            if ch == current_selection:
                self.channel_list.selection_set(i)
                self.channel_list.activate(i)
                found_selection = True
        
        if not found_selection and sorted_channels:
             # Nếu kênh hiện tại không còn, chọn kênh đầu tiên
             self.current_channel.set(sorted_channels[0])
             self.channel_list.selection_set(0)
             self.channel_list.activate(0)


    def update_peer_list_ui(self):
        """Cập nhật Listbox peer."""
        self.peer_list.delete(0, END)
        with self.lock:
            for peer_name in sorted(self.peer_sockets.keys()):
                self.peer_list.insert(END, peer_name)

    # --- Logic Mạng (Tương tự chat_client.py) ---
    
    def http_request(self, method, path, body_obj=None):
        """Hàm helper để gọi API của Tracker."""
        try:
            url = f"{self.tracker_url}{path}"
            if method == "GET":
                resp = requests.get(url, timeout=5)
            elif method == "POST":
                resp = requests.post(url, json=body_obj, timeout=5)
            
            resp.raise_for_status() # Báo lỗi nếu status code là 4xx hoặc 5xx
            return resp.json()
        except requests.exceptions.RequestException as e:
            self.log_message(f"[Tracker Error] Lỗi khi gọi {method} {path}: {e}")
            return {"status": "error", "message": str(e)}

    def register_with_tracker(self):
        """API 1: Đăng ký với tracker."""
        payload = {"username": self.username, "p2p_port": self.p2p_port}
        res = self.http_request("POST", "/chat/register", payload)
        
        if res and res.get("status") == "success":
            self.log_message(f"[Tracker] Đăng ký thành công: {res.get('message')}")
            # Tự động tham gia #general khi đăng ký
            self.join_channel("#general")
        else:
            msg = res.get('message', 'Không rõ lỗi')
            self.log_message(f"[Tracker Error] Đăng ký thất bại: {msg}")
            # Lên lịch hiển thị lỗi và đóng app trên main thread
            self.root.after(0, 
                lambda: messagebox.showerror("Lỗi Tracker", f"Không thể đăng ký: {msg}")
            )
            self.root.after(0, self.on_closing)

    def join_channel(self, channel_name):
        """API 3: Tham gia kênh."""
        payload = {"username": self.username, "channel": channel_name}
        res = self.http_request("POST", "/chat/join", payload)
        
        if res and res.get("status") == "success":
            if channel_name not in self.joined_channels:
                self.joined_channels.add(channel_name)
                self.log_message(f"[Tracker] {res.get('message')}")
                # Cập nhật GUI (thread-safe)
                self.root.after(0, self.update_channel_list_ui)
            
            # Tự động đồng bộ khi join kênh mới
            self.sync_peers(channel_name)
        else:
            self.log_message(f"[Tracker Error] Tham gia kênh thất bại: {res.get('message')}")

    def sync_peers(self, channel):
        """API 4: Lấy danh sách peer và kết nối."""
        payload = {"username": self.username, "channel": channel}
        res = self.http_request("POST", "/chat/peers", payload)
        
        if res and res.get("status") == "success":
            peers = res.get("peers", [])
            if not peers:
                self.log_message(f"[{channel}] Không tìm thấy peer nào khác.")
                return

            self.log_message(f"[{channel}] Tìm thấy {len(peers)} peer(s). Đang kết nối...")
            
            with self.lock:
                current_peers = set(self.peer_sockets.keys())
            
            found_peers = set()

            for peer_info in peers:
                peer_username = peer_info.get("username")
                if not peer_username:
                    continue
                
                found_peers.add(peer_username)

                # Chỉ kết nối nếu chưa kết nối
                if peer_username != self.username and peer_username not in current_peers:
                    # Chạy kết nối trong thread riêng
                    threading.Thread(target=self.connect_to_peer, args=(peer_info,), daemon=True).start()
        else:
            self.log_message(f"[Tracker Error] Đồng bộ thất bại: {res.get('message')}")

    def start_p2p_listener(self):
        """Luồng 1: Chạy server P2P."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Cho phép tái sử dụng địa chỉ ngay lập tức
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.p2p_port))
            self.server_socket.listen(5)
            self.log_message(f"[P2P Server] Đang lắng nghe ở port {self.p2p_port}")
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    # Tạo luồng mới xử lý kết nối đến
                    threading.Thread(target=self.handle_peer_connection, args=(conn, addr), daemon=True).start()
                except OSError:
                    if self.running: # Bỏ qua lỗi nếu server đang tắt
                        self.log_message("[P2P Server] Lỗi chấp nhận kết nối (có thể do đang tắt).")
                    break # Thoát vòng lặp
        except OSError as e:
            self.log_message(f"[P2P Server Error] Không thể bind port {self.p2p_port}: {e}")
            # ==================================================================
            # PHẦN ĐÃ SỬA LỖI (Thread-safe GUI call)
            # ==================================================================
            # Lên lịch hiển thị lỗi trên main thread
            self.root.after(0, 
                lambda: messagebox.showerror("Lỗi P2P", f"Không thể chạy P2P server ở port {self.p2p_port}. Port có thể đang được dùng.")
            )
            # Lên lịch đóng ứng dụng trên main thread
            self.root.after(0, self.on_closing)
            # ==================================================================
        except Exception as e:
            if self.running:
                self.log_message(f"[P2P Server Error] {e}")

    def handle_peer_connection(self, conn, addr):
        """Luồng 3...N: Xử lý tin nhắn từ peer khác."""
        peer_username = None
        try:
            # Chờ tin nhắn handshake (với timeout)
            conn.settimeout(10.0)
            data = conn.recv(BUFFER).decode('utf-8')
            conn.settimeout(None) # Tắt timeout
            msg = json.loads(data)
            
            if msg.get("type") == "handshake":
                peer_username = msg.get("username")
                if not peer_username:
                    conn.close()
                    return

                self.log_message(f"[P2P] Chấp nhận kết nối từ {peer_username} ({addr[0]})")
                with self.lock:
                    # Nếu đã có kết nối cũ, đóng nó đi
                    if peer_username in self.peer_sockets:
                        self.peer_sockets[peer_username].close()
                    self.peer_sockets[peer_username] = conn
                self.root.after(0, self.update_peer_list_ui) # Cập nhật GUI
                
                # Vòng lặp nhận tin nhắn chat
                while self.running:
                    data = conn.recv(BUFFER)
                    if not data:
                        break # Peer ngắt kết nối
                    
                    try:
                        chat_msg = json.loads(data.decode('utf-8'))
                        if chat_msg.get("type") == "chat":
                            ch = chat_msg.get("channel", "unknown")
                            sender = chat_msg.get("username", "unknown")
                            content = chat_msg.get("content", "")
                            self.log_message(f"[{ch}] {sender}: {content}")
                    except json.JSONDecodeError:
                        self.log_message(f"[P2P] {peer_username} gửi tin nhắn lỗi (không phải JSON).")
            else:
                self.log_message(f"[P2P] Từ chối kết nối từ {addr[0]}: Handshake không hợp lệ.")
                conn.close()

        except socket.timeout:
            self.log_message(f"[P2P] {addr[0]} không gửi handshake (timeout).")
            conn.close()
        except (json.JSONDecodeError, KeyError):
            self.log_message(f"[P2P] {addr[0]} gửi handshake lỗi.")
            conn.close()
        except Exception as e:
            if self.running:
                self.log_message(f"[P2P Error] Lỗi khi xử lý {addr[0]}: {e}")
        finally:
            if peer_username:
                self.log_message(f"[P2P] Peer {peer_username} đã ngắt kết nối.")
                with self.lock:
                    if peer_username in self.peer_sockets and self.peer_sockets[peer_username] == conn:
                        del self.peer_sockets[peer_username]
                self.root.after(0, self.update_peer_list_ui) # Cập nhật GUI
            conn.close()

    def connect_to_peer(self, peer_info):
        """Chủ động kết nối P2P đến 1 peer."""
        peer_username = peer_info['username']
        peer_ip = peer_info['ip']
        peer_port = int(peer_info['port'])
        
        # Không kết nối với chính mình
        if peer_username == self.username:
            return
            
        # Kiểm tra lại (trong lock) xem đã kết nối chưa
        with self.lock:
            if peer_username in self.peer_sockets:
                self.log_message(f"[P2P Client] Đã kết nối với {peer_username} từ trước.")
                return
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0) # 5s timeout kết nối
            s.connect((peer_ip, peer_port))
            s.settimeout(None) # Tắt timeout
            
            # Gửi "handshake" ngay lập tức
            handshake_msg = json.dumps({
                "type": "handshake",
                "username": self.username
            }).encode('utf-8')
            s.sendall(handshake_msg)
            
            with self.lock:
                self.peer_sockets[peer_username] = s
            self.root.after(0, self.update_peer_list_ui) # Cập nhật GUI
                
            self.log_message(f"[P2P Client] Đã kết nối đến {peer_username} ({peer_ip}:{peer_port})")
            
            # Bắt đầu luồng lắng nghe tin nhắn từ peer này
            threading.Thread(target=self.handle_peer_messages_active, args=(s, peer_username), daemon=True).start()

        except Exception as e:
            self.log_message(f"[P2P Client] Lỗi kết nối đến {peer_username}: {e}")
            s.close()
            
    def handle_peer_messages_active(self, conn, peer_username):
        """Chỉ lắng nghe tin nhắn (dùng cho kết nối chủ động)."""
        try:
            while self.running:
                data = conn.recv(BUFFER)
                if not data:
                    break # Peer ngắt kết nối
                
                try:
                    chat_msg = json.loads(data.decode('utf-8'))
                    if chat_msg.get("type") == "chat":
                        ch = chat_msg.get("channel", "unknown")
                        sender = chat_msg.get("username", "unknown")
                        content = chat_msg.get("content", "")
                        self.log_message(f"[{ch}] {sender}: {content}")
                except json.JSONDecodeError:
                    self.log_message(f"[P2P] {peer_username} gửi tin nhắn lỗi (không phải JSON).")
        except Exception:
            pass # Lỗi sẽ được xử lý ở finally
        finally:
            self.log_message(f"[P2P] Peer {peer_username} (kết nối chủ động) đã ngắt.")
            with self.lock:
                # Chỉ xóa nếu socket này đúng là socket đang quản lý
                if peer_username in self.peer_sockets and self.peer_sockets[peer_username] == conn:
                    del self.peer_sockets[peer_username]
            self.root.after(0, self.update_peer_list_ui) # Cập nhật GUI
            conn.close()


    def broadcast_message(self, channel, message_content):
        """Gửi tin nhắn của mình cho TẤT CẢ các peer đang kết nối."""
        if channel not in self.joined_channels:
            self.log_message(f"[System] Bạn phải tham gia kênh '{channel}' trước khi gửi!")
            return

        self.log_message(f"[{channel}] {self.username}: {message_content}") # Tự hiển thị tin nhắn của mình

        payload = {
            "type": "chat",
            "username": self.username,
            "channel": channel,
            "content": message_content
        }
        json_payload = json.dumps(payload).encode('utf-8')

        dead_peers = []
        with self.lock:
            # Sao chép danh sách để tránh lỗi "dictionary changed size during iteration"
            for username, sock in self.peer_sockets.items():
                try:
                    sock.sendall(json_payload)
                except Exception as e:
                    self.log_message(f"[Broadcast] Lỗi khi gửi cho {username}: {e}. Đang xóa...")
                    dead_peers.append(username)
        
        # Xóa các peer chết (nếu có)
        if dead_peers:
            with self.lock:
                for username in dead_peers:
                    if username in self.peer_sockets:
                        self.peer_sockets[username].close()
                        del self.peer_sockets[username]
            self.root.after(0, self.update_peer_list_ui) # Cập nhật GUI

# --- Khởi chạy ứng dụng ---
if __name__ == "__main__":
    main_root = tk.Tk()
    app = ChatClientGUI(main_root)
    
    # Chỉ chạy mainloop nếu app không bị hủy ở cửa sổ login
    if app.running:
        main_root.mainloop()