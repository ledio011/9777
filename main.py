import socket
import threading

PORT = 9777

def handle_client(client, address):
    print(f"[*] Lidhje e re: {address}")
    try:
        while True:
            data = client.recv(1024)
            if not data:
                break
            print(f"[*] Marrë nga {address}: {data.hex()}")
            
            # KËTU DUHET KODI QË DËRGON PËRGJIGJEN (client.send)
            # Pa dërguar përgjigjen Sproto, loading nuk do të lëvizë
            
    except Exception as e:
        print(f"[!] Gabim me {address}: {e}")
    finally:
        print(f"[*] Lidhja u mbyll: {address}")
        client.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("0.0.0.0", PORT))
server.listen(5)

print(f"Serveri po dëgjon në portin: {PORT}")

while True:
    client, address = server.accept()
    # Përdorim threading që serveri të mos bllokohet
    client_thread = threading.Thread(target=handle_client, args=(client, address))
    client_thread.start()
