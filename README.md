# 🔨 Mini Auction System

A **real-time, multi-client auction platform** built with Python sockets and a modern web dashboard. This project demonstrates core **Computer Networks** concepts — TCP socket programming, multi-threaded server design, client-server communication, and WebSocket bridging.

---

## ✨ Features

| Feature | Description |
|---|---|
| **TCP Auction Server** | Multi-threaded server handling concurrent bidders over raw TCP sockets |
| **Terminal Client** | Lightweight CLI client for placing bids from the command line |
| **Web Dashboard** | Beautiful browser-based UI ("Nexus Auctions") with live bidding cards |
| **Admin Panel** | Dedicated admin view with live logs, client count, and force-stop control |
| **WebSocket Bridge** | FastAPI bridge (`bridge.py`) that translates between TCP and WebSocket protocols |
| **Bid Forfeit** | Bidders can forfeit their highest bid on any item |
| **Auction Logging** | Timestamped log file (`auction_log.txt`) records every event |
| **Results Page** | Auto-generated results summary when all item timers expire |

---

## 🏗️ Architecture

```
┌──────────────┐        TCP         ┌──────────────┐
│ Terminal CLI  │ ◄────────────────► │              │
│  (client.py)  │                    │  TCP Auction  │
└──────────────┘                    │    Server     │
                                    │  (server.py)  │
┌──────────────┐    WebSocket       │              │
│   Browser    │ ◄──────────────►  ┌┤              │
│  Dashboard   │                   ││              │
│ (index.html) │    FastAPI Bridge ││              │
└──────────────┘ ◄──────────────►  └┤              │
                     (bridge.py)    └──────────────┘
```

- **`server.py`** — Core auction engine. Manages items, bids, timers, and broadcasts over TCP.
- **`client.py`** — Simple terminal client that connects, sends bids, and prints server messages.
- **`bridge.py`** — FastAPI + WebSocket server that bridges browser clients to the TCP server.
- **`static/`** — Web frontend (HTML, CSS, JS) for the live auction dashboard and admin panel.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **pip** packages: `fastapi`, `uvicorn`, `websockets`

```bash
pip install fastapi uvicorn websockets
```

### 1. Start the TCP Auction Server

```bash
python server.py
```

The server listens on **port 5000** and waits for clients. The auction timer (60 seconds per item) starts when the first client connects.

### 2. Option A — Connect via Terminal Client

```bash
python client.py
```

Enter your username, then place bids using the format:

```
laptop 500
phone 300
headphones 200
```

**Commands:**
| Command | Description |
|---|---|
| `<item> <amount>` | Place a bid (e.g., `laptop 1000`) |
| `forfeit <item>` | Withdraw your highest bid on an item |
| `exit` | Leave the auction (bids are retained) |

### 2. Option B — Connect via Web Dashboard

Start the bridge server:

```bash
uvicorn bridge:app --reload --port 8000
```

Then open your browser:

| Page | URL |
|---|---|
| **Bidder Dashboard** | [http://localhost:8000](http://localhost:8000) |
| **Admin Panel** | [http://localhost:8000/admin](http://localhost:8000/admin) |
| **Results Page** | [http://localhost:8000/results](http://localhost:8000/results) |

---

## 📁 Project Structure

```
mini-Auction-system/
├── server.py              # TCP auction server (core engine)
├── client.py              # Terminal-based bidding client
├── bridge.py              # FastAPI WebSocket ↔ TCP bridge
├── auction_log.txt        # Auto-generated session log
├── static/
│   ├── index.html         # Bidder dashboard UI
│   ├── admin.html         # Admin monitoring panel
│   ├── results.html       # Final auction results page
│   ├── style.css          # Dashboard styling
│   ├── script.js          # Client-side bidding logic
│   └── admin.js           # Admin panel logic
└── plan-webBasedAuctionDashboard.prompt.md  # Future architecture plan
```

---

## 🎯 Auction Items

The server starts with three default items:

| Item | Starting Bid |
|---|---|
| 💻 Laptop | 0 |
| 📱 Phone | 0 |
| 🎧 Headphones | 0 |

Each item has an independent **60-second countdown timer** that begins when the first client connects.

---

## 🔑 CN Concepts Demonstrated

- **TCP Socket Programming** — Raw `socket` module for reliable, connection-oriented communication
- **Multi-threading** — Concurrent client handling with `threading` and shared-state synchronization via `Lock`
- **Client-Server Model** — Centralized server broadcasting state to multiple connected clients
- **Protocol Design** — Plain-text message protocol over TCP for bidding commands
- **WebSocket Communication** — Real-time bidirectional messaging between browser and server
- **Protocol Bridging** — Translating between TCP and WebSocket protocols via an intermediary

---

## 👥 Team

**Group: Jackfruit**

---

## 📄 License

This project was developed as a Computer Networks mini-project for academic purposes.
