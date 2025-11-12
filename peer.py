import socket
import threading
import json
import time
import argparse
import sys

BUFFER = 4096
DEFAULT_TRACKER_PORT = 8000
HEARTBEAT_INTERVAL = 60 


class HybridPeer:
    def __init__(self, username, ip, port, tracker_ip, tracker_port):
        self.username = username
        self.ip = ip
        self.port = int(port)
        self.tracker_ip = tracker_ip
        self.tracker_port = int(tracker_port)
        self.channels = set()
        self.running = True
        self.peersockets = {}  
        self.server = None
        self.lock = threading.Lock()


    def http_request(self, method, path, body_obj=None):
        try:
            body = json.dumps(body_obj) if body_obj else ""
            req = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: {self.tracker_ip}:{self.tracker_port}\r\n"
                "User-Agent: HybridPeer/1.0\r\n"
                "Content-Type: application/json\r\n"
                "Accept: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{body}"
            )

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((self.tracker_ip, self.tracker_port))
            s.sendall(req.encode("utf-8"))

            #
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            s.close()

            resp = data.decode("utf-8", errors="ignore")
            # DEBUG:
            # print(f"[DEBUG RAW RESPONSE]\n{resp}\n")

            
            parts = resp.split("\r\n\r\n", 1)
            if len(parts) < 2:
                return {"status": "error", "message": "No body in HTTP response"}
                
            body = parts[1].strip()
            if not body:
                return {}
            
            try:
                return json.loads(body)
            except json.JSONDecodeError as e:
                if body == 'WeApRous hook executed':
                    print(f"[{self.username}] JSON parse error: Expecting JSON, received known WeApRous corruption.")
                    return {"status": "error", "message": "WEAPROUS_RESPONSE_CORRUPTED"}
                else:
                    print(f"[{self.username}] JSON parse error: {e}")
                    print(f"Body: '{body}'")
                    return {"status": "error", "message": "UNKNOWN_JSON_ERROR"}
            
        except Exception as e:
            print(f"[{self.username}] HTTP error: {e}")
            return {"status": "error", "message": f"Connection/Socket Error: {e}"}

    def register_with_tracker(self):
        payload = {"username": self.username, "ip": self.ip, "port": self.port}
        res = self.http_request("POST", "/register-peer", payload)
        
        if res.get("status") == "success":
            print(f"[{self.username}] Registered successfully with tracker.")
            self.join_channel("#general")
        elif res.get("message") == "WEAPROUS_RESPONSE_CORRUPTED":
             print(f"[{self.username}] Registration request sent. Ignoring corrupted response from Tracker.")
             self.join_channel("#general") #Vẫn cố gắng join
        else:
            print(f"[{self.username}] Registration failed:", res)

    def heartbeat(self):
        payload = {"username": self.username}
        while self.running:
            res = self.http_request("POST", "/heartbeat", payload)
            if res.get("status") == "error" and res.get("message") != "WEAPROUS_RESPONSE_CORRUPTED":
                print(f"[{self.username}] Heartbeat error: {res}")
            time.sleep(HEARTBEAT_INTERVAL)

    def get_channels(self):
        res = self.http_request("GET", "/channels/list")
        
        if res.get("status") == "success":
            print("Available channels:", ", ".join(res.get("channels", [])))
        elif res.get("message") == "WEAPROUS_RESPONSE_CORRUPTED":
            print(f"[{self.username}] Channel list request sent. Ignoring corrupted response from Tracker. (List unavailable)")
        else:
            print("Failed to get channels:", res)

    def create_channel(self, channel_name):
        payload = {"username": self.username, "channel_name": channel_name}
        res = self.http_request("POST", "/channels/create", payload)
        
        if res.get("status") == "success" or res.get("message") == "WEAPROUS_RESPONSE_CORRUPTED":
            self.channels.add(channel_name)
            print(f"[{self.username}] Request to create channel '{channel_name}' sent. (Assumed success)")
        else:
            print(res.get("message", res))

    def join_channel(self, channel_name):
        payload = {"username": self.username, "channel_name": channel_name}
        res = self.http_request("POST", "/channels/join", payload)
        
        if res.get("status") == "success" or res.get("message") == "WEAPROUS_RESPONSE_CORRUPTED":
            self.channels.add(channel_name)
            print(f"[{self.username}] Request to join channel '{channel_name}' sent. (Assumed success)")
        else:
            print(res.get("message", res))

    def get_peers_in_channel(self, channel_name):
        payload = {"channel_name": channel_name}
        res = self.http_request("POST", "/channels/get-peers", payload)
        
        if res.get("status") == "success":
            return res.get("peers", [])
        elif res.get("message") == "WEAPROUS_RESPONSE_CORRUPTED":
            print(f"[{self.username}] WARNING: Cannot sync peers. Tracker response corrupted and data (peer list) lost")
            return [] 
        else:
            print("Failed to get peers:", res)
            return []

    # ============================================================
    # --- Peer-to-peer network ------------------
    # ============================================================

    def start_server(self):
        t = threading.Thread(target=self._serve_loop, daemon=True)
        t.start()

    def _serve_loop(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.ip, self.port))
        self.server.listen(5)
        print(f"[{self.username}] P2P server listening on {self.ip}:{self.port}")
        while self.running:
            try:
                self.server.settimeout(1.0)
                conn, addr = self.server.accept()
                th = threading.Thread(target=self._handle_conn, args=(conn, addr), daemon=True)
                th.start()
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    break
        try:
            self.server.close()
        except:
            pass


    def _handle_conn(self, conn, addr):
        peer_username = "UNKNOWN"
        try:
            data = b""
            while self.running:
                chunk = conn.recv(BUFFER)
                if not chunk:
                    break
                data += chunk
                while b"\n" in data:
                    line, data = data.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        if msg.get("type") == "identify":
                            peer_username = msg.get("username")
                            if peer_username and peer_username not in self.peersockets:
                                with self.lock:
                                    self.peersockets[peer_username] = conn
                        
                        self._on_message(msg, conn)
                    except Exception:
                        continue
        except Exception:
            pass
        finally:
            with self.lock:
                if peer_username in self.peersockets and self.peersockets[peer_username] == conn:
                    del self.peersockets[peer_username]

    def _on_message(self, msg, conn):
        mtype = msg.get("type")
        if mtype == "chat":
            ch = msg.get("channel", "general")
            #In tin nhắn, sau đó in lại prompt '>'
            print(f"\n[{ch}] {msg.get('from')}: {msg.get('msg')}")
            sys.stdout.write("> ")
            sys.stdout.flush()
        elif mtype == "identify":
            pid = msg.get("username")
            if pid:
                with self.lock:
                    self.peersockets[pid] = conn
                print(f"[{self.username}] Accepted incoming connection from peer {pid}.")
        else:
            print(f"[{self.username}] Unknown message type:", msg)

    def connect_to_peer(self, peer_ip, peer_port, peer_username):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((peer_ip, int(peer_port)))
            ident = {"type": "identify", "username": self.username}
            s.sendall((json.dumps(ident) + "\n").encode("utf-8"))
            with self.lock:
                self.peersockets[peer_username] = s
            t = threading.Thread(target=self._recv_loop, args=(s,), daemon=True)
            t.start()
            print(f"[{self.username}] Connected to peer {peer_username} at {peer_ip}:{peer_port}")
        except Exception as e:
            # print(f"[{self.username}] Connection error:", e)
            pass #Lỗi kết nối kp cần in ra nếu ko thành công

    def _recv_loop(self, s):
        data = b""
        try:
            while True:
                chunk = s.recv(BUFFER)
                if not chunk:
                    break
                data += chunk
                while b"\n" in data:
                    line, data = data.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        self._on_message(msg, s)
                    except Exception:
                        continue
        except Exception:
            pass
        finally:
            # Dọn dẹp socket khi bị ngắt
            username_to_remove = None
            with self.lock:
                for uname, sock in list(self.peersockets.items()):
                    if sock == s:
                        username_to_remove = uname
                        break
                if username_to_remove:
                    del self.peersockets[username_to_remove]


    def broadcast(self, channel, text):
        if channel not in self.channels:
            print(f"[{self.username}] Error: You must be in channel '{channel}' to broadcast.")
            return

        obj = {"type": "chat", "from": self.username, "channel": channel, "msg": text}
        dead = []
        with self.lock:
            #Tự in tin nhắn của mình
            print(f"[{channel} {self.username}] {text}") 

            for uname, s in list(self.peersockets.items()):
                try:
                    s.sendall((json.dumps(obj) + "\n").encode("utf-8"))
                except Exception:
                    dead.append(uname)
            for uname in dead:
                self.peersockets.pop(uname, None)

        if len(self.peersockets) == 0:
            print(f"[{self.username}] Broadcast sent locally. No peers connected.")

    def send_direct(self, target_username, text):
        s = self.peersockets.get(target_username)
        if not s:
            print("Connecting to", target_username)
            return
        obj = {"type": "chat", "from": self.username, "channel": "direct", "msg": text}
        try:
            s.sendall((json.dumps(obj) + "\n").encode("utf-8"))
            print(f"[DM to {target_username}] {text}")
        except Exception:
            print("Send error, removing socket.")
            with self.lock:
                self.peersockets.pop(target_username, None)

    def sync_channel(self, channel_name):
        if channel_name not in self.channels:
            print(f"[{self.username}] You must join channel '{channel_name}' before syncing.")
            return
            
        peers = self.get_peers_in_channel(channel_name)
        if not peers:
            print(f"[{self.username}] Sync failed: No peer data received from Tracker.")
            return

        print(f"[{self.username}] Syncing: Found {len(peers)} peers (including self).")
        for p in peers:
            if p["username"] == self.username:
                continue
            if p["username"] not in self.peersockets:
                self.connect_to_peer(p["ip"], p["port"], p["username"])

    def stop(self):
        self.running = False
        try:
            if self.server:
                #Đóng server socket 
                self.server.close()
        except Exception:
            pass
        with self.lock:
            for s in self.peersockets.values():
                try:
                    s.close()
                except Exception:
                    pass
            self.peersockets.clear()


