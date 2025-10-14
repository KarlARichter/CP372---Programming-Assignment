"""

* CP372 Programming ASGMT - Fall 2025
* client.py
* Karl Richter | rich1728@mylaurier.ca | 169061728
* 
* 10/20/2025

"""

import socket
import sys
import json
from pathlib import Path

HOST = "127.0.0.1"   
PORT = 5000          
DOWNLOADS = Path(__file__).with_name("downloads")  # where binary files are saved

# Read a single newline-terminated line from the socket.
def recvline(sock):
    # accumulate bytes until newline or EOF
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(1024)
        # connection closed -> return any buffered text or None
        if not chunk:
            return buf.decode(errors="ignore") if buf else None
        buf += chunk
    # decode and return the first line only
    return buf.decode(errors="ignore").splitlines()[0]

# Read exactly n bytes from the socket.
def recvn(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

# Send a single newline-terminated message.
def sendline(sock, s: str):
    sock.sendall((s + "\n").encode())

# Receive a length-prefixed JSON payload.
def receive_json(sock, expected_tag: str):
    header = recvline(sock)
    if not header:
        return None
    parts = header.split()
    # validate header format
    if len(parts) != 2 or parts[0] != expected_tag or not parts[1].isdigit():
        return header
    n = int(parts[1])
    payload = recvn(sock, n)
    if payload is None:
        return None
    try:
        return json.loads(payload.decode(errors="ignore"))
    except Exception:
        # parsing failed -> caller will treat as error
        return None

def main():
    # pick host/port from argv or use defaults for quick testing
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT

    # connect to server and perform NAME handshake
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))

        # initial server greeting: either BUSY or NAME? <ClientNN>
        line = recvline(s)
        if not line:
            return
        if line.startswith("BUSY"):
            # server at capacity; print user-facing message and exit
            print(line)
            return
        if not line.startswith("NAME? "):
            # unexpected protocol; bail silently to avoid terminal spam
            return

        # accept assigned name and send handshake reply
        assigned = line.split(" ", 1)[1]
        sendline(s, f"NAME {assigned}")
        print(f"You are {assigned}")

        # interactive loop: user types commands, client handles server responses
        while True:
            try:
                msg = input("Enter message: ").strip()
            except (EOFError, KeyboardInterrupt):
                # treat user interrupt as polite 'exit' so server can respond
                msg = "exit"

            if not msg:
                # ignore empty lines to keep interaction smooth
                continue

            sendline(s, msg)

            # if user wants to exit, read the final server line (if any) then quit
            if msg.lower() == "exit":
                resp = recvline(s)
                if resp is not None:
                    print("Server response:", resp)
                break

            # status: server sends length-prefixed JSON payload
            if msg.lower() == "status":
                payload = receive_json(s, "STATUS")
                if isinstance(payload, dict):
                    # pretty-print status JSON for human inspection
                    print(json.dumps(payload, indent=4))
                else:
                    # fallback: print whatever arrived so it's debuggable
                    print("Server response:", payload)
                continue

            # read a header/line to decide next action (could be FILE, list, error, ACK)
            header = recvline(s)
            if header is None:
                print("Server closed the connection.")
                break

            # file transfer handling: "FILE <name> <size>" then raw bytes
            if header.startswith("FILE "):
                parts = header.split()
                if len(parts) >= 3 and parts[2].isdigit():
                    name = parts[1]
                    size = int(parts[2])
                    data = recvn(s, size)
                    if data is None:
                        print("Server response: <file transfer truncated>")
                        continue
                    # try to display text files directly, save binaries to downloads/
                    try:
                        text = data.decode("utf-8")
                        print(f"--- {name} (text, {size} bytes) ---")
                        print(text)
                        print(f"--- end {name} ---")
                    except UnicodeDecodeError:
                        DOWNLOADS.mkdir(exist_ok=True)
                        out = DOWNLOADS / name
                        out.write_bytes(data)
                        print(f"Downloaded binary file '{name}' -> {out}")
                    continue
                else:
                    # malformed FILE header: print for debugging
                    print("Malformed FILE header:", header)
                    continue

            # default: print single-line server response (list, error, echo ACK)
            print("Server response:", header)

if __name__ == "__main__":
    main()
