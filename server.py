"""

* CP372 Programming ASGMT - Fall 2025
* server.py
* Karl Richter | rich1728@mylaurier.ca | 169061728
* 
* 10/20/2025

"""


import socket
import threading
import json
from datetime import datetime
from pathlib import Path

HOST = "127.0.0.1"   
PORT = 5000          
MAX_CLIENTS = 3      # maximum simultaneous clients allowed

# Directory used to store files served by the server
REPO_DIR = Path(__file__).with_name("repo")

# Track allocated numeric client IDs
_assigned_ids = set()
_assigned_ids_lock = threading.Lock()

# This lets the "status" command show connect/disconnect times
clients_cache = {}
clients_cache_lock = threading.Lock()

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

def recvline(conn):
    # Read bytes until a newline or EOF; return the first decoded line or None.
    # We return partial buffered data if peer closes mid-line so short final
    # messages aren't lost during shutdown.
    buf = b""
    while b"\n" not in buf:
        try:
            chunk = conn.recv(1024)
        except ConnectionError:
            # treat socket errors as EOF for our simple protocol
            return None
        # connection closed -> return any buffered text or None
        if not chunk:
            return buf.decode(errors="ignore") if buf else None
        buf += chunk
    # decode and return the first line only
    return buf.decode(errors="ignore").splitlines()[0]

def sendline(conn, s: str):
    try:
        conn.sendall((s + "\n").encode())
    except Exception:
        pass

def send_json(conn, tag: str, obj):
    # Send a length-prefixed JSON payload: "<tag> <len>\\n<payload bytes>"
    data = json.dumps(obj, indent=4).encode()
    sendline(conn, f"{tag} {len(data)}")
    try:
        conn.sendall(data)
    except Exception:
        pass

def try_assign_client_id():
    # Allocate the smallest unused numeric id starting at 1, or return None
    with _assigned_ids_lock:
        if len(_assigned_ids) >= MAX_CLIENTS:
            return None
        i = 1
        while i in _assigned_ids:
            i += 1
        _assigned_ids.add(i)
        return f"Client{i:02d}"

def release_client_id(name: str):
    # Release a numeric id so it can be reused
    if not name:
        return
    try:
        num = int(name.replace("Client", ""))
    except Exception:
        return
    with _assigned_ids_lock:
        _assigned_ids.discard(num)

def record_connect(name: str, addr):
    # Store address and connection timestamp for status reporting.
    with clients_cache_lock:
        clients_cache[name] = {
            "addr": addr,
            "connected_at": now_str(),
            "disconnected_at": None,
        }

def record_disconnect(name: str):
    # Mark disconnect time if not already set so status shows session end.
    with clients_cache_lock:
        info = clients_cache.get(name)
        if info and not info.get("disconnected_at"):
            info["disconnected_at"] = now_str()

def format_status_json():
    # Build a dict suitable for JSON export. Sort keys by numeric id so
    # Client01 appears before Client02 in the output.
    with clients_cache_lock:
        def keyfunc(k):
            try:
                return int(k.replace("Client", ""))
            except Exception:
                return k
        out = {}
        for name in sorted(clients_cache.keys(), key=keyfunc):
            info = clients_cache[name]
            addr = info.get("addr")
            out.setdefault(name, []).append({
                "address": [addr[0], addr[1]] if addr else None,
                "connected_at": info.get("connected_at"),
                "disconnected_at": info.get("disconnected_at"),
            })
        return out

def ensure_repo():
    # Create the repo directory if it doesn't exist. Keeps file features simple.
    REPO_DIR.mkdir(exist_ok=True)

def list_repo_files():
    # Return non-hidden files in the repo; used by the "list" command.
    ensure_repo()
    try:
        return [p.name for p in sorted(REPO_DIR.iterdir())
                if p.is_file() and not p.name.startswith(".")]
    except FileNotFoundError:
        return []

def safe_open_from_repo(name: str):
    # Open a file from repo safely:
    if not name or "/" in name or "\\" in name:
        return None, None
    p = (REPO_DIR / name).resolve()
    root = REPO_DIR.resolve()
    if not (p.exists() and p.is_file() and p.parent == root):
        return None, None
    try:
        f = p.open("rb")
        return f, p.stat().st_size
    except Exception:
        return None, None

def handle_client(conn, addr):
    # Per-connection handler run in its own thread.
    assigned = try_assign_client_id()
    if assigned is None:
        # Server full: let the client know and close the write side so it sees EOF.
        sendline(conn, f"BUSY: Server is full ({MAX_CLIENTS} clients max reached)")
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()
        return

    # Handshake: server proposes NAME? ClientNN and expects "NAME ClientNN".
    sendline(conn, f"NAME? {assigned}")
    hello = recvline(conn)
    if not hello or not hello.startswith("NAME "):
        # Handshake failed: release id and close connection.
        release_client_id(assigned)
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()
        return

    # Record metadata for status reporting.
    record_connect(assigned, addr)

    try:
        while True:
            msg = recvline(conn)
            if msg is None:
                # client closed connection
                break
            low = msg.strip().lower()

            if low == "exit":
                # client exit: acknowledge and stop handling.
                sendline(conn, "EXIT")
                break

            elif low == "list":
                files = list_repo_files()
                line = "List of files: " + (", ".join(files) if files else "(empty)")
                sendline(conn, line)

            elif low.startswith("print "):
                # Serve raw file bytes after a "FILE <name> <size>" header.
                req_name = msg.strip()[6:].strip()
                f, size = safe_open_from_repo(req_name)
                if not f:
                    sendline(conn, "ERROR: File not found or invalid name")
                else:
                    sendline(conn, f"FILE {req_name} {size}")
                    with f:
                        # stream file in chunks so we don't load entire file into memory
                        while True:
                            chunk = f.read(64 * 1024)
                            if not chunk:
                                break
                            try:
                                conn.sendall(chunk)
                            except Exception:
                                # on send error just stop transfer
                                break

            elif low == "status":
                # Return JSON describing currently seen clients and their timestamps.
                payload = format_status_json()
                send_json(conn, "STATUS", payload)

            else:
                # Default echo acknowledgement keeps client interactions simple.
                sendline(conn, f"{msg} ACK")
    finally:
        # Ensure we always record disconnect time, free the id, and close socket.
        record_disconnect(assigned)
        release_client_id(assigned)
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()

def main():
    # Server entry point: make sure repo exists, bind socket, and accept connections.
    ensure_repo()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(8)
        print(f"[SERVER] Listening on {HOST}:{PORT} | repo={REPO_DIR}")
        while True:
            try:
                conn, addr = srv.accept()
            except KeyboardInterrupt:
                print("\n[SERVER] Shutting down.")
                break
            # Spawn a thread per client so handlers run independently.
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()

if __name__ == "__main__":
    main()