# ============================================================
# --- interface (CLI) --------------------------
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Hybrid Chat Peer (Task 2)")
    parser.add_argument("--username", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--tracker-ip", default="127.0.0.1")
    parser.add_argument("--tracker-port", type=int, default=DEFAULT_TRACKER_PORT)
    args = parser.parse_args()

    peer = HybridPeer(args.username, args.ip, args.port, args.tracker_ip, args.tracker_port)
    peer.start_server()
    
    #1. Đăng ký và tự động Join #general
    peer.register_with_tracker()

    #2. Khởi chạy Heartbeat
    threading.Thread(target=peer.heartbeat, daemon=True).start()

    print("\n--- CLI ---")
    print("Commands:")
    print("  channels                 - list channels")
    print("  create <name>            - create channel")
    print("  join <name>              - join channel")
    print("  sync <name>              - connect to peers in channel")
    print("  broadcast <ch> <msg>     - broadcast message (to connected peers in channel)")
    print("  send <user> <msg>        - direct message")
    print("  peers                    - list connected peers")
    print("  quit                     - exit\n")

    try:
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue

            if cmd == "channels":
                peer.get_channels()

            elif cmd.startswith("create "):
                try:
                    _, ch = cmd.split(maxsplit=1)
                    peer.create_channel(ch)
                except ValueError:
                    print("Usage: create <channel_name>")

            elif cmd.startswith("join "):
                try:
                    _, ch = cmd.split(maxsplit=1)
                    peer.join_channel(ch)
                except ValueError:
                    print("Usage: join <channel_name>")

            elif cmd.startswith("sync "):
                try:
                    _, ch = cmd.split(maxsplit=1)
                    peer.sync_channel(ch)
                except ValueError:
                    print("Usage: sync <channel_name>")

            elif cmd.startswith("broadcast "):
                parts = cmd.split(maxsplit=2)
                if len(parts) >= 3:
                    ch, msg = parts[1], parts[2]
                    peer.broadcast(ch, msg)
                else:
                    print("Usage: broadcast <channel_name> <message>")

            elif cmd.startswith("send "):
                parts = cmd.split(maxsplit=2)
                if len(parts) >= 3:
                    target, msg = parts[1], parts[2]
                    peer.send_direct(target, msg)
                else:
                    print("Usage: send <target_username> <message>")

            elif cmd == "peers":
                print("Connected peers:", list(peer.peersockets.keys()))

            elif cmd == "quit":
                break
    except KeyboardInterrupt:
        pass
    except EOFError:
        pass
    finally:
        peer.stop()


if __name__ == "__main__":
    main()