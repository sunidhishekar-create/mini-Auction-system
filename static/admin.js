let adminSocket = null;

const stopAuctionBtn = document.getElementById("stopAuctionBtn");
const adminLogsEl = document.getElementById("adminLogs");

// Simple state mirror for the admin view
const items = {
    laptop: { bid: 0, bidder: null },
    phone: { bid: 0, bidder: null },
    headphones: { bid: 0, bidder: null },
};

function prettyItemName(key) {
    return key.charAt(0).toUpperCase() + key.slice(1);
}

function resetAdminState() {
    items.laptop = { bid: 0, bidder: null };
    items.phone = { bid: 0, bidder: null };
    items.headphones = { bid: 0, bidder: null };
    if (adminLogsEl) {
        adminLogsEl.innerHTML = "";
    }
    updateStateUI();
}

function appendAdminLog(text) {
    if (!text || !adminLogsEl) return;
    const line = document.createElement("div");
    line.className = "log-line";
    line.textContent = text;
    adminLogsEl.appendChild(line);
    adminLogsEl.scrollTop = adminLogsEl.scrollHeight;
}

function persistResults() {
    try {
        localStorage.setItem("auctionResults", JSON.stringify(items));
    } catch (e) {
        // ignore storage errors
    }
}

function updateStateUI() {
    ["laptop", "phone", "headphones"].forEach((key) => {
        const data = items[key];
        const bidEl = document.querySelector(`[data-item="${key}"][data-role="bid"]`);
        const bidderEl = document.querySelector(`[data-item="${key}"][data-role="bidder"]`);

        if (bidEl) bidEl.textContent = data.bid.toString();
        if (bidderEl) bidderEl.textContent = data.bidder || "No bids";
    });
}

function parseAdminLine(line) {
    const trimmed = line.trim();
    if (!trimmed) return;

    // Snapshot: "laptop | Highest Bid: 100 | Bidder: Gagan | Time Left: 600 sec"
    if (trimmed.includes("| Highest Bid:")) {
        const parts = trimmed.split("|");
        const item = parts[0].trim().toLowerCase();
        if (items[item]) {
            const bidMatch = parts[1].match(/Highest Bid:\s*(\d+)/i);
            const bidderMatch = parts[2].match(/Bidder:\s*(.+)/i);
            if (bidMatch) items[item].bid = parseInt(bidMatch[1], 10) || 0;
            if (bidderMatch) {
                const bidderVal = bidderMatch[1].trim();
                items[item].bidder = (bidderVal === "None") ? null : bidderVal;
            }
            updateStateUI();
        }
        return;
    }

    // Bid lines: "Gagan bids 600 on laptop"
    if (trimmed.includes(" bids ") && trimmed.includes(" on ")) {
        const parts = trimmed.split(" ");
        if (parts.length >= 5) {
            const bidderName = parts[0];
            const amount = parseInt(parts[2], 10);
            const item = parts[4].toLowerCase();
            if (items[item]) {
                items[item].bid = amount;
                items[item].bidder = bidderName;
                updateStateUI();
                appendAdminLog(`${bidderName} bids ₹${amount} on ${prettyItemName(item)}`);
            }
        }
        return;
    }

    // Forfeit lines
    if (trimmed.includes("forfeited their bid on")) {
        const parts = trimmed.split(" ");
        const item = parts[parts.length - 1].toLowerCase();
        if (items[item]) {
            items[item].bid = 0;
            items[item].bidder = null;
            updateStateUI();
            appendAdminLog(trimmed);
        }
        return;
    }

    // Generic logs
    if (trimmed.includes("joined") || trimmed.includes("left") || trimmed.includes("disconnected") ||
        trimmed.includes("Auction ended") || trimmed.includes("retained")) {
        appendAdminLog(trimmed);

        if (trimmed.includes("AUCTION RESULTS")) {
            persistResults();
        }
    }
}

function handleAdminMessage(text) {
    text.split("\n").forEach(parseAdminLine);
}

function connectAdmin() {
    if (adminSocket && adminSocket.readyState === WebSocket.OPEN) return;

    resetAdminState();
    const wsUrl = `ws://${window.location.hostname}:8080/ws/admin`;
    adminSocket = new WebSocket(wsUrl);

    adminSocket.onmessage = (event) => {
        handleAdminMessage(event.data);
    };

    adminSocket.onclose = () => {
        stopAuctionBtn.disabled = true;
    };

    adminSocket.onopen = () => {
        stopAuctionBtn.disabled = false;
    };
}

connectAdmin();

stopAuctionBtn.addEventListener("click", () => {
    if (!adminSocket || adminSocket.readyState !== WebSocket.OPEN) return;

    adminSocket.send("stop_auction_now");

    setTimeout(() => {
        persistResults();
        window.location.href = "/results";
    }, 500);
});

updateStateUI();