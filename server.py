import socket
import threading
import time
import os
from datetime import datetime

HOST = "0.0.0.0"
PORT = 5000
TIMER_DURATION = 60  # seconds

clients = []
lock = threading.Lock()
auction_finished = False
auction_started = False  # Timer only starts when first client connects

# Default items
auction_items = {
    "laptop":     {"highest_bid": 0, "bidder": None, "time_left": TIMER_DURATION},
    "phone":      {"highest_bid": 0, "bidder": None, "time_left": TIMER_DURATION},
    "headphones": {"highest_bid": 0, "bidder": None, "time_left": TIMER_DURATION}
}

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auction_log.txt")

def log(message):
    """Write a timestamped line to the log file and print to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Log write error: {e}")


# ── Broadcast ──────────────────────────────────────────────────────────────────
def broadcast(message):
    log(f"BROADCAST: {message}")
    for c in clients:
        try:
            c.send((message + "\n").encode())
        except:
            pass


# ── Timer ──────────────────────────────────────────────────────────────────────
def item_timer(item):
    global auction_finished

    # Wait until auction has started (first client connected)
    while True:
        with lock:
            if auction_started:
                break
        time.sleep(0.5)

    while auction_items[item]["time_left"] > 0:
        time.sleep(1)
        with lock:
            auction_items[item]["time_left"] -= 1

    winner = auction_items[item]["bidder"]
    bid = auction_items[item]["highest_bid"]

    if winner:
        broadcast(f"Auction ended for {item}. Winner: {winner} with bid {bid}")
    else:
        broadcast(f"Auction ended for {item}. No bids placed.")

    with lock:
        all_done = all(v["time_left"] <= 0 for v in auction_items.values())
        if all_done and not auction_finished:
            auction_finished = True
            time.sleep(1)
            results = get_auction_results()
            log("FINAL RESULTS:\n" + results)
            broadcast(results)


# ── Helpers ────────────────────────────────────────────────────────────────────
def show_items():
    message = ""
    for item, data in auction_items.items():
        bidder = data['bidder'] if data['bidder'] else "None"
        message += f"{item} | Highest Bid: {data['highest_bid']} | Bidder: {bidder} | Time Left: {data['time_left']} sec\n"
    return message


def get_auction_results():
    message = "\n=== AUCTION RESULTS ===\n"
    for item, data in auction_items.items():
        if data["bidder"]:
            message += f"{item}: Winner - {data['bidder']} | Final Bid: {data['highest_bid']}\n"
        else:
            message += f"{item}: No bids placed\n"
    message += "=======================\n"
    return message


# ── Client handler ─────────────────────────────────────────────────────────────
def handle_client(conn, addr):
    global auction_started
    log(f"Connection from {addr}")
    name = "Guest"

    try:
        data = conn.recv(1024).decode().strip()
        if not data:
            conn.close()
            return

        name = data
        log(f"{name} joined from {addr}")

        # Start the timer the moment the first real client connects
        with lock:
            if not auction_started:
                auction_started = True
                log("Auction timer started (first client connected)")

        broadcast(f"{name} joined the auction")
        conn.send(show_items().encode())

        while True:
            data = conn.recv(1024).decode().strip()

            if not data:
                broadcast(f"{name} disconnected (bids retained)")
                log(f"{name} dropped connection — bids retained")
                break

            if data.lower() == "exit":
                broadcast(f"{name} left the auction (bids retained)")
                log(f"{name} exited gracefully — bids retained")
                break

            # ADMIN ONLY: force stop
            if data.lower() == "stop_auction_now" and name == "ADMIN":
                log("ADMIN force-stopped the auction")
                with lock:
                    for item in auction_items:
                        auction_items[item]["time_left"] = 0
                continue

            parts = data.split()

            # FORFEIT command
            if parts[0].lower() == "forfeit":
                if len(parts) == 2:
                    item = parts[1].lower()
                    with lock:
                        if item in auction_items and auction_items[item]["bidder"] == name:
                            auction_items[item]["highest_bid"] = 0
                            auction_items[item]["bidder"] = None
                            broadcast(f"{name} forfeited their bid on {item}")
                            log(f"{name} forfeited bid on {item}")
                        else:
                            conn.send(f"You don't hold the highest bid on {item}\n".encode())
                else:
                    conn.send("Usage: forfeit <item>\n".encode())
                continue

            if len(parts) != 2:
                continue

            item = parts[0].lower()
            try:
                bid = int(parts[1])
            except ValueError:
                continue

            if item not in auction_items:
                conn.send(f"Invalid item: {item}\n".encode())
                continue

            with lock:
                if auction_items[item]["time_left"] <= 0:
                    conn.send(f"Auction already finished for {item}\n".encode())
                    continue

                if bid > auction_items[item]["highest_bid"]:
                    auction_items[item]["highest_bid"] = bid
                    auction_items[item]["bidder"] = name
                    broadcast(f"{name} bids {bid} on {item}")
                    log(f"BID: {name} bids {bid} on {item}")
                else:
                    conn.send(f"Bid too low. Current highest bid: {auction_items[item]['highest_bid']}\n".encode())

    except Exception as e:
        log(f"Error with {name}: {e}")
        broadcast(f"{name} disconnected (bids retained)")

    finally:
        if conn in clients:
            clients.remove(conn)
        conn.close()
        log(f"{name} disconnected")


# ── Start ──────────────────────────────────────────────────────────────────────
def start_server():
    # Fresh log file each run
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== Auction Session Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    log(f"Auction Server Running on port {PORT}")
    log(f"Logging to: {LOG_FILE}")

    for item in auction_items:
        threading.Thread(target=item_timer, args=(item,), daemon=True).start()

    while True:
        conn, addr = server.accept()
        clients.append(conn)
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    start_server()