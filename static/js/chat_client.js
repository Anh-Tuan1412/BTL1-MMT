// static/js/chat_client.js
// PHIÊN BẢN NÂNG CẤP VỚI WEBRTC (P2P)

document.addEventListener("DOMContentLoaded", () => {

    // --- Lấy các element từ chat.html ---
    const userListUI = document.getElementById("user-list");
    const chatBoxUI = document.getElementById("chat-box");
    const messageInput = document.getElementById("message-input");
    const sendButton = document.getElementById("send-btn");

    // === 1. LẤY THÔNG TIN PEER (CLIENT) NÀY ===
    const myUsername = localStorage.getItem("username");
    if (!myUsername) {
        alert("Bạn chưa đăng nhập!");
        window.location.href = '/login.html';
        return;
    }

    const myPeerInfo = {
        username: myUsername,
        ip: "127.0.0.1", // (Giả lập)
        port: Math.floor(Math.random() * 5000) + 10000 // (Giả lập)
    };

    const CURRENT_CHANNEL = "#general";

    // === 2. CẤU HÌNH WEBRTC ===

    // Cấu hình máy chủ STUN (để vượt NAT/firewall)
    // Chúng ta dùng máy chủ miễn phí của Google
    const RTC_CONFIG = {
        'iceServers': [
            { 'urls': 'stun:stun.l.google.com:19302' },
            { 'urls': 'stun:stun1.l.google.com:19302' },
        ]
    };

    // Nơi lưu trữ tất cả các kết nối P2P
    // { "ten_peer": RTCPeerConnection, ... }
    const peerConnections = {};

    // ================================================
    // === GIAI ĐOẠN 1: GIAO TIẾP CLIENT-SERVER (với Tracker) ===
    // ================================================

    // (Các hàm registerWithTracker, sendHeartbeat, joinChannel
    //  giữ nguyên như file trước của bạn)

    async function registerWithTracker() {
        await fetch('/register-peer', {
            method: 'POST', body: JSON.stringify(myPeerInfo),
            headers: { 'Content-Type': 'application/json' }
        });
    }

    async function sendHeartbeat() {
        await fetch('/heartbeat', {
            method: 'POST', body: JSON.stringify({ username: myUsername }),
            headers: { 'Content-Type': 'application/json' }
        });
    }

    async function joinChannel(channelName) {
        await fetch('/channels/join', {
            method: 'POST',
            body: JSON.stringify({ username: myUsername, channel_name: channelName }),
            headers: { 'Content-Type': 'application/json' }
        });
    }

    /**
     * Cập nhật giao diện danh sách người dùng
     */
    function updateUserListUI(peers) {
        userListUI.innerHTML = ""; // Xóa list cũ
        peers.forEach(peer => {
            const li = document.createElement("li");
            li.textContent = peer.username;
            if (peer.username === myUsername) {
                li.textContent += " (You)";
                li.style.fontWeight = "bold";
            }
            userListUI.appendChild(li);
        });
    }

    // ================================================
    // === GIAI ĐOẠN 2: LOGIC WEBRTC (P2P) ===
    // ================================================

    /**
     * Gửi tín hiệu (offer, answer, candidate) đến một peer cụ thể
     * thông qua server (tracker.py)
     */
    async function sendSignal(toUsername, signalData) {
        await fetch('/signal', {
            method: 'POST',
            body: JSON.stringify({
                to: toUsername,
                from: myUsername,
                signal: signalData
            }),
            headers: { 'Content-Type': 'application/json' }
        });
    }

    /**
     * Lấy tín hiệu đang chờ (poll) từ server
     */
    async function fetchSignals() {
        try {
            const response = await fetch('/get-signals', {
                method: 'POST',
                body: JSON.stringify({ username: myUsername }),
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            if (data.status === 'success' && data.signals) {
                // Xử lý từng tín hiệu nhận được
                data.signals.forEach(signalMsg => {
                    handleSignal(signalMsg.from, signalMsg.signal);
                });
            }
        } catch (e) {
            // Bỏ qua lỗi polling
        }
    }

    /**
     * Xử lý tín hiệu nhận được từ một peer khác
     */
    async function handleSignal(fromUsername, signal) {
        let pc = peerConnections[fromUsername];

        // Nếu chưa có kết nối, tạo một kết nối mới (trường hợp người kia gọi trước)
        if (!pc) {
            pc = createPeerConnection(fromUsername);
        }

        try {
            if (signal.sdp) { // Đây là 'offer' hoặc 'answer'
                await pc.setRemoteDescription(new RTCSessionDescription(signal));

                // Nếu đây là 'offer', chúng ta cần tạo 'answer'
                if (signal.type === 'offer') {
                    const answer = await pc.createAnswer();
                    await pc.setLocalDescription(answer);
                    sendSignal(fromUsername, answer); // Gửi answer lại
                }
            } else if (signal.candidate) { // Đây là 'ICE candidate'
                await pc.addIceCandidate(new RTCIceCandidate(signal));
            }
        } catch (e) {
            console.error(`Lỗi khi xử lý tín hiệu từ ${fromUsername}:`, e);
        }
    }

    /**
     * Tạo một kết nối P2P mới đến một peer
     * @param {string} peerUsername Tên của peer cần kết nối
     * @param {boolean} isInitiator Báo cho biết ta có phải là người "gọi" (tạo offer) không
     */
    function createPeerConnection(peerUsername, isInitiator = false) {
        // Tránh kết nối với chính mình hoặc kết nối trùng lặp
        if (peerUsername === myUsername || peerConnections[peerUsername]) {
            return;
        }

        console.log(`Tạo kết nối P2P tới ${peerUsername}... (Initiator: ${isInitiator})`);
        const pc = new RTCPeerConnection(RTC_CONFIG);
        peerConnections[peerUsername] = pc;

        // 1. Xử lý khi tìm thấy ICE candidate (đường dẫn mạng)
        pc.onicecandidate = (event) => {
            if (event.candidate) {
                // Gửi candidate này cho peer kia
                sendSignal(peerUsername, event.candidate);
            }
        };

        // 2. Xử lý khi kết nối P2P bị ngắt
        pc.onconnectionstatechange = (event) => {
            if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
                console.log(`Mất kết nối P2P với ${peerUsername}.`);
                pc.close();
                delete peerConnections[peerUsername];
            }
        };

        // 3. Xử lý Data Channel
        if (isInitiator) {
            // Người gọi: Tạo data channel
            const dataChannel = pc.createDataChannel("chat");
            setupDataChannelEvents(dataChannel, peerUsername);
            pc.dataChannel = dataChannel; // Lưu lại để dùng
        } else {
            // Người nhận: Lắng nghe data channel được tạo
            pc.ondatachannel = (event) => {
                const dataChannel = event.channel;
                setupDataChannelEvents(dataChannel, peerUsername);
                pc.dataChannel = dataChannel; // Lưu lại
            };
        }

        return pc;
    }

    /**
     * Gán các sự kiện (onopen, onmessage) cho Data Channel
     */
    function setupDataChannelEvents(dataChannel, peerUsername) {
        dataChannel.onopen = () => {
            console.log(`Kênh Data Channel với ${peerUsername} đã MỞ!`);
            addMessageToChat("System", `Đã kết nối P2P với ${peerUsername}.`);
        };

        dataChannel.onmessage = (event) => {
            // TIN NHẮN P2P ĐÃ ĐẾN!
            const msgData = JSON.parse(event.data);
            onP2PMessageReceived(msgData.from, msgData.msg);
        };

        dataChannel.onclose = () => {
            console.log(`Kênh Data Channel với ${peerUsername} đã ĐÓNG.`);
        };
    }

    /**
     * [API MỚI] Lấy danh sách peer và BẮT ĐẦU kết nối P2P
     */
    async function getPeersAndInitiateP2P(channelName) {
        try {
            const response = await fetch('/channels/get-peers', {
                method: 'POST',
                body: JSON.stringify({ channel_name: channelName }),
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();

            if (data.status === 'success') {
                updateUserListUI(data.peers);

                // CHUẨN BỊ P2P:
                data.peers.forEach(async (peer) => {
                    // Chỉ người "gọi" (có username > peer) mới tạo offer
                    // để tránh cả hai cùng tạo offer
                    const isInitiator = myUsername > peer.username;

                    if (!peerConnections[peer.username] && peer.username !== myUsername) {
                        const pc = createPeerConnection(peer.username, isInitiator);

                        // Nếu là người "gọi", tạo và gửi offer
                        if (isInitiator) {
                            try {
                                const offer = await pc.createOffer();
                                await pc.setLocalDescription(offer);
                                sendSignal(peer.username, offer); // Gửi offer
                            } catch (e) {
                                console.error(`Lỗi tạo offer tới ${peer.username}:`, e);
                            }
                        }
                    }
                });
            }
        } catch (e) {
            console.error("Lỗi lấy danh sách peer:", e);
        }
    }


    // ================================================
    // === GIAI ĐOẠN 3: GỬI/NHẬN TIN NHẮN ===
    // ================================================

    /**
     * Gửi tin nhắn (đã sửa để dùng P2P)
     */
    function handleSendMessage() {
        const message = messageInput.value;
        if (message.trim() === "") return;

        addMessageToChat(myUsername, message); // Hiển thị tin nhắn của mình
        messageInput.value = ""; // Xóa input

        // LOGIC GỬI P2P (Dùng WebRTC Data Channels)
        const messagePayload = JSON.stringify({
            from: myUsername,
            msg: message
        });

        // Lặp qua tất cả các kết nối P2P và gửi
        for (const username in peerConnections) {
            const pc = peerConnections[username];
            if (pc.dataChannel && pc.dataChannel.readyState === 'open') {
                try {
                    pc.dataChannel.send(messagePayload);
                } catch (e) {
                    console.error(`Lỗi gửi P2P tới ${username}:`, e);
                }
            }
        }
    }

    // Hàm nhận tin nhắn P2P (được gọi bởi Data Channel)
    function onP2PMessageReceived(user, message) {
        addMessageToChat(user, message);
    }

    /**
     * Hiển thị tin nhắn lên giao diện
     */
    function addMessageToChat(user, message) {
        const msgDiv = document.createElement("div");
        msgDiv.innerHTML = `<strong>${escapeHTML(user)}:</strong> ${escapeHTML(message)}`;
        chatBoxUI.appendChild(msgDiv);
        chatBoxUI.scrollTop = chatBoxUI.scrollHeight; // Tự cuộn
    }

    function escapeHTML(str) {
        return str.replace(/[&<>"']/g, function (match) {
            return {
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
            }[match];
        });
    }

    // --- KHỞI CHẠY ỨNG DỤNG ---
    async function main() {
        addMessageToChat("System", `Đang đăng nhập với tên ${myUsername}...`);

        await registerWithTracker();
        await joinChannel(CURRENT_CHANNEL);

        // Bắt đầu gửi heartbeat (mỗi 30 giây)
        sendHeartbeat();
        setInterval(sendHeartbeat, 30000);

        // Lấy danh sách peer VÀ bắt đầu kết nối P2P (mỗi 10 giây)
        getPeersAndInitiateP2P(CURRENT_CHANNEL);
        setInterval(() => getPeersAndInitiateP2P(CURRENT_CHANNEL), 10000);

        // Bắt đầu polling để NHẬN tín hiệu P2P (mỗi 2 giây)
        setInterval(fetchSignals, 2000);

        // Gán sự kiện cho nút Gửi
        sendButton.onclick = handleSendMessage;
        messageInput.addEventListener("keyup", (e) => e.key === "Enter" && handleSendMessage());

        addMessageToChat("System", "Đã kết nối! Đang tìm kiếm các peer khác...");
    }

    main();
});