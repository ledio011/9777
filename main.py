import socket
import struct
import threading
import random


PORT = 9777


# ==========================
# SPROTO 0 PACK
# ==========================

def sproto_pack(data):
    out = bytearray()

    for i in range(0, len(data), 8):
        chunk = data[i:i+8]

        mask = 0
        values = bytearray()

        for j, b in enumerate(chunk):
            if b != 0:
                mask |= (1 << j)
                values.append(b)

        out.append(mask)
        out.extend(values)

    return bytes(out)


# ==========================
# SPROTO HELPERS
# ==========================

def integer(value):
    return struct.pack("<H", (value + 1) * 2)


def string_field(text):
    data = text.encode("utf-8")
    return struct.pack("<I", len(data)) + data


def make_header(fields):
    result = struct.pack("<H", len(fields))

    for f in fields:
        if isinstance(f, int):
            result += integer(f)
        elif isinstance(f, str):
            result += struct.pack("<H", 0)
        else:
            result += struct.pack("<H", 0)

    return result


# ==========================
# PACKAGE HEADER
# ==========================

def package_response(session):

    # Package:
    # tag0 = type absent
    # tag1 = session

    return (
        struct.pack("<H", 2) +
        struct.pack("<H", 0) +
        struct.pack("<H", 1) +
        integer(session)
    )


# ==========================
# VISITOR RESPONSE
# ==========================

def visitor_response(session):

    uid = str(random.randint(100000000000,999999999999))
    pwd = str(random.randint(1000000000,9999999999))

    print("")
    print("================")
    print("ACCOUNT CREATED")
    print("ID :", uid)
    print("PWD:", pwd)
    print("================")


    body = make_header([
        "",
        "",
    ])

    body += string_field(uid)
    body += string_field(pwd)


    raw = package_response(session) + body

    packed = sproto_pack(raw)

    return struct.pack(">H", len(packed)) + packed



# ==========================
# VERIFY RESPONSE
# ==========================

def verify_response(session):


    body = make_header([
        0,
        1,
        "",
        "",
        0,
        "1.012.017",
        "0",
        0,
        "Welcome",
        "1"
    ])


    body += string_field("Welcome")


    raw = package_response(session) + body

    packed = sproto_pack(raw)

    return struct.pack(">H", len(packed)) + packed



# ==========================
# CLIENT
# ==========================

def client_thread(sock, addr):

    print("[+] Connected:", addr)

    try:

        while True:

            data = sock.recv(4096)

            if not data:
                break


            print("RX:", data.hex())


            # visitor request
            if len(data) > 0:

                print("Sending verify response")

                sock.sendall(
                    visitor_response(1)
                )

                sock.sendall(
                    verify_response(2)
                )

                break


    except Exception as e:

        print("ERROR:", e)


    finally:

        sock.close()
        print("Disconnected")



# ==========================
# SERVER
# ==========================

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


print("======================")
print("LOGIN SERVER 9777 ON")
print("======================")


while True:

    c,a = server.accept()

    threading.Thread(
        target=client_thread,
        args=(c,a),
        daemon=True
    ).start()
