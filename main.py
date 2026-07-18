import socket
import threading
import struct
import random


PORT = 9777


def create_number(length):
    return "".join(
        random.choice("0123456789")
        for _ in range(length)
    )


def handle_client(client, address):

    print("[+] Client connected:", address)

    try:

        while True:

            data = client.recv(4096)


            if not data:
                print("[DISCONNECT]", address)
                break


            print("RX:", data.hex())


            # Visitor request
            if b"\x15\x02" in data:


                player_id = create_number(
                    random.randint(15,18)
                )

                player_key = create_number(
                    random.randint(12,15)
                )


                print("===================")
                print("ID :", player_id)
                print("KEY:", player_key)
                print("===================")


                # Për momentin vetëm ruajmë log.
                # Këtu do vendosim përgjigjen finale
                # pasi të kapim paketën e saktë.


                print("visitor request detected")


            else:

                print("Unknown packet")


    except Exception as e:

        print("ERROR:", e)


    finally:

        client.close()



server = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)


server.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)


server.bind(
    ("0.0.0.0", PORT)
)


server.listen(20)


print("===================")
print("9777 SERVER RUNNING")
print("===================")



while True:

    client, address = server.accept()


    threading.Thread(
        target=handle_client,
        args=(client,address)
    ).start()
