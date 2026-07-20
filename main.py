import socket
import struct
import threading
import random


PORT = 9777


# ==========================
# SPROTO PACK
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
# SPROTO ENCODE
# ==========================

def int_encode(v):

    return struct.pack(
        "<H",
        (v + 1) * 2
    )



def write_string(value):

    b = value.encode("utf-8")

    return (
        struct.pack("<I", len(b))
        +
        b
    )



def encode_object(fields):

    header = bytearray()
    body = bytearray()

    last = -1


    for tag, value in fields:

        skip = tag - last - 1


        if skip > 0:

            record = (skip - 1) * 2 + 1
            header += struct.pack("<H", record)



        if isinstance(value, int):

            header += int_encode(value)


        elif isinstance(value, str):

            header += struct.pack("<H", 0)
            body += write_string(value)


        elif isinstance(value, bytes):

            header += struct.pack("<H", 0)
            body += struct.pack("<I", len(value))
            body += value


        last = tag



    return (
        struct.pack("<H", len(header)//2)
        +
        header
        +
        body
    )



# ==========================
# PACKAGE HEADER
# ==========================

def package_response(session):

    # response:
    # tag 1 = session

    return encode_object([
        (1, session)
    ])



# ==========================
# VISITOR RESPONSE
# TAG 2
# ==========================

def visitor_response(session):


    uid = str(
        random.randint(
            10**14,
            10**17-1
        )
    )


    key = str(
        random.randint(
            10**11,
            10**14-1
        )
    )


    print("")
    print("================")
    print("ACCOUNT CREATED")
    print("ID :", uid)
    print("KEY:", key)
    print("================")



    body = encode_object([

        (0, uid),   # id

        (1, key),   # key/password

        (2, 1)      # state success

    ])



    raw = (
        package_response(session)
        +
        body
    )



    packed = sproto_pack(raw)



    return (
        struct.pack(">H", len(packed))
        +
        packed
    )



# ==========================
# VERIFY RESPONSE
# TAG 3
# ==========================

def verify_response(session):


    body = encode_object([

        (0,1),              # type

        (1,"1.012.017"),    # version

        (2,"0"),            # data version

        (3,1)               # server level

    ])



    raw = (
        package_response(session)
        +
        body
    )



    packed = sproto_pack(raw)



    return (
        struct.pack(">H", len(packed))
        +
        packed
    )



# ==========================
# CLIENT
# ==========================

def client(conn,addr):

    print("[+] Connected:",addr)


    try:


        while True:


            data = conn.recv(4096)


            if not data:
                break



            print(
                "RX:",
                data.hex()
            )



            # visitor request

            if True:


                conn.sendall(
                    visitor_response(1)
                )


                conn.sendall(
                    verify_response(2)
                )


                break



    except Exception as e:

        print(
            "ERROR:",
            e
        )


    finally:

        conn.close()

        print(
            "Disconnected"
        )



# ==========================
# SERVER START
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



server.listen(50)



print("======================")
print("LOGIN SERVER 9777 ON")
print("======================")



while True:


    conn,addr = server.accept()


    threading.Thread(
        target=client,
        args=(conn,addr),
        daemon=True
    ).start()
