"""
* CP372 Programming ASGMT - Fall 2025
* Client.py
* Haitham Timimi | timi6805@mylaurier.ca | 000006805
* Karl Richter | rich1728@mylaurier.ca | 169061728
* 10/20/2025
"""

import socket

EOF_MARKER = b"<<EOF>>" 

# helper function for list feature
def _recv_until_eof(sock) -> bytes:
    buffer = bytearray()
    while True:
        chunk = sock.recv(1024)
        if not chunk:
            break
        buffer += chunk
        pos = buffer.find(EOF_MARKER)
        if pos != -1:
            data = bytes(buffer[:pos])
            return data
    return bytes(buffer)

def start_client():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   #IPv4 and TCP connection
    client.connect(('127.0.0.1', 9999))     #establishes a connection to a server running on the same machine

    #initial connection with server
    client_name_message = client.recv(1024).decode()
    print("Server Response:", client_name_message)
   
    #check if the server is at max capacity
    if "Server is at full capacity" in client_name_message:
        client.close()  # Close the connection
        return

    #allows the user to input a message via the input() function
    while True:
        message = input("Enter a message: ")
        #The message is then encoded to bytes and sent to the server
        client.send(message.encode())
        lower = message.lower()

        if lower == "exit":
            print(client.recv(1024).decode())
            client.close()
            break

        # For 'list' and 'print' read until EOF marker to support streaming
        elif lower == "list" or lower.startswith("print "):
            payload = _recv_until_eof(client)
            # Treat as text for display; replace errors to avoid crashes for odd files
            try:
                print(payload.decode().rstrip("\n"))
            except UnicodeDecodeError:
                print("[Binary data received]", len(payload), "bytes")

        elif lower == "status":
            # Print status without prefix 
            print(client.recv(4096).decode())
        else:
            print("Server's Response: ", client.recv(1024).decode())


if __name__ == "__main__":
    start_client()
