import socket
import threading
import struct
import random


PORT = 9777


def send_packet(client, payload):
    # Sproto packet = 2 byte length + data
    length = len(payload)
    header = struct.pack(">H", length)
    client.send(header + payload)


def create_guest_id():
    return str(random.randint(100000000000, 999999999999))


def create_key():
    return str(random.randint(1000000000, 9999999999))


def handle_client(client, address):

    print(f"[*] Lidhje e re: {address}")

    try:

        while True:

            data = client.recv(1024)

            if not data:
                break


            print("RX:", data.hex())


            # ============================
            # visitor request (type 2)
            # ============================

            if "0206" in data.hex():

                guest_id = create_guest_id()
                guest_key = create_key()

                print("Krijova account:")
                print("ID:", guest_id)
                print("KEY:", guest_key)


                # TEMP RESPONSE
                # state=0
                # id
                # key

                response = bytes.fromhex(
                    "0200"
                )

                send_packet(client, response)

                print("visitor.response SENT")


            # ============================
            # verify request (type 3)
            # ============================

            elif "0306" in data.hex():

                session = random.randint(10000,99999)

                print("Session:", session)


                # state=0
                # session


                response = bytes.fromhex(
                    "0200"
                )


                send_packet(client,response)

                print("verfiy.response SENT")


    except Exception as e:
        print("[ERROR]",e)


    finally:
        client.close()
        print("[DISCONNECT]",address)



server = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

server.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)


server.bind(
    ("0.0.0.0",PORT)
)


server.listen(20)


print("======================")
print("9777 SERVER RUNNING")
print("======================")


while True:

    client,address = server.accept()

    threading.Thread(
        target=handle_client,
        args=(client,address)
    ).start()
