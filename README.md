# WeApRous - P2P Chat Application

Ứng dụng chat P2P (Peer-to-Peer) được xây dựng với Python backend và WebRTC cho giao tiếp trực tiếp giữa các peer.

## 📋 Yêu Cầu

- Python 3.7+
- Trình duyệt hiện đại hỗ trợ WebRTC (Chrome, Firefox, Edge)

## 🚀 Cài Đặt và Chạy

### Bước 1: Chạy Backend Server (Task 1)

Mở terminal thứ nhất:

```bash
python start_backend.py
```

Backend sẽ chạy trên port **9000** (mặc định).

### Bước 2: Chạy Proxy Server (Task 1)

Mở terminal thứ hai:

```bash
python start_proxy.py
```

Proxy sẽ chạy trên port **8081** (mặc định).

### Bước 3: Chạy Tracker Server (Task 2)

Mở terminal thứ ba:

```bash
python tracker.py
```

Tracker sẽ chạy trên port **8000** (mặc định).

### Bước 4: Truy Cập Ứng Dụng

Mở trình duyệt và truy cập:

```
http://127.0.0.1:8081/index.html
```

## 📖 Hướng Dẫn Sử Dụng

### Đăng Nhập

1. Click vào nút **"🔐 Login"** hoặc truy cập trực tiếp:

   ```
   http://127.0.0.1:8081/login.html
   ```

2. Nhập thông tin đăng nhập:

   - **Username:** `admin`
   - **Password:** `password`

3. Sau khi đăng nhập thành công, bạn sẽ thấy nút **"💬 Go to Chat"**.

### Sử Dụng Chat

1. Click vào nút **"💬 Go to Chat"** để vào trang chat.

2. Ứng dụng sẽ tự động:

   - Đăng ký với Tracker server
   - Tham gia kênh `#general` mặc định
   - Tìm kiếm và kết nối P2P với các peer khác

3. **Gửi tin nhắn:**

   - Nhập tin nhắn vào ô input
   - Nhấn Enter hoặc click nút "Send"
   - Tin nhắn sẽ được gửi trực tiếp P2P đến tất cả các peer đang kết nối

4. **Tạo kênh mới:**

   - Click nút **"+ Create Channel"**
   - Nhập tên kênh (ví dụ: `random`)
   - Click "Create"

5. **Chuyển kênh:**
   - Click vào tên kênh trong sidebar bên trái

## 🏗️ Kiến Trúc

### Task 1: Backend & Proxy Server

- **Backend Server** (`start_backend.py`):

  - Xử lý HTTP requests
  - Xử lý đăng nhập (POST /login)
  - Quản lý cookie authentication
  - Serve static files (HTML, CSS, JS, images)

- **Proxy Server** (`start_proxy.py`):
  - Reverse proxy với routing dựa trên hostname
  - Hỗ trợ load balancing (round-robin)
  - Forward requests đến backend servers

### Task 2: P2P Chat System

- **Tracker Server** (`tracker.py`):

  - Quản lý danh sách peers online
  - Quản lý channels (kênh chat)
  - Xử lý heartbeat để theo dõi peers
  - Relay WebRTC signaling (offer, answer, ICE candidates)

- **Web Client** (`chat.html` + `chat_client.js`):
  - Giao diện chat đẹp và hiện đại
  - Kết nối P2P với WebRTC
  - Gửi/nhận tin nhắn trực tiếp giữa các peer
  - Quản lý channels và users

## 📁 Cấu Trúc Thư Mục

```
CO3094-weaprous/
├── daemon/              # Core backend modules
│   ├── backend.py      # Backend server implementation
│   ├── proxy.py         # Proxy server implementation
│   ├── httpadapter.py   # HTTP request/response adapter
│   ├── request.py       # HTTP request parser
│   ├── response.py      # HTTP response builder
│   └── ...
├── www/                 # HTML files
│   ├── index.html       # Trang chủ
│   ├── login.html       # Trang đăng nhập
│   └── chat.html        # Trang chat
├── static/              # Static files
│   ├── css/            # Stylesheets
│   ├── js/             # JavaScript files
│   └── images/         # Images
├── config/             # Configuration files
│   └── proxy.conf      # Proxy routing configuration
├── start_backend.py    # Backend server entry point
├── start_proxy.py      # Proxy server entry point
├── tracker.py          # Tracker server (Task 2)
└── peer.py             # CLI peer client (optional)
```

## 🔧 Cấu Hình

### Thay Đổi Port

**Backend:**

```bash
python start_backend.py --server-port 9001
```

**Proxy:**

```bash
python start_proxy.py --server-port 8082
```

**Tracker:**

```bash
python tracker.py --server-port 8001
```

### Proxy Routing

Chỉnh sửa file `config/proxy.conf` để cấu hình routing:

```
host "127.0.0.1:8081" {
    proxy_pass http://127.0.0.1:9000;
}
```

## 🐛 Xử Lý Lỗi

### Port đã được sử dụng

Nếu gặp lỗi "Address already in use":

- Đổi port bằng cách thêm `--server-port <port_mới>`
- Hoặc tắt ứng dụng đang sử dụng port đó

### Không thấy nút "Go to Chat"

1. Kiểm tra cookie trong Developer Tools (F12 → Application → Cookies)
2. Đảm bảo cookie `auth=true` đã được set
3. Thử xóa cookie và đăng nhập lại

### Không kết nối được P2P

1. Đảm bảo Tracker server đang chạy
2. Kiểm tra console của trình duyệt (F12) xem có lỗi không
3. Đảm bảo WebRTC được hỗ trợ trong trình duyệt

## 📝 Ghi Chú

- **Credentials mặc định:** `admin` / `password`
- **Kênh mặc định:** `#general`
- **Heartbeat interval:** 30 giây
- **Peer sync interval:** 10 giây
- **Signal poll interval:** 2 giây

## 👥 Nhiều Người Dùng

Để test với nhiều người dùng:

1. Mở nhiều cửa sổ trình duyệt (hoặc dùng chế độ ẩn danh)
2. Đăng nhập với cùng username/password
3. Vào trang chat
4. Các peer sẽ tự động kết nối P2P và có thể chat với nhau

## 📚 Tài Liệu Tham Khảo

- [WebRTC API](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API)
- [RTCPeerConnection](https://developer.mozilla.org/en-US/docs/Web/API/RTCPeerConnection)
- [RTCDataChannel](https://developer.mozilla.org/en-US/docs/Web/API/RTCDataChannel)

## 📄 License

Phần mềm này được phát triển cho mục đích học tập trong khóa học CO3093/CO3094.
