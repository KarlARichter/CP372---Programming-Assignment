import socket
import sys

HOST = "127.0.0.1"
PORT = 5000

def recvline(sock):
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(1024)
        if not chunk:
            return buf.decode(errors="ignore") if buf else None
        buf += chunk
    return buf.decode(errors="ignore").splitlines()[0]

def recvn(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def sendline(sock, s: str):
    sock.sendall((s + "\n").encode())

def main():
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))

        line = recvline(s)
        if not line:
            return
        if line.startswith("BUSY"):
            print(line)
            return
        if not line.startswith("NAME? "):
            return

        assigned = line.split(" ", 1)[1]
        sendline(s, f"NAME {assigned}")
        print(f"You are {assigned}")

        while True:
            try:
                msg = input("Enter message: ")
            except (EOFError, KeyboardInterrupt):
                msg = "exit"

            sendline(s, msg)
            if msg.strip().lower() == "exit":
                break

            resp = recvline(s)
            if resp is None:
                break

            if resp.startswith("STATUS "):
                parts = resp.split()
                if len(parts) == 2 and parts[1].isdigit():
                    n = int(parts[1])
                    payload = recvn(s, n)
                    if payload is None:
                        print("Server response: <truncated>")
                        break
                    print("Server response:", payload.decode(errors="ignore"))
                else:
                    print("Server response:", resp)
                continue

            print("Server response:", resp)

if __name__ == "__main__":
    main()
