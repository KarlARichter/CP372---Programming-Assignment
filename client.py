import socket
import sys

HOST = "127.0.0.1"
PORT = 5000


# will return None if the connection is closed with no buffered data
def recvline(sock):
    buf = b""
    # read until newline appears in buffer 
    while b"\n" not in buf:
        chunk = sock.recv(1024)
        if not chunk:
            return buf.decode(errors="ignore") if buf else None
        buf += chunk
    # decode and return the first line
    return buf.decode(errors="ignore").splitlines()[0]

# recvn: read exactly n bytes from socket
# returns None if the connection is closed before n bytes are received
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
    # pick host/port from argv if provided, else use defaults
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT

    # creates a TCP socket and connect to server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))

        # read initial server line
        line = recvline(s)
        if not line:
            return
        # if server is full print msg and exit 
        if line.startswith("BUSY"):
            print(line)
            return
        if not line.startswith("NAME? "):
            # unexpected response will exit as well
            return

        # parse assigned name from "NAME? ClientXX" and reply with "NAME ClientXX" 
        assigned = line.split(" ", 1)[1]
        sendline(s, f"NAME {assigned}")
        print(f"You are {assigned}")


        # loop reads user input, sends to server and prints response(s)
        while True:
            try:
                msg = input("Enter message: ")
            except (EOFError, KeyboardInterrupt):
                msg = "exit"

            # if user requested exit, read final server response and break
            sendline(s, msg)
            if msg.strip().lower() == "exit":
                resp = recvline(s)
                if resp is not None:
                    print(resp)
                break
            
            # else read server response
            resp = recvline(s)
            if resp is None:
                break
            
            # handles the "status" function keyword
            # server first sends "STATUS <length>" line, then the exact <length> bytes of payload
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
