import asyncio
import socket
import threading
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

TCP_HOST = "127.0.0.1"  # existing auction server
TCP_PORT = 5000

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Auction Bridge Server")

# Track connected client websockets for simple status (admin view)
connected_clients = 0
admin_sockets: list[WebSocket] = []


# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index() -> HTMLResponse:
    """Serve the main client page."""
    index_path = STATIC_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")
    return HTMLResponse(content)


@app.get("/admin")
async def admin_page() -> HTMLResponse:
    """Serve the admin page."""
    admin_path = STATIC_DIR / "admin.html"
    content = admin_path.read_text(encoding="utf-8")
    return HTMLResponse(content)


@app.get("/results")
async def results_page() -> HTMLResponse:
    """Serve the final results page."""
    results_path = STATIC_DIR / "results.html"
    content = results_path.read_text(encoding="utf-8")
    return HTMLResponse(content)


def tcp_to_websocket(tcp_sock: socket.socket, websocket: WebSocket, loop: asyncio.AbstractEventLoop) -> None:
    """Background thread: read from TCP server and forward to a browser WebSocket.

    This keeps using the existing plain-text protocol from server.py and does not
    change any message formats.
    """
    try:
        while True:
            try:
                data = tcp_sock.recv(1024)
            except OSError:
                break

            if not data:
                break

            text = data.decode(errors="ignore")

            # Schedule send_text on the FastAPI event loop from this thread
            asyncio.run_coroutine_threadsafe(websocket.send_text(text), loop)
    except Exception:
        # For a teaching project, we keep error handling minimal
        pass
    finally:
        # When TCP ends, close the WebSocket from the loop
        try:
            asyncio.run_coroutine_threadsafe(websocket.close(), loop)
        except RuntimeError:
            # Event loop might already be closed
            pass
        try:
            tcp_sock.close()
        except OSError:
            pass


async def _connect_tcp(websocket: WebSocket, username: str) -> socket.socket | None:
    """Connect to the existing TCP auction server and send the username.

    Returns the connected socket or None on failure.
    """
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp_sock.connect((TCP_HOST, TCP_PORT))
    except OSError:
        await websocket.send_text("Could not connect to auction server. Is server.py running?\n")
        return None

    # Send username automatically as the first message to the TCP server
    try:
        tcp_sock.sendall((username + "\n").encode())
    except OSError:
        await websocket.send_text("Connection to auction server lost.\n")
        try:
            tcp_sock.close()
        except OSError:
            pass
        return None

    return tcp_sock


async def _bridge_loop(websocket: WebSocket, username: str, kind: str) -> None:
    """Shared bridge logic for both client and admin WebSockets."""
    global connected_clients

    await websocket.accept()
    loop = asyncio.get_running_loop()

    # Establish TCP connection
    tcp_sock = await _connect_tcp(websocket, username)
    if tcp_sock is None:
        await websocket.close()
        return

    # If this is a client connection, update count and notify admins
    if kind == "client":
        connected_clients += 1
        # Notify admins in a very simple plain-text format
        for admin_ws in list(admin_sockets):
            try:
                await admin_ws.send_text(f"CONNECTED_CLIENTS {connected_clients}\n")
            except Exception:
                # Drop dead admin sockets lazily
                try:
                    admin_sockets.remove(admin_ws)
                except ValueError:
                    pass
    else:
        # Admin connections are tracked in a list for simple broadcasts
        if websocket not in admin_sockets:
            admin_sockets.append(websocket)

    # Start background thread to forward TCP -> WebSocket
    thread = threading.Thread(
        target=tcp_to_websocket,
        args=(tcp_sock, websocket, loop),
        daemon=True,
    )
    thread.start()

    # Main loop: forward browser messages -> TCP server
    try:
        while True:
            try:
                message = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            # Keep protocol simple: raw text lines, exactly like the terminal client
            try:
                tcp_sock.sendall((message + "\n").encode())
            except OSError:
                break
    finally:
        # Clean up TCP and bookkeeping
        try:
            tcp_sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            tcp_sock.close()
        except OSError:
            pass

        if kind == "client":
            connected_clients = max(connected_clients - 1, 0)
            # Notify admins that client count changed
            for admin_ws in list(admin_sockets):
                try:
                    await admin_ws.send_text(f"CONNECTED_CLIENTS {connected_clients}\n")
                except Exception:
                    try:
                        admin_sockets.remove(admin_ws)
                    except ValueError:
                        pass
        else:
            # Remove admin socket from tracking
            try:
                if websocket in admin_sockets:
                    admin_sockets.remove(websocket)
            except ValueError:
                pass


@app.websocket("/ws/client")
async def client_websocket(websocket: WebSocket) -> None:
    """Client WebSocket bridge -> TCP server.

    Each browser client gets its own TCP connection and uses the original
    plain-text messages (e.g. "laptop 500").
    """
    username = websocket.query_params.get("username") or "Guest"
    await _bridge_loop(websocket, username=username, kind="client")


@app.websocket("/ws/admin")
async def admin_websocket(websocket: WebSocket) -> None:
    """Admin WebSocket bridge -> TCP server.

    Admin also connects to the TCP server (as a regular client) but the
    browser UI formats messages as logs, shows connected client count, and
    provides a simple "Stop Auction" button that sends plain text like "exit".
    """
    # Use a fixed label so it is obvious in the terminal/server logs
    await _bridge_loop(websocket, username="ADMIN", kind="admin")
