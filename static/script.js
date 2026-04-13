let socket = null;
let username = "";

const usernameInput = document.getElementById("username");
const connectBtn = document.getElementById("connectBtn");
const disconnectBtn = document.getElementById("disconnectBtn");
const statusEl = document.getElementById("status");
const messagesEl = document.getElementById("messages");
const bidButtons = document.querySelectorAll(".bid-button:not(.custom-bid-btn)");
const customBidBtns = document.querySelectorAll(".custom-bid-btn");
const quickUserButtons = document.querySelectorAll(".quick-username");

// Local state for items
const items = {
    laptop: { highestBid: 0, highestBidder: null, status: "Active" },
    phone: { highestBid: 0, highestBidder: null, status: "Active" },
    headphones: { highestBid: 0, highestBidder: null, status: "Active" },
};

function setStatus(text, type) {
    statusEl.textContent = text;
    statusEl.className = `status ${type}`;
}

function setConnectedState(connected) {
    connectBtn.disabled = connected;
    disconnectBtn.disabled = !connected;
    usernameInput.disabled = connected;
    quickUserButtons.forEach(b => b.disabled = connected);

    // Show/hide forfeit buttons based on connection state
    document.querySelectorAll(".forfeit-btn").forEach(btn => {
        btn.style.display = connected ? "inline-block" : "none";
    });
}

function appendMessage(text) {
    if (!text || !messagesEl) return;
    const line = document.createElement("div");
    line.className = "message-line";
    line.textContent = text;
    messagesEl.appendChild(line);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function updateItemUI() {
    ["laptop", "phone", "headphones"].forEach((key) => {
        const data = items[key];
        const bidEl = document.querySelector(`[data-item="${key}"][data-role="bid"]`);
        const bidderEl = document.querySelector(`[data-item="${key}"][data-role="bidder"]`);
        const badgeEl = document.querySelector(`[data-item="${key}"][data-role="status"]`);
        const cardEl = document.querySelector(`.item-card[data-item="${key}"]`);
        const forfeitBtn = document.querySelector(`.forfeit-btn[data-item="${key}"]`);

        if (bidEl) bidEl.textContent = data.highestBid.toString();
        if (bidderEl) bidderEl.textContent = data.highestBidder || "–";
        if (badgeEl) {
            badgeEl.textContent = data.status;
            badgeEl.className = `badge ${data.status !== "Active" ? "badge-ended" : ""}`;
        }
        if (cardEl) {
            cardEl.classList.toggle("item-card-leader", !!data.highestBidder && data.highestBidder === username);
        }

        // Show forfeit button only if this user holds the highest bid
        if (forfeitBtn) {
            const isLeader = data.highestBidder === username && socket && socket.readyState === WebSocket.OPEN;
            forfeitBtn.style.display = isLeader ? "inline-block" : "none";
        }
    });
}

function prettyItemName(key) {
    return key.charAt(0).toUpperCase() + key.slice(1);
}

function parseServerLine(line) {
    const trimmed = line.trim();
    if (!trimmed) return;

    // Snapshot: "laptop | Highest Bid: 0 | Time Left: 60 sec"
    if (trimmed.includes("| Highest Bid:")) {
        const parts = trimmed.split("|");
        const item = parts[0].trim().toLowerCase();
        const bidMatch = parts[1].match(/Highest Bid:\s*(\d+)/i);
        const bidderMatch = parts[2] && parts[2].match(/Bidder:\s*(.+)/i);
        if (items[item] && bidMatch) {
            items[item].highestBid = Math.max(items[item].highestBid, parseInt(bidMatch[1], 10));
            if (bidderMatch) {
                const val = bidderMatch[1].trim();
                items[item].highestBidder = val === "None" ? null : val;
            }
            updateItemUI();
        }
        return;
    }

    // Bid confirmation: "Name bids 100 on laptop"
    if (trimmed.includes(" bids ") && trimmed.includes(" on ")) {
        const parts = trimmed.split(" ");
        const bidderName = parts[0];
        const amount = parseInt(parts[2], 10);
        const item = parts[4].toLowerCase();
        if (items[item]) {
            items[item].highestBid = amount;
            items[item].highestBidder = bidderName;
            updateItemUI();
            appendMessage(`${bidderName} placed a bid of ₹${amount} on ${prettyItemName(item)}`);
        }
        return;
    }

    // Forfeit: "Name forfeited their bid on laptop"
    if (trimmed.includes("forfeited their bid on")) {
        const parts = trimmed.split(" ");
        const forfeiter = parts[0];
        const item = parts[parts.length - 1].toLowerCase();
        if (items[item]) {
            items[item].highestBid = 0;
            items[item].highestBidder = null;
            updateItemUI();
            appendMessage(`${forfeiter} forfeited their bid on ${prettyItemName(item)}`);
        }
        return;
    }

    // Generic messages
    if (trimmed.includes("joined") || trimmed.includes("left") || trimmed.includes("disconnected") ||
        trimmed.includes("Winner") || trimmed.includes("ended") || trimmed.includes("retained")) {
        if (trimmed.startsWith("Auction ended for")) {
            const item = trimmed.split(" ")[3].replace(".", "").toLowerCase();
            if (items[item]) items[item].status = "Ended";
            updateItemUI();
        }
        appendMessage(trimmed);
        return;
    }

    // Catch errors
    if (trimmed.startsWith("Bid too low") || trimmed.startsWith("Invalid") ||
        trimmed.startsWith("Auction already finished") || trimmed.startsWith("You don't hold") ||
        trimmed.startsWith("Usage:")) {
        appendMessage(`Server: ${trimmed}`);
    }
}

connectBtn.addEventListener("click", () => {
    username = usernameInput.value.trim();
    if (!username) return alert("Please enter a username.");

    const wsUrl = `ws://${window.location.hostname}:8080/ws/client?username=${encodeURIComponent(username)}`;
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        setStatus("Connected", "status-connected");
        setConnectedState(true);
    };

    socket.onmessage = (event) => {
        event.data.split("\n").forEach(parseServerLine);
    };

    socket.onclose = () => {
        setStatus("Disconnected", "status-disconnected");
        setConnectedState(false);
        updateItemUI();
    };

    socket.onerror = () => setStatus("Error", "status-error");
});

disconnectBtn.addEventListener("click", () => {
    if (socket) {
        socket.send("exit");
        socket.close();
    }
});

function sendBid(item, amount) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return alert("Connect first!");
    socket.send(`${item} ${amount}`);
}

function sendForfeit(item) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return alert("Connect first!");
    if (!confirm(`Are you sure you want to forfeit your bid on ${prettyItemName(item)}?`)) return;
    socket.send(`forfeit ${item}`);
}

bidButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        const item = btn.getAttribute("data-item");
        const increment = parseInt(btn.getAttribute("data-increment"), 10);
        const newBid = items[item].highestBid + increment;

        items[item].highestBid = newBid;
        updateItemUI();

        sendBid(item, newBid);
    });
});

customBidBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        const item = btn.getAttribute("data-item");
        const input = document.querySelector(`.custom-bid-input[data-item="${item}"]`);
        const val = parseInt(input.value, 10);
        if (isNaN(val) || val <= items[item].highestBid) {
            return alert("Enter a bid higher than the current price.");
        }
        items[item].highestBid = val;
        updateItemUI();
        sendBid(item, val);
        input.value = "";
    });
});

// Forfeit buttons
document.querySelectorAll(".forfeit-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        const item = btn.getAttribute("data-item");
        sendForfeit(item);
    });
});

quickUserButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        usernameInput.value = btn.getAttribute("data-name");
    });
});

updateItemUI();