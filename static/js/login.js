// static/js/login.js

document.addEventListener("DOMContentLoaded", () => {

    // Chọn các phần tử từ HTML của bạn
    const loginForm = document.querySelector('form[action="/login"]');
    const usernameInput = document.querySelector('input[name="username"]');
    const passwordInput = document.querySelector('input[name="password"]');

    if (!loginForm) return; // Thoát nếu không ở trang login

    // Tạo một thẻ div để hiện lỗi
    const errorMessage = document.createElement("div");
    errorMessage.style.color = "red";
    loginForm.after(errorMessage);

    // Bắt sự kiện "submit" của form
    loginForm.addEventListener("submit", (event) => {

        // NGĂN CHẶN form tự gửi và tải lại trang
        event.preventDefault();

        // Gọi hàm fetch
        handleLogin();
    });

    async function handleLogin() {
        const username = usernameInput.value;
        const password = passwordInput.value;

        // Chúng ta đang truy cập qua proxy, nên chỉ cần dùng đường dẫn tương đối
        const loginUrl = '/login'; // Proxy sẽ tự điều hướng

        try {
            const response = await fetch(loginUrl, {
                method: 'POST',
                // Backend của bạn có thể cần JSON
                // hoặc form-data. Giả sử là JSON.
                body: JSON.stringify({
                    username: username,
                    password: password // (Backend sẽ check 'admin'/'password')
                }),
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.status === 200) {
                // Thành công! Backend đã set cookie
                errorMessage.textContent = "Login successful! Redirecting...";

                // *** QUAN TRỌNG: Lưu username để trang chat sử dụng ***
                localStorage.setItem("username", username);

                // Chuyển hướng về trang index
                window.location.href = '/index.html';

            } else if (response.status === 401) {
                // Sai credentials
                errorMessage.textContent = "Invalid username or password.";
            } else {
                errorMessage.textContent = `Error: ${response.statusText}`;
            }

        } catch (error) {
            console.error("Error during login:", error);
            errorMessage.textContent = "Could not connect to server.";
        }
    }
});