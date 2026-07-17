import socket

PORT = 9777

server = socket.socket()
server.bind(("0.0.0.0", PORT))
server.listen()

print("Server running on port:", PORT)

while True:
    client, address = server.accept()
    print("Connected:", address)

    try:
        data = client.recv(1024)
        print("Received:", data.hex())
    except Exception as e:
        print("Error:", e)

    client.close()
