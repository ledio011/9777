import socket
import threading
import struct
import random


PORT = 9777


# -----------------------------
# SPROTO RESPONSE CREATOR
# -----------------------------

def sproto_pack(data):

    out = bytearray()

    for i in range(0, len(data), 8):

        chunk = data[i:i+8]

        chunk = chunk.ljust(8, b"\x00")

        mask = 0
        values = []

        for j, b in enumerate(chunk):

            if b != 0:
                mask |= (1 << j)
                values.append(b)

        out.append(mask)
        out.extend(values)

    return bytes(out)



def create_visitor_response(session, guest_id, guest_key):


    # Package header
    # tag 0 = type (omitted)
    # tag 1 = session

    package = struct.pack(
        "<HHH",
        2,
        1,
        (session + 1) * 2
    )


    # visitor.response

    id_bytes = guest_id.encode()
    key_bytes = guest_key.encode()


    body_header = struct.pack(
        "<HHHH",
        3,
        1,
        1,
        2
    )


    body_data = (
        struct.pack("<I", len(id_bytes))
        + id_bytes
        + struct.pack("<I", len(key_bytes))
        + key_bytes
    )


    full = package + body_header + body_data


    packed = sproto_pack(full)


    return (
        struct.pack(">H", len(packed))
        + packed
    )



# -----------------------------
# ACCOUNT GENERATOR
# -----------------------------

def generate_id():

    return "".join(
        random.choice("0123456789")
        for _ in range(random.randint(15,18))
    )


def generate_key():

    return "".join(
        random.choice("0123456789")
        for _ in range(random.randint(12,15))
    )



# -----------------------------
# CLIENT
# -----------------------------

def handle_client(client, address):

    print("[+] Client:", address)

    try:

        while True:

            data = client.recv(2048)


            if not data:
                break


            print("RX:", data.hex())


            # visitor.request
            if data == bytes.fromhex("000415020604"):


                session = 1


                player_id = generate_id()
                player_key = generate_key()


                print("===================")
                print("ID :", player_id)
                print("KEY:", player_key)
                print("===================")



                response = create_visitor_response(
                    session,
                    player_id,
                    player_key
                )


                print(
                    "RAW RESPONSE:",
                    response.hex()
                )


                client.sendall(response)


                print(
                    "visitor.response SENT"
                )


            else:

                print(
                    "Unknown packet"
                )


    except Exception as e:

        print(
            "ERROR:",
            e
        )


    finally:

        client.close()

        print(
            "Disconnected",
            address
        )



# -----------------------------
# SERVER
# -----------------------------

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
