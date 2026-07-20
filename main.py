import socket
import struct
import threading
import random
import json
import os
import time


PORT = 9777

DB_FILE = "accounts.json"


# ==========================
# ACCOUNT DATABASE
# ==========================

def load_accounts():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}


def save_accounts():
    with open(DB_FILE, "w") as f:
        json.dump(accounts, f, indent=4)


accounts = load_accounts()



# ==========================
# SPROTO PACK / UNPACK
# ==========================

def sproto_pack(data):

    out = bytearray()

    for i in range(0, len(data), 8):

        chunk = data[i:i+8]

        mask = 0
        values = bytearray()

        for j,b in enumerate(chunk):

            if b != 0:
                mask |= (1 << j)
                values.append(b)

        out.append(mask)
        out.extend(values)

    return bytes(out)



def sproto_unpack(data):

    out = bytearray()

    i = 0

    while i < len(data):

        mask = data[i]
        i += 1

        for bit in range(8):

            if mask & (1 << bit):

                if i < len(data):
                    out.append(data[i])
                    i += 1

            else:
                out.append(0)

    return bytes(out)



# ==========================
# SPROTO ENCODE
# ==========================

def int_encode(v):

    return struct.pack(
        "<H",
        (v + 1) * 2
    )



def string_encode(v):

    b = v.encode()

    return (
        struct.pack("<I",len(b))
        +
        b
    )



def encode_object(fields):

    header = bytearray()
    body = bytearray()

    last = -1


    for tag,value in fields:


        skip = tag-last-1


        if skip > 0:

            record = (skip-1)*2+1

            header += struct.pack(
                "<H",
                record
            )


        if isinstance(value,int):

            header += int_encode(value)


        elif isinstance(value,str):

            header += struct.pack("<H",0)

            body += string_encode(value)


        elif isinstance(value,bytes):

            header += struct.pack("<H",0)

            body += struct.pack(
                "<I",
                len(value)
            )

            body += value


        last = tag



    return (
        struct.pack(
            "<H",
            len(header)//2
        )
        +
        header
        +
        body
    )



# ==========================
# PACKAGE
# ==========================

def package(session=None):

    fields=[]

    if session is not None:
        fields.append((1,session))


    return encode_object(fields)



def send_packet(sock, session, body):

    raw = (
        package(session)
        +
        body
    )


    packed = sproto_pack(raw)


    sock.sendall(
        struct.pack(">H",len(packed))
        +
        packed
    )



# ==========================
# VISITOR RESPONSE
# TAG 2
# ==========================

def visitor_response(session):

    uid = str(random.randint(
        10000000000000000,
        99999999999999999
    ))

    key = str(random.randint(
        1000000000000,
        99999999999999
    ))


    accounts[uid] = key
    save_accounts()


    print("================")
    print("ACCOUNT CREATED")
    print("ID :",uid)
    print("KEY:",key)
    print("================")


    body = encode_object([

        (0,uid),
        (1,key),
        (2,0)

    ])


    return body



# ==========================
# VERIFY RESPONSE
# TAG 3
# ==========================

def verify_response(session):


    game_server = encode_object([

        (0,1),                         # serverId
        (1,"Europe"),                  # name
        (2,"tokaido.proxy.rlwy.net"),  # IP
        (3,48282),                     # port
        (4,1),                         # state
        (6,1)                          # area

    ])



    body = encode_object([

        (0,0),               # success
        (1,session),         # session
        (2,game_server),     # server list
        (3,"1"),
        (5,"1.012.017"),
        (6,"0"),
        (8,"Welcome"),
        (9,"1")

    ])


    return body



# ==========================
# CLIENT HANDLER
# ==========================

def client(conn,addr):

    print("[+] Connected:",addr)


    try:


        while True:


            h = conn.recv(2)


            if not h:
                break


            size = struct.unpack(
                ">H",
                h
            )[0]


            data=b""


            while len(data)<size:

                data += conn.recv(
                    size-len(data)
                )


            raw = sproto_unpack(data)


            print("RX:",raw.hex())



            # visitor request
            # protocol 2

            if b"\x02\x00" in raw:


                print("VISITOR REQUEST")


                send_packet(
                    conn,
                    1,
                    visitor_response(1)
                )



            # verify request
            # protocol 3

            elif b"\x03\x00" in raw:


                print("VERIFY REQUEST")


                # TEMP:
                # accept any existing account

                session = random.randint(
                    1000,
                    9999
                )


                send_packet(
                    conn,
                    session,
                    verify_response(session)
                )



    except Exception as e:

        print("ERROR:",e)



    finally:

        conn.close()

        print("Disconnected")




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
    ("0.0.0.0",PORT)
)


server.listen(50)


print("======================")
print("LOGIN SERVER 9777 ON")
print("======================")


while True:

    c,a = server.accept()


    threading.Thread(
        target=client,
        args=(c,a),
        daemon=True
    ).start()
