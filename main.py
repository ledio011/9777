import socket
import struct
import threading
import random


PORT = 9777


# =========================
# SPROTO 0 PACK
# =========================

def sproto_pack(data):

    packed = bytearray()

    for i in range(0, len(data), 8):

        chunk = data[i:i+8]

        if len(chunk) < 8:
            chunk += b'\x00' * (8-len(chunk))

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
# SPROTO HELPERS
# =========================

def write_string(text):

    data = text.encode("utf-8")

    return struct.pack("<I", len(data)) + data



def write_header(fields):

    result = struct.pack("<H", len(fields))

    for field in fields:

        if field is None:
            result += struct.pack("<H", 1)

        elif isinstance(field, int):
            result += struct.pack("<H", (field + 1) * 2)

        else:
            result += struct.pack("<H", 0)

    return result



# =========================
# VISITOR RESPONSE
# =========================

def visitor_response(session):

    guest_id = str(
        random.randint(
            100000000000000000,
            999999999999999999
        )
    )

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


    # Package header
    package = write_header([
        None,
        session
    ])


    # visitor.response
    body = write_header([
        "",
        "",
        0
    ])


    body += write_string(guest_id)
    body += write_string(guest_key)


    raw = package + body


    packed = sproto_pack(raw)


    return struct.pack(">H", len(packed)) + packed



# =========================
# VERIFY RESPONSE
# =========================

def verify_response(session):


    package = write_header([
        None,
        session
    ])


    response = write_header([

        0,              # state
        999,            # session
        "",             # game server list
        None,
        None,
        "1.012.017",
        "1.012.017",
        0,
        "Welcome",
        "1"

    ])


    # game_server object

    game = write_header([

        1,
        "",
        "",
        9555,
        0

    ])


    game += write_string("Revival Server")
    game += write_string("127.0.0.1")


    response += struct.pack("<I", len(game))
    response += game


    raw = package + response


    packed = sproto_pack(raw)


    return struct.pack(">H", len(packed)) + packed



# =========================
# CLIENT
# =========================

def handle_client(client, addr):

    print("[+] Client:", addr)


    try:

        client.settimeout(5)

        buffer = b""


        while True:


            data = client.recv(4096)


            if not data:
                break


            buffer += data


            print("RX:", buffer.hex())


            # visitor.request

            if b"\x15\x02" in buffer:


                print("Visitor request")


                packet = visitor_response(1)


                client.sendall(packet)


                print("visitor.response SENT")


                break



            else:


                if len(buffer) > 2:


                    print("Verify request")


                    packet = verify_response(2)


                    client.sendall(packet)


                    print("verfiy.response SENT")


                    break



    except Exception as e:

        print("ERROR:", e)



    finally:

        client.close()

        print("Disconnected", addr)



# =========================
# START SERVER
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
print("LOGIN SERVER 9777 RUNNING")
print("===================")



while True:


    client, addr = server.accept()


    thread = threading.Thread(
        target=handle_client,
        args=(client, addr)
    )


    thread.start()
