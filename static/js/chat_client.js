// static/js/chat_client.js
// P2P Chat Client với WebRTC và Tracker Server

document.addEventListener("DOMContentLoaded", () => {
    console.log("[chat_client] DOM loaded, bắt đầu khởi tạo...");
    
    // === LẤY CÁC ELEMENT TỪ HTML ===
    const userListUI = document.getElementById("user-list");
    const chatBoxUI = document.getElementById("chat-box");
    const messageInput = document.getElementById("message-input");
    const sendButton = document.getElementById("send-btn");
    const currentUserSpan = document.getElementById("current-user");
    const logoutBtn = document.getElementById("logout-btn");
    const connectionStatus = document.getElementById("connection-status");
    const peerCountSpan = document.getElementById("peer-count");
    const channelListUI = document.getElementById("channel-list");
    const createChannelBtn = document.getElementById("create-channel-btn");
    const channelModal = document.getElementById("channel-modal");
    const newChannelNameInput = document.getElementById("new-channel-name");
    const confirmCreateBtn = document.getElementById("confirm-create-btn");
    const closeModal = document.querySelector(".close");

    // Debug: Kiểm tra các element
    console.log("[chat_client] Elements found:", {
        messageInput: !!messageInput,
        sendButton: !!sendButton,
        createChannelBtn: !!createChannelBtn,
        channelListUI: !!channelListUI
    });

    // Đảm bảo các element hiển thị
    if (messageInput) {
        messageInput.style.display = "block";
        messageInput.disabled = false;
    }
    if (sendButton) {
        sendButton.style.display = "block";
        sendButton.disabled = false;
    }
    if (createChannelBtn) {
        createChannelBtn.style.display = "block";
        createChannelBtn.disabled = false;
    }

    // === KIỂM TRA ĐĂNG NHẬP ===
    // Hàm đọc cookie
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(';').shift().trim();
        }
        return null;
    }

    // Kiểm tra cookie auth trước
    const authCookie = getCookie("auth");
    if (authCookie !== "true") {
        alert("Bạn chưa đăng nhập!");
        window.location.href = '/login.html';
        return;
    }

    // Lấy username từ localStorage hoặc dùng "admin" mặc định
    let myUsername = localStorage.getItem("username");
    if (!myUsername) {
        // Nếu không có trong localStorage, dùng "admin" mặc định
        // (vì chỉ có admin mới đăng nhập được)
        myUsername = "admin";
        localStorage.setItem("username", myUsername);
    }

    currentUserSpan.textContent = myUsername;

    // === CẤU HÌNH ===
    const TRACKER_URL = "http://127.0.0.1:8000"; // Tracker server
    let CURRENT_CHANNEL = "#general";
    const HEARTBEAT_INTERVAL = 30000; // 30 giây
    const PEER_SYNC_INTERVAL = 10000; // 10 giây
    const SIGNAL_POLL_INTERVAL = 2000; // 2 giây

    // WebRTC Configuration
    const RTC_CONFIG = {
        iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' }
        ]
    };

    // State
    const peerConnections = {}; // { username: RTCPeerConnection }
    let dataChannels = {}; // { username: RTCDataChannel }
    let heartbeatInterval = null;
    let peerSyncInterval = null;
    let signalPollInterval = null;

    // === TRACKER API FUNCTIONS ===

    async function trackerRequest(endpoint, method = 'GET', body = null) {
        try {
            const options = {
                method: method,
                headers: { 'Content-Type': 'application/json' }
            };
            if (body) {
                options.body = JSON.stringify(body);
            }
            const response = await fetch(`${TRACKER_URL}${endpoint}`, options);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error(`Tracker request error (${endpoint}):`, error);
            return { status: 'error', message: error.message };
        }
    }

    async function registerWithTracker() {
        const myPeerInfo = {
            username: myUsername,
            ip: "127.0.0.1",
            port: Math.floor(Math.random() * 5000) + 10000
        };
        const result = await trackerRequest('/register-peer', 'POST', myPeerInfo);
        if (result.status === 'success') {
            updateStatus('connected', 'Đã kết nối với Tracker');
        }
        return result;
    }

    async function sendHeartbeat() {
        await trackerRequest('/heartbeat', 'POST', { username: myUsername });
    }

    async function joinChannel(channelName) {
        const result = await trackerRequest('/channels/join', 'POST', {
            username: myUsername,
            channel_name: channelName
        });
        if (result.status === 'success') {
            CURRENT_CHANNEL = channelName;
            updateChannelUI();
            addSystemMessage(`Đã tham gia kênh ${channelName}`);
        }
        return result;
    }

    async function createChannel(channelName) {
        const result = await trackerRequest('/channels/create', 'POST', {
            username: myUsername,
            channel_name: channelName
        });
        if (result.status === 'success') {
            await joinChannel(channelName);
            loadChannels();
        } else {
            alert(result.message || 'Không thể tạo kênh');
        }
        return result;
    }

    async function loadChannels() {
        const result = await trackerRequest('/channels/list', 'GET');
        if (result.status === 'success' && result.channels) {
            channelListUI.innerHTML = '';
            result.channels.forEach(channel => {
                const channelItem = document.createElement('div');
                channelItem.className = 'channel-item';
                if (channel === CURRENT_CHANNEL) {
                    channelItem.classList.add('active');
                }
                channelItem.textContent = channel;
                channelItem.dataset.channel = channel;
                channelItem.onclick = () => switchChannel(channel);
                channelListUI.appendChild(channelItem);
            });
        }
    }

    async function switchChannel(channelName) {
        if (channelName === CURRENT_CHANNEL) return;
        
        // Đóng tất cả kết nối P2P hiện tại
        Object.keys(peerConnections).forEach(username => {
            if (peerConnections[username]) {
                peerConnections[username].close();
                delete peerConnections[username];
            }
        });
        dataChannels = {};

        CURRENT_CHANNEL = channelName;
        updateChannelUI();
        addSystemMessage(`Đã chuyển sang kênh ${channelName}`);
        await joinChannel(channelName);
        getPeersAndInitiateP2P(channelName);
    }

    function updateChannelUI() {
        document.querySelectorAll('.channel-item').forEach(item => {
            if (item.dataset.channel === CURRENT_CHANNEL) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    async function getPeersInChannel(channelName) {
        const result = await trackerRequest('/channels/get-peers', 'POST', {
            channel_name: channelName
        });
        if (result.status === 'success' && result.peers) {
            return result.peers;
        }
        return [];
    }

    async function sendSignal(toUsername, signalData) {
        await trackerRequest('/signal', 'POST', {
            to: toUsername,
            from: myUsername,
            signal: signalData
        });
    }

    async function fetchSignals() {
        const result = await trackerRequest('/get-signals', 'POST', {
            username: myUsername
        });
        if (result.status === 'success' && result.signals) {
            result.signals.forEach(signalMsg => {
                handleSignal(signalMsg.from, signalMsg.signal);
            });
        }
    }

    // === WEBRTC P2P FUNCTIONS ===

    function createPeerConnection(peerUsername, isInitiator = false) {
        if (peerUsername === myUsername || peerConnections[peerUsername]) {
            return null;
        }

        console.log(`Tạo P2P connection tới ${peerUsername} (Initiator: ${isInitiator})`);
        const pc = new RTCPeerConnection(RTC_CONFIG);
        peerConnections[peerUsername] = pc;

        // ICE Candidate handler
        pc.onicecandidate = (event) => {
            if (event.candidate) {
                sendSignal(peerUsername, event.candidate);
            }
        };

        // Connection state handler
        pc.onconnectionstatechange = () => {
            console.log(`Connection state với ${peerUsername}: ${pc.connectionState}`);
            if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
                pc.close();
                delete peerConnections[peerUsername];
                delete dataChannels[peerUsername];
                updatePeerCount();
            }
        };

        // Data Channel setup
        if (isInitiator) {
            const dataChannel = pc.createDataChannel("chat");
            setupDataChannel(dataChannel, peerUsername);
            dataChannels[peerUsername] = dataChannel;
        } else {
            pc.ondatachannel = (event) => {
                const dataChannel = event.channel;
                setupDataChannel(dataChannel, peerUsername);
                dataChannels[peerUsername] = dataChannel;
            };
        }

        return pc;
    }

    function setupDataChannel(dataChannel, peerUsername) {
        dataChannel.onopen = () => {
            console.log(`Data channel với ${peerUsername} đã mở`);
            addSystemMessage(`Đã kết nối P2P với ${peerUsername}`);
            updatePeerCount();
        };

        dataChannel.onmessage = (event) => {
            try {
                const msgData = JSON.parse(event.data);
                addMessageToChat(msgData.from, msgData.msg, false);
            } catch (e) {
                console.error('Lỗi parse message:', e);
            }
        };

        dataChannel.onclose = () => {
            console.log(`Data channel với ${peerUsername} đã đóng`);
            delete dataChannels[peerUsername];
            updatePeerCount();
        };
    }

    async function handleSignal(fromUsername, signal) {
        let pc = peerConnections[fromUsername];

        if (!pc) {
            pc = createPeerConnection(fromUsername, false);
        }

        try {
            if (signal.sdp) {
                await pc.setRemoteDescription(new RTCSessionDescription(signal));
                if (signal.type === 'offer') {
                    const answer = await pc.createAnswer();
                    await pc.setLocalDescription(answer);
                    sendSignal(fromUsername, answer);
                }
            } else if (signal.candidate) {
                await pc.addIceCandidate(new RTCIceCandidate(signal));
            }
        } catch (error) {
            console.error(`Lỗi xử lý signal từ ${fromUsername}:`, error);
        }
    }

    async function getPeersAndInitiateP2P(channelName) {
        const peers = await getPeersInChannel(channelName);
        updateUserList(peers);
        updatePeerCount();

        peers.forEach(async (peer) => {
            if (peer.username === myUsername || peerConnections[peer.username]) {
                return;
            }

            // Chỉ người có username lớn hơn mới tạo offer (tránh duplicate)
            const isInitiator = myUsername > peer.username;
            const pc = createPeerConnection(peer.username, isInitiator);

            if (isInitiator && pc) {
                try {
                    const offer = await pc.createOffer();
                    await pc.setLocalDescription(offer);
                    sendSignal(peer.username, offer);
                } catch (error) {
                    console.error(`Lỗi tạo offer tới ${peer.username}:`, error);
                }
            }
        });
    }

    // === UI UPDATE FUNCTIONS ===

    function updateUserList(peers) {
        userListUI.innerHTML = '';
        peers.forEach(peer => {
            const li = document.createElement('li');
            li.textContent = peer.username;
            if (peer.username === myUsername) {
                li.classList.add('you');
                li.textContent += ' (You)';
            }
            userListUI.appendChild(li);
        });
    }

    function updatePeerCount() {
        const count = Object.keys(dataChannels).filter(
            username => dataChannels[username]?.readyState === 'open'
        ).length;
        peerCountSpan.textContent = `Peers: ${count}`;
    }

    function updateStatus(status, message) {
        connectionStatus.textContent = message;
        connectionStatus.className = `status-indicator ${status}`;
    }

    function addMessageToChat(user, message, isOwn = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isOwn ? 'own' : ''}`;

        const header = document.createElement('div');
        header.className = 'message-header';

        const usernameSpan = document.createElement('span');
        usernameSpan.className = 'message-username';
        usernameSpan.textContent = user;

        const timeSpan = document.createElement('span');
        timeSpan.className = 'message-time';
        timeSpan.textContent = new Date().toLocaleTimeString();

        header.appendChild(usernameSpan);
        header.appendChild(timeSpan);

        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = message;

        messageDiv.appendChild(header);
        messageDiv.appendChild(content);

        chatBoxUI.appendChild(messageDiv);
        chatBoxUI.scrollTop = chatBoxUI.scrollHeight;
    }

    function addSystemMessage(message) {
        const systemDiv = document.createElement('div');
        systemDiv.className = 'system-message';
        systemDiv.innerHTML = `<p>${escapeHTML(message)}</p>`;
        chatBoxUI.appendChild(systemDiv);
        chatBoxUI.scrollTop = chatBoxUI.scrollHeight;
    }

    function escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // === MESSAGE HANDLING ===

    function handleSendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        addMessageToChat(myUsername, message, true);
        messageInput.value = '';

        // Gửi qua tất cả data channels đang mở
        const messagePayload = JSON.stringify({
            from: myUsername,
            msg: message
        });

        Object.keys(dataChannels).forEach(username => {
            const dc = dataChannels[username];
            if (dc && dc.readyState === 'open') {
                try {
                    dc.send(messagePayload);
                } catch (error) {
                    console.error(`Lỗi gửi message tới ${username}:`, error);
                }
            }
        });
    }

    // === EVENT HANDLERS ===
    // (Event handlers sẽ được gán sau khi định nghĩa các hàm, ở cuối file)

    // === INITIALIZATION ===

    async function init() {
        addSystemMessage(`Đang kết nối với Tracker...`);
        
        // Đăng ký với Tracker
        await registerWithTracker();
        
        // Tham gia kênh mặc định
        await joinChannel(CURRENT_CHANNEL);
        
        // Load danh sách kênh
        await loadChannels();
        
        // Bắt đầu heartbeat
        sendHeartbeat();
        heartbeatInterval = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
        
        // Bắt đầu sync peers
        getPeersAndInitiateP2P(CURRENT_CHANNEL);
        peerSyncInterval = setInterval(() => {
            getPeersAndInitiateP2P(CURRENT_CHANNEL);
        }, PEER_SYNC_INTERVAL);
        
        // Bắt đầu poll signals
        signalPollInterval = setInterval(fetchSignals, SIGNAL_POLL_INTERVAL);
        
        addSystemMessage('Đã kết nối! Đang tìm kiếm các peer khác...');
        updateStatus('connected', 'Đã kết nối');
        
        console.log("[chat_client] Init hoàn tất!");
    }

    // Gán event handlers TRƯỚC KHI gọi init()
    // Đảm bảo các handlers được gán ngay cả khi init() có lỗi
    console.log("[chat_client] Gán event handlers...");
    
    // Gán event handlers với kiểm tra null
    if (sendButton && messageInput) {
        console.log("[chat_client] Gán event handlers cho send button và message input");
        sendButton.onclick = handleSendMessage;
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleSendMessage();
            }
        });
    } else {
        console.error("[chat_client] Không tìm thấy sendButton hoặc messageInput!");
    }

    if (logoutBtn) {
        logoutBtn.onclick = () => {
            localStorage.removeItem('username');
            window.location.href = '/index.html';
        };
    }

    if (createChannelBtn) {
        console.log("[chat_client] Gán event handler cho create channel button");
        createChannelBtn.onclick = () => {
            if (channelModal) {
                channelModal.style.display = 'block';
            }
        };
    } else {
        console.error("[chat_client] Không tìm thấy createChannelBtn!");
    }

    // Gán event cho channel items
    if (channelListUI) {
        // Event delegation cho channel items
        channelListUI.addEventListener('click', (e) => {
            const channelItem = e.target.closest('.channel-item');
            if (channelItem && channelItem.dataset.channel) {
                switchChannel(channelItem.dataset.channel);
            }
        });
    }

    if (closeModal) {
        closeModal.onclick = () => {
            if (channelModal) {
                channelModal.style.display = 'none';
            }
        };
    }

    if (confirmCreateBtn && newChannelNameInput) {
        confirmCreateBtn.onclick = async () => {
            let channelName = newChannelNameInput.value.trim();
            if (channelName) {
                if (!channelName.startsWith('#')) {
                    channelName = '#' + channelName;
                }
                await createChannel(channelName);
                if (channelModal) {
                    channelModal.style.display = 'none';
                }
                newChannelNameInput.value = '';
            }
        };
    }

    window.onclick = (event) => {
        if (channelModal && event.target === channelModal) {
            channelModal.style.display = 'none';
        }
    };

    // Gọi init() sau khi đã gán tất cả event handlers
    console.log("[chat_client] Bắt đầu init()...");
    init();
});
