# Hướng Dẫn Chạy Ứng Dụng WeApRous

## Yêu Cầu

- Python 3.x đã được cài đặt
- Windows/Linux/Mac

## Các Bước Chạy Ứng Dụng

### Bước 1: Mở Terminal/Command Prompt

Mở **2 cửa sổ terminal** riêng biệt (một cho Backend, một cho Proxy).

### Bước 2: Chạy Backend Server

Trong terminal thứ nhất, chạy lệnh:

```bash
python start_backend.py
```

Hoặc với các tùy chọn:

```bash
python start_backend.py --server-ip 127.0.0.1 --server-port 9000
```

**Kết quả mong đợi:**

```
[Backend] Listening on port 9000
```

### Bước 3: Chạy Proxy Server

Trong terminal thứ hai, chạy lệnh:

```bash
python start_proxy.py
```

Hoặc với các tùy chọn:

```bash
python start_proxy.py --server-ip 127.0.0.1 --server-port 8081
```

**Kết quả mong đợi:**

```
Proxy server đang chạy trên port 8081
```

### Bước 4: Truy Cập Ứng Dụng

Mở trình duyệt và truy cập:

```
http://127.0.0.1:8081/index.html
```

Hoặc:

```
http://localhost:8081/index.html
```

### Bước 5: Đăng Nhập

1. Click vào nút **"Login"** hoặc truy cập trực tiếp:

   ```
   http://127.0.0.1:8081/login.html
   ```

2. Nhập thông tin đăng nhập:

   - **Username:** `admin`
   - **Password:** `password`

3. Sau khi đăng nhập thành công, bạn sẽ được chuyển về trang index và thấy nút **"Go to Chat"**.

## Các Tính Năng Khác (Tùy Chọn)

### Chạy Tracker Server (Cho Chat P2P)

Nếu bạn muốn sử dụng tính năng chat P2P, cần chạy thêm Tracker:

```bash
python tracker.py
```

Tracker sẽ chạy trên port **8000** (mặc định).

### Chạy Peer Client (Cho Chat P2P)

Để tham gia chat P2P, chạy peer client:

```bash
python peer.py --username <tên_của_bạn> --port <port_number> --ip 127.0.0.1 --tracker-ip 127.0.0.1 --tracker-port 8000
```

**Ví dụ:**

```bash
python peer.py --username alice --port 9001
python peer.py --username bob --port 9002
```

## Lưu Ý Quan Trọng

1. **Thứ tự khởi động:** Luôn chạy Backend trước, sau đó mới chạy Proxy.

2. **Port đang sử dụng:**

   - Backend: `9000` (mặc định)
   - Proxy: `8081` (mặc định)
   - Tracker: `8000` (mặc định)

3. **Nếu port bị chiếm:** Thay đổi port bằng cách thêm tham số `--server-port` khi chạy.

4. **Cookie:** Sau khi đăng nhập thành công, cookie `auth=true` sẽ được lưu. Nếu không thấy nút "Go to Chat", hãy:
   - Kiểm tra console của trình duyệt (F12) xem có lỗi không
   - Xóa cookie và thử đăng nhập lại
   - Đảm bảo đã thêm `credentials: 'include'` trong fetch request (đã được sửa)

## Xử Lý Lỗi

### Lỗi "Address already in use"

- Port đang được sử dụng bởi ứng dụng khác
- Giải pháp: Đổi port hoặc tắt ứng dụng đang dùng port đó

### Lỗi "Module not found"

- Thiếu module Python
- Giải pháp: Cài đặt các module cần thiết (thường là các module trong thư mục `daemon/`)

### Không thấy nút "Go to Chat" sau khi đăng nhập

- Cookie không được lưu
- Giải pháp: Đảm bảo đã sửa file `static/js/login.js` với `credentials: 'include'` (đã được sửa)

## Cấu Trúc Thư Mục

```
CO3094-weaprous/
├── daemon/          # Các module backend
├── www/             # Các file HTML
├── static/          # CSS, JS, images
├── config/          # File cấu hình proxy
├── start_backend.py # Khởi chạy backend
├── start_proxy.py   # Khởi chạy proxy
└── tracker.py       # Tracker server (P2P)
```

## Hỗ Trợ

Nếu gặp vấn đề, kiểm tra:

1. Console của trình duyệt (F12 → Console)
2. Terminal output của Backend và Proxy
3. Đảm bảo tất cả các file cần thiết đều có trong thư mục
