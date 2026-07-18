import socket
import threading
import struct
import random


PORT = 9777


# =========================
# SPROTO PACK
# =========================

def sproto_pack(data):
    packed = bytearray()

    for i in range(0, len(data), 8):
        chunk = data[i:i+8]

        if len(chunk) < 8:
            chunk = chunk.ljust(8, b'\x00')

        mask = 0
        values = bytearray()

        for j in range(8):
            if chunk[j] != 0:
                mask |= (1 << j)
                values.append(chunk[j])

        packed.append(mask)
        packed.extend(values)

    return bytes(packed)


# =========================
# SPROTO SERIALIZE HELPERS
# =========================

def write_string(value):
    data = value.encode("utf-8")
    return struct.pack("<I", len(data)) + data


def write_integer(value):
    # small integer optimization
    return struct.pack("<H", (value + 1) * 2)


# =========================
# VISITOR RESPONSE
# =========================

def create_visitor_response(session, guest_id, guest_key):

    # -------------------------
    # Package header
    # response only contains session
    # -------------------------

    package = bytearray()

    # field count = 2
    package.extend(struct.pack("<H", 2))

    # skip type tag (tag 0)
    package.extend(struct.pack("<H", 1))

    # session tag 1
    package.extend(struct.pack("<H", (session + 1) * 2))


    # -------------------------
    # visitor.response body
    #
    # tag 0 id
    # tag 1 key
    # tag 2 state
    # -------------------------

    body = bytearray()

    # field count = 3
    body.extend(struct.pack("<H", 3))

    # string fields
    body.extend(struct.pack("<H", 0))
    body.extend(struct.pack("<H", 0))
    
    # state = 0
    body.extend(struct.pack("<H", 2))


    # data section
    body.extend(write_string(guest_id))
    body.extend(write_string(guest_key))


    raw = package + body


    packed = sproto_pack(raw)


    # 2 byte big endian length
    return struct.pack(">H", len(packed)) + packed



# =========================
# CLIENT HANDLER
# =========================

def handle_client(client, addr):

    print("[+] Client:", addr)

    try:

        data = client.recv(1024)

        if not data:
            return


        print("RX:", data.hex())


        # visitor request:
        # 0004 1502 0604

        if b"\x15\x02" in data:

            session = 1


            # 18 digit ID
            guest_id = str(
                random.randint(
                    100000000000000000,
                    999999999999999999
                )
            )


            # 12 digit KEY
            guest_key = str(
                random.randint(
                    100000000000,
                    999999999999
                )
            )


            print("===================")
            print("ID :", guest_id)
            print("KEY:", guest_key)
            print("===================")


            response = create_visitor_response(
                session,
                guest_id,
                guest_key
            )


            client.sendall(response)

            print("visitor.response SENT")


        else:

            print("Unknown packet")


    except Exception as e:

        print("ERROR:", e)


    finally:

        client.close()
        print("Disconnected", addr)



# =========================
# SERVER START
# =========================

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

    client, addr = server.accept()

    t = threading.Thread(
        target=handle_client,
        args=(client, addr)
    )

    t.start()
