import socket
import struct
import threading
import random
import json
import os


PORT = int(os.environ.get("PORT", 9777))

DB_FILE = "accounts.json"

GAME_HOST = "tokaido.proxy.rlwy.net"
GAME_PORT = 48282


# ==========================
# DATABASE
# ==========================

def load_accounts():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_accounts():
    with open(DB_FILE, "w") as f:
        json.dump(accounts, f, indent=4)


accounts = load_accounts()



# ==========================
# SPROTO PACK
# ==========================

def sproto_pack(data):

    out = bytearray()

    for i in range(0, len(data), 8):

        chunk = data[i:i+8]

        if len(chunk) < 8:
            chunk += b"\x00" * (8-len(chunk))


        mask = 0
        values = bytearray()


        for j in range(8):

            if chunk[j] != 0:
                mask |= (1 << j)
                values.append(chunk[j])


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

def encode_sproto(fields, fn):

    header = [1] * fn

    body = bytearray()


    for tag,value in fields:


        if isinstance(value,int):

            header[tag] = (value + 1) * 2


        elif isinstance(value,str):

            value = value.encode()

            header[tag] = 0

            body += struct.pack("<I",len(value))
            body += value


        elif isinstance(value,bytes):

            header[tag] = 0

            body += struct.pack("<I",len(value))
            body += value



    result = struct.pack("<H",fn)


    for h in header:

        result += struct.pack("<H",h)


    result += body


    return result



# ==========================
# SPROTO DECODE
# ==========================

def decode_sproto(data,offset=0):

    if len(data) < offset+2:
        return {}


    fn = struct.unpack(
        "<H",
        data[offset:offset+2]
    )[0]


    header = offset+2

    body = offset+2+(fn*2)


    fields={}


    for i in range(fn):

        value = struct.unpack(
            "<H",
            data[header+i*2:header+i*2+2]
        )[0]


        if value == 0:

            length = struct.unpack(
                "<I",
                data[body:body+4]
            )[0]


            fields[i]=data[
                body+4:
                body+4+length
            ]


            body += 4+length


        elif value > 1:

            fields[i]=(value//2)-1


    return fields




# ==========================
# CLIENT
# ==========================

def client_handler(conn,addr):

    print("[+] Connected:",addr)


    try:

        while True:


            size_data = conn.recv(2)

            if not size_data:
                break


            size = struct.unpack(
                ">H",
                size_data
            )[0]


            packet=b""


            while len(packet)<size:

                packet += conn.recv(
                    size-len(packet)
                )


            raw = sproto_unpack(packet)


            header = decode_sproto(raw,0)


            msg_type = header.get(0)
            session = header.get(1)


            print(
                "[PACKET]",
                msg_type,
                session
            )


            body_start = 2 + (
                struct.unpack(
                    "<H",
                    raw[:2]
                )[0]*2
            )


            body = decode_sproto(
                raw,
                body_start
            )



            # ======================
            # CREATE ACCOUNT
            # ======================

            if msg_type == 2:


                while True:

                    length=random.randint(12,16)


                    uid=random.choice(
                        [
                            "67",
                            "68",
                            "69"
                        ]
                    )


                    uid += "".join(
                        str(random.randint(0,9))
                        for _ in range(length-2)
                    )


                    if uid not in accounts:
                        break



                password="".join(
                    str(random.randint(0,9))
                    for _ in range(
                        random.randint(8,13)
                    )
                )


                accounts[uid]=password

                save_accounts()


                print(
                    "[NEW ACCOUNT]",
                    uid,
                    password
                )



                response = encode_sproto(
                    [
                        (0,uid),
                        (1,password),
                        (2,0)
                    ],
                    3
                )


                head = encode_sproto(
                    [
                        (1,session)
                    ],
                    2
                )


                send = sproto_pack(
                    head+response
                )


                conn.sendall(
                    struct.pack(">H",len(send))
                    +send
                )



            # ======================
            # VERIFY
            # ======================

            elif msg_type == 3:


                user = body.get(
                    0,b""
                ).decode(
                    errors="ignore"
                )


                password = body.get(
                    1,b""
                ).decode(
                    errors="ignore"
                )


                print(
                    "[VERIFY]",
                    user
                )


                state = 0


                if user not in accounts:
                    state=1

                elif accounts[user]!=password:
                    state=1



                server = encode_sproto(
                    [
                        (0,1),
                        (1,"Vice City Main"),
                        (2,GAME_HOST),
                        (3,GAME_PORT)
                    ],
                    11
                )


                response = encode_sproto(
                    [
                        (0,state),
                        (2,server),
                        (5,"1.012.017")
                    ],
                    12
                )


                head = encode_sproto(
                    [
                        (1,session)
                    ],
                    2
                )


                send=sproto_pack(
                    head+response
                )


                conn.sendall(
                    struct.pack(">H",len(send))
                    +send
                )



            # ======================
            # HEARTBEAT
            # ======================

            elif msg_type == 218:

                head=encode_sproto(
                    [
                        (1,session)
                    ],
                    2
                )


                send=sproto_pack(head)


                conn.sendall(
                    struct.pack(">H",len(send))
                    +send
                )



    except Exception as e:

        print(
            "[ERROR]",
            e
        )


    finally:

        conn.close()



# ==========================
# START
# ==========================


server=socket.socket(
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


server.listen(20)


print(
    "LOGIN SERVER RUNNING ON",
    PORT
)



while True:

    conn,addr=server.accept()


    threading.Thread(
        target=client_handler,
        args=(conn,addr),
        daemon=True
    ).start()
