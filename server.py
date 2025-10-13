import socket
import threading
import json
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000
MAX_CLIENTS = 3  

# Track numeric client ids that are currently assigned (e.g. {1,2} means Client01 & Client02 taken)
_assigned_ids = set()                    
_assigned_ids_lock = threading.Lock()

clients_cache = {}
clients_cache_lock = threading.Lock()

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

# Read a single newline-terminated line from the connection.
# Returns None on connection closed with no buffered data, otherwise returns the line (no newline).
def recvline(conn):
    buf = b""
    while b"\n" not in buf:
        try:
            chunk = conn.recv(1024)
        except ConnectionError:
            return None
        if not chunk:
            # return any buffered data (decoded) or None if none
            return buf.decode(errors="ignore") if buf else None
        buf += chunk
    # decode and return the first line
    return buf.decode(errors="ignore").splitlines()[0]

# Send a single-line response terminated by newline. Exceptions are caught to avoid crashing handler.
def sendline(conn, s: str):
    try:
        conn.sendall((s + "\n").encode())
    except Exception:
        pass

# Send a multi-byte payload preceded by a "STATUS <len>" header.
# The client expects the header line, then exactly <len> bytes follow.
def sendpayload(conn, payload: str):
    data = payload.encode()
    header = f"STATUS {len(data)}"
    sendline(conn, header)       
    try:
        conn.sendall(data)    
    except Exception:
        pass

# Try to allocate the smallest available numeric client id (1,2,3...).
# Returns "ClientNN" string or None if the server is at capacity.
def try_assign_client_id(addr):
    with _assigned_ids_lock:
        if len(_assigned_ids) >= MAX_CLIENTS:
            return None
        i = 1
        while i in _assigned_ids:
            i += 1
        _assigned_ids.add(i)
        return f"Client{i:02d}"

# Release an assigned client id so it can be reused by new connections.
def release_client_id(name: str):
    if not name:
        return
    try:
        num = int(name.replace("Client", ""))
    except Exception:
        return
    with _assigned_ids_lock:
        _assigned_ids.discard(num)

# Record a client's connect event in the clients_cache with timestamp and address.
def record_connect(name: str, addr):
    with clients_cache_lock:
        clients_cache[name] = {
            "addr": addr,
            "connected_at": now_str(),
            "disconnected_at": None,
        }

# Mark the client's disconnect time in the clients_cache if not already set.
def record_disconnect(name: str):
    with clients_cache_lock:
        info = clients_cache.get(name)
        if info and not info.get("disconnected_at"):
            info["disconnected_at"] = now_str()

# Produce a pretty-printed JSON string representing the clients_cache.
# Keys are sorted by numeric client id when possible so Client01 appears before Client02.
def format_status_json():
    with clients_cache_lock:
        def keyfunc(k):
            try:
                return int(k.replace("Client", ""))
            except Exception:
                return k
        data = {}
        for name in sorted(clients_cache.keys(), key=keyfunc):
            info = clients_cache[name]
            addr = info.get("addr")
            entry = {
                "address": [addr[0], addr[1]] if addr else None,
                "connected_at": info.get("connected_at"),
                "disconnected_at": info.get("disconnected_at")
            }
            data.setdefault(name, []).append(entry)
        return json.dumps(data, indent=4)

# Per-connection handler:
# - Performs handshake to accept assigned name
# - Records connect metadata
# - Processes incoming lines: "exit", "status", or echo-ACK otherwise
# - Ensures cleanup: record disconnect + release id + close socket
def handle_client(conn, addr):
    assigned_name = try_assign_client_id(addr)
    if assigned_name is None:
        # Server full: inform client and close write side
        sendline(conn, f"BUSY: Server is full (3 clients max reached)")
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()
        return

    # Handshake: send NAME? and expect "NAME <assigned>"
    sendline(conn, f"NAME? {assigned_name}")
    line = recvline(conn)
    if not line or not line.startswith("NAME "):
        # Handshake failed: free id and close connection
        release_client_id(assigned_name)
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()
        return

    # Record that this client connected
    record_connect(assigned_name, addr)

    try:
        while True:
            msg = recvline(conn)
            if msg is None:
                # connection closed by client
                break

            low = msg.strip().lower()
            if low == "exit":
                # client requested exit: acknowledge and break loop
                sendline(conn, "EXIT")
                break
            elif low == "status":
                # client requested server status: send JSON payload
                payload = format_status_json()
                sendpayload(conn, payload)
            else:
                # default: echo acknowledgement
                sendline(conn, f"{msg} ACK")
    finally:
        # Cleanup on handler exit: record disconnect time, release id, close socket
        record_disconnect(assigned_name)
        release_client_id(assigned_name)
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()

# Server main loop:
# - Binds, listens, and spawns handler threads for connections.
# - Responds to KeyboardInterrupt to shut down cleanly.
def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(8)
        print(f"Server listening on {HOST}:{PORT}")
        while True:
            try:
                conn, addr = srv.accept()
            except KeyboardInterrupt:
                # allow Ctrl-C to stop the server gracefully
                print("\n[SERVER] Shutting down.")
                break
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()

if __name__ == "__main__":
    main()
