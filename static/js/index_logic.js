// static/js/index_logic.js

document.addEventListener("DOMContentLoaded", () => {

    // Tìm khu vực để chèn nút
    const navArea = document.getElementById("navigation-area");
    if (!navArea) {
        console.error("Không tìm thấy 'navigation-area' trong index.html");
        return;
    }

    // Hàm trợ giúp để đọc cookie
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    // Kiểm tra xem cookie 'auth=true' có tồn tại không
    const isLoggedIn = getCookie("auth") === "true";

    if (isLoggedIn) {
        // Đã đăng nhập: Hiển thị nút "Chat"
        const chatButton = document.createElement("button");
        chatButton.textContent = "Go to Chat";
        chatButton.onclick = () => {
            // Chuyển hướng đến trang chat.html (bạn cần tạo file này)
            window.location.href = '/chat.html';
        };
        navArea.appendChild(chatButton);
    } else {
        // Chưa đăng nhập: Hiển thị nút "Login"
        const loginButton = document.createElement("button");
        loginButton.textContent = "Login";
        loginButton.onclick = () => {
            // Chuyển hướng đến trang login.html
            window.location.href = '/login.html';
        };
        navArea.appendChild(loginButton);
    }
});