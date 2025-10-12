import socket
import threading
import json
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000
MAX_CLIENTS = 3  

_assigned_ids = set()                    
_assigned_ids_lock = threading.Lock()

clients_cache = {}
clients_cache_lock = threading.Lock()

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

def recvline(conn):
    buf = b""
    while b"\n" not in buf:
        try:
            chunk = conn.recv(1024)
        except ConnectionError:
            return None
        if not chunk:
            return buf.decode(errors="ignore") if buf else None
        buf += chunk
    return buf.decode(errors="ignore").splitlines()[0]

def sendline(conn, s: str):
    try:
        conn.sendall((s + "\n").encode())
    except Exception:
        pass

def sendpayload(conn, payload: str):
    data = payload.encode()
    header = f"STATUS {len(data)}"
    sendline(conn, header)       
    try:
        conn.sendall(data)    
    except Exception:
        pass

def try_assign_client_id(addr):
    with _assigned_ids_lock:
        if len(_assigned_ids) >= MAX_CLIENTS:
            return None
        i = 1
        while i in _assigned_ids:
            i += 1
        _assigned_ids.add(i)
        return f"Client{i:02d}"

def release_client_id(name: str):
    if not name:
        return
    try:
        num = int(name.replace("Client", ""))
    except Exception:
        return
    with _assigned_ids_lock:
        _assigned_ids.discard(num)

def record_connect(name: str, addr):
    with clients_cache_lock:
        clients_cache[name] = {
            "addr": addr,
            "connected_at": now_str(),
            "disconnected_at": None,
        }

def record_disconnect(name: str):
    with clients_cache_lock:
        info = clients_cache.get(name)
        if info and not info.get("disconnected_at"):
            info["disconnected_at"] = now_str()

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

def handle_client(conn, addr):
    assigned_name = try_assign_client_id(addr)
    if assigned_name is None:
        sendline(conn, f"BUSY: Server is full (3 clients max reached)")
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()
        return

    # Handshake
    sendline(conn, f"NAME? {assigned_name}")
    line = recvline(conn)
    if not line or not line.startswith("NAME "):
        release_client_id(assigned_name)
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()
        return

    record_connect(assigned_name, addr)

    try:
        while True:
            msg = recvline(conn)
            if msg is None:
                break

            low = msg.strip().lower()
            if low == "exit":
                sendline(conn, "EXIT")
                break
            elif low == "status":
                payload = format_status_json()
                sendpayload(conn, payload)
            else:
                # ACK response
                sendline(conn, f"{msg} ACK")
    finally:
        record_disconnect(assigned_name)
        release_client_id(assigned_name)
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()

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
                print("\n[SERVER] Shutting down.")
                break
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()

if __name__ == "__main__":
    main()
