import socket
import threading
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5000
MAX_CLIENTS = 3  

_assigned_ids = set()                   
_assigned_ids_lock = threading.Lock()

clients_cache = {}
clients_cache_lock = threading.Lock()

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def recvline(conn):
    buf = b""
    while b"\n" not in buf:
        try:
            chunk = conn.recv(1024)
        except ConnectionError:
            return None
        if not chunk:
            return None
        buf += chunk
    return buf.decode(errors="ignore").rstrip("\r\n")

def sendline(conn, s: str):
    try:
        conn.sendall((s + "\n").encode())
    except Exception:
        pass

def try_assign_client_id(addr):
    """Return assigned name like 'Client01' or None if at capacity."""
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

def format_status():
    with clients_cache_lock, _assigned_ids_lock:
        lines = []
        lines.append(f"=== Server Status @ {now_str()} ===")
        lines.append(f"Active: {len(_assigned_ids)}/{MAX_CLIENTS}")

        for name in sorted(clients_cache.keys()):
            info = clients_cache[name]
            active = "(active)" if int(name.replace('Client','')) in _assigned_ids else "(closed)"
            addr = info.get("addr")
            lines.append(f"{name:>8} {active} | addr={addr} | start={info.get('connected_at')} | end={info.get('disconnected_at')}")
        return "\n".join(lines)

def handle_client(conn, addr):
    assigned_name = try_assign_client_id(addr)
    if assigned_name is None:
        sendline(conn, f"Server is currently at capacity ({MAX_CLIENTS}).")
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        conn.close()
        return

    sendline(conn, f"NAME? {assigned_name}")
    line = recvline(conn)
    if not line or not line.startswith("NAME "):
        release_client_id(assigned_name)
        try:
            conn.shutdown(socket.SHUT_RDWR)
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

            #exit msg
            if low == "exit":
                sendline(conn, "EXIT")
                break
            elif low == "status":
                sendline(conn, format_status())
            else:
                # ACK response
                sendline(conn, f"Server response: {msg} ACK")
    finally:
        record_disconnect(assigned_name)
        release_client_id(assigned_name)
        try:
            conn.shutdown(socket.SHUT_RDWR)
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
