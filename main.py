import socket
import threading
import struct
import random


PORT = 9777


# =========================
# SPROTO PACK
# =========================

def sproto_pack(data):
    out = bytearray()

    for i in range(0, len(data), 8):

        chunk = data[i:i+8]

        if len(chunk) < 8:
            chunk = chunk + b'\x00' * (8-len(chunk))

        mask = 0
        values = bytearray()

        for j in range(8):
            if chunk[j] != 0:
                mask |= (1 << j)
                values.append(chunk[j])

        out.append(mask)
        out.extend(values)

    return bytes(out)



# =========================
# SPROTO SERIALIZE
# =========================

def write_uint16(v):
    return struct.pack("<H", v)


def write_uint32(v):
    return struct.pack("<I", v)



def write_integer(value):

    # sproto small integer
    return write_uint16((value + 1) * 2)



def write_string(value):

    b = value.encode("utf-8")

    return (
        write_uint32(len(b))
        +
        b
    )



# =========================
# VISITOR RESPONSE
# =========================

def create_visitor_response(session, guest_id, guest_key):


    # =====================
    # Package
    # =====================

    package = bytearray()


    # max field count = 2
    package += write_uint16(2)


    # tag 0 missing
    package += write_uint16(1)


    # tag 1 = session
    package += write_integer(session)



    # =====================
    # visitor.response
    # =====================

    body = bytearray()


    # fields = 3
    body += write_uint16(3)


    # tag 0 id string
    body += write_uint16(0)


    # tag 1 key string
    body += write_uint16(0)


    # tag 2 state = 0
    body += write_integer(0)



    # data section
    body += write_string(guest_id)

    body += write_string(guest_key)



    raw = package + body


    packed = sproto_pack(raw)


    # network length
    return (
        struct.pack(">H", len(packed))
        +
        packed
    )



# =========================
# CLIENT
# =========================

def handle_client(client, addr):

    print("[+] Client:", addr)

    try:

        data = client.recv(4096)


        if not data:
            return


        print("RX:", data.hex())



        # visitor.request
        if b"\x15\x02" in data:


            session = 1



            # 18 digit ID
            guest_id = str(
                random.randint(
                    100000000000000000,
                    999999999999999999
                )
            )


            # 12 digit password
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



            packet = create_visitor_response(
                session,
                guest_id,
                guest_key
            )


            client.sendall(packet)


            print("visitor.response SENT")



        else:

            print("Unknown packet")



    except Exception as e:

        print("ERROR:", e)


    finally:

        client.close()

        print("Disconnected", addr)





# =========================
# SERVER
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


server.listen(50)



print("===================")
print("9777 SERVER RUNNING")
print("===================")



while True:

    client, addr = server.accept()


    thread = threading.Thread(
        target=handle_client,
        args=(client, addr)
    )


    thread.start()
