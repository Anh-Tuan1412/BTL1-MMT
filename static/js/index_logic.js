// static/js/index_logic.js
// Đảm bảo script chạy ngay cả khi DOM chưa sẵn sàng

(function() {
    'use strict';
    
    function init() {
        console.log("[index_logic] Bắt đầu khởi tạo...");
        
        // Tìm hoặc tạo navigation area
        let navArea = document.getElementById("navigation-area");
        if (!navArea) {
            console.warn("[index_logic] Không tìm thấy navigation-area, tạo mới...");
            navArea = document.createElement("div");
            navArea.id = "navigation-area";
            navArea.style.textAlign = "center";
            navArea.style.padding = "2rem";
            
            // Tìm container hoặc body để thêm vào
            const container = document.querySelector(".container") || document.body;
            container.appendChild(navArea);
        }
        
        console.log("[index_logic] Navigation area:", navArea);

        // Hàm đọc cookie
        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) {
                return parts.pop().split(';').shift().trim();
            }
            return null;
        }

        // Kiểm tra cookie
        const authCookie = getCookie("auth");
        const isLoggedIn = authCookie === "true";
        
        console.log("[index_logic] Cookie 'auth':", authCookie);
        console.log("[index_logic] All cookies:", document.cookie);
        console.log("[index_logic] Is logged in:", isLoggedIn);

        // Xóa nút cũ nếu có
        navArea.innerHTML = "";

        // Tạo nút mới
        if (isLoggedIn) {
            console.log("[index_logic] Tạo nút Go to Chat");
            const chatButton = document.createElement("button");
            chatButton.className = "btn-chat";
            chatButton.textContent = "💬 Go to Chat";
            chatButton.style.cssText = "padding: 1rem 2rem; margin: 0.5rem; font-size: 1rem; font-weight: 600; border: none; border-radius: 5px; cursor: pointer; background: #667eea; color: white;";
            chatButton.onclick = function() {
                window.location.href = '/chat.html';
            };
            navArea.appendChild(chatButton);
            console.log("[index_logic] Đã thêm nút Go to Chat");
        } else {
            console.log("[index_logic] Tạo nút Login");
            const loginButton = document.createElement("button");
            loginButton.className = "btn-login";
            loginButton.textContent = "🔐 Login";
            loginButton.style.cssText = "padding: 1rem 2rem; margin: 0.5rem; font-size: 1rem; font-weight: 600; border: none; border-radius: 5px; cursor: pointer; background: #4caf50; color: white;";
            loginButton.onclick = function() {
                window.location.href = '/login.html';
            };
            navArea.appendChild(loginButton);
            console.log("[index_logic] Đã thêm nút Login");
        }
        
        console.log("[index_logic] Hoàn tất!");
    }

    // Chạy ngay khi DOM sẵn sàng
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOM đã sẵn sàng, chạy ngay
        init();
    }
    
    // Fallback: chạy sau 1 giây nếu vẫn chưa chạy
    setTimeout(function() {
        const navArea = document.getElementById("navigation-area");
        if (navArea && navArea.children.length === 0) {
            console.warn("[index_logic] Fallback: Chạy lại sau 1 giây...");
            init();
        }
    }, 1000);
})();