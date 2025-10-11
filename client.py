import socket
import sys

HOST = "127.0.0.1"
PORT = 5000

def recvline(sock):
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(1024)
        if not chunk:
            return None
        buf += chunk
    return buf.decode(errors="ignore").rstrip("\r\n")

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
            # SERVER IS FULL
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
                resp = recvline(s)
                if resp:
                    print(resp)
                break

            resp = recvline(s)
            if resp is None:
                break
            print(resp)

if __name__ == "__main__":
    main()
