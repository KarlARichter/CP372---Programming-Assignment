"""
* CP372 Programming ASGMT - Fall 2025
* Server.py
* Haitham Timimi | timi6805@mylaurier.ca | 000006805
* Karl Richter | rich1728@mylaurier.ca | 169061728
* 10/20/2025
"""

#listens to incoming connections on specific IP addresses and port

import threading
import socket
import datetime
import os

client_cache = {}
MAX_CLIENTS = 3
client_count = 0

available_client_slots = ["Client01", "Client02", "Client03"]

REPO_PATH = os.path.join(os.path.dirname(__file__), "repo")

# frames variable-length responses
EOF_MARKER = b"<<EOF>>" 
def _send_with_eof(sock, data: bytes):
    sock.sendall(data)
    sock.sendall(EOF_MARKER)


# helper to handle list function
def _handle_list(sock):
    try:
        entries = []
        if os.path.isdir(REPO_PATH):
            for name in os.listdir(REPO_PATH):
                full = os.path.join(REPO_PATH, name)
                if os.path.isfile(full):
                    entries.append(name)
        payload = ("\n".join(entries) if entries else "No files.").encode()
    except Exception as e:
        payload = f"Repository error: {e}".encode()
    _send_with_eof(sock, payload)

# helper to parse filenames from repo
def _parse_print_filename(msg: str) -> str | None:
    rest = msg[6:].strip() 
    if not rest:
        return None
    if (rest[0] == rest[-1]) and rest[0] in ('"', "'") and len(rest) >= 2:
        return rest[1:-1].strip()
    return rest.split()[0]

# helper to print file 
def _handle_print(sock, msg: str):
    fname = _parse_print_filename(msg)
    if not fname:
        _send_with_eof(sock, b"Usage: print 'filename'\n")
        return

    fpath = os.path.join(REPO_PATH, fname)
    if not (os.path.isfile(fpath)):
        _send_with_eof(sock, b"File not found.\n")
        return

    try:
        with open(fpath, 'rb') as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                sock.sendall(chunk)
        sock.sendall(EOF_MARKER)
    except Exception as e:
        _send_with_eof(sock, f"Error reading file: {e}\n".encode())


def handle_client(client_socket, client_address, client_name):
    global client_cache, client_count

    # Assign a unique client name based on client count
    client_socket.sendall(f"You are {client_name}.".encode())
    print(f"{client_name} connected from {client_address}.")

    #adding client information to memory cache
    start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Store address/port + connect/disconnect times
    client_cache[client_name] = {
        "address": client_address[0],
        "port": client_address[1],
        "start_time": start_time,
        "end_time": "N/A"
    }

    while True:
        message = client_socket.recv(1024).decode()

        #exit = close connections and terminate the program
        if message.lower() == "exit":

            #end time for cache
            end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            #set the end time in memory cache
            client_cache[client_name]["end_time"] = end_time

            #close socket and prints message
            client_socket.send(f"Connection closed for {client_name}".encode())
            print(f"{client_name} disconnected.")
            client_socket.close()

            #remove from cache and free the slot
            available_client_slots.append(client_name)
            available_client_slots.sort()
           
            #decrements the client_count to ensure doesn't go over the limit
            global client_count
            client_count -= 1
            break
        
        # formats status function 
        elif message == "status":
            if client_cache:
                lines = []
                for cname, info in client_cache.items():
                    addr = info.get("address", "?")
                    port = info.get("port", "?")
                    start = info.get("start_time", "?")
                    end = info.get("end_time", "N/A")
                    lines.append(f"{cname} — {addr}:{port} — Connected: {start} — Disconnected: {end}")
                status_text = "\n".join(lines)
            else:
                status_text = "No clients yet."
            client_socket.send(status_text.encode())

        # list files in repo
        elif message == "list":
            _handle_list(client_socket)

        # stream file contents
        elif message.startswith("print "):
            _handle_print(client_socket, message)

        else:
            client_socket.send(f"{message} ACK".encode())
           
#starts server and manages incoming connections
def start_server():
    global client_count

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 9999))
    server.listen(MAX_CLIENTS)

    print(f"Server started. Listening for connections on...")

    while True:
        #accept connection
        client_socket, client_address = server.accept()

        #ensure client_count doesn't go over the limit
        if client_count < MAX_CLIENTS:
            client_count += 1

            #assign the first available client slot
            client_name = available_client_slots.pop(0)

            #start a new thread to handle client
            thread = threading.Thread(target=handle_client, args=(client_socket, client_address, client_name))
            thread.start()

        #server at max capacity
        else:
            #print to client and server
            client_socket.send("Server is at max capacity. Please try again later.".encode())
            client_socket.close()
            print("Server is at max capacity. Waiting for clients to disconnect...")
       
   
if __name__ == "__main__":
    start_server()
