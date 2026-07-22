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


# =========================
# DATABASE
# =========================

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



# =========================
# SPROTO PACK
# =========================

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

        if mask == 0xff:
            out.extend(b"\x00")
            out.extend(chunk)

        else:
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



# =========================
# ENCODE / DECODE
# =========================

def encode_sproto(fields, fn):

    header = [1] * fn
    body = bytearray()


    for tag,value in fields:

        if tag >= fn:
            continue


        if isinstance(value,int):

            header[tag] = (value + 1) * 2


        elif isinstance(value,str):

            b = value.encode()

            header[tag] = 0

            body += struct.pack("<I",len(b))
            body += b


        elif isinstance(value,bytes):

            header[tag] = 0

            body += struct.pack("<I",len(value))
            body += value



    result = struct.pack("<H",fn)


    for h in header:

        if h > 65535:
            h = 1

        result += struct.pack("<H",h)


    result += body


    return result



def decode_sproto(data,offset=0):

    if len(data) < offset+2:
        return {}


    fn = struct.unpack(
        "<H",
        data[offset:offset+2]
    )[0]


    h = offset+2

    b = offset+2+(fn*2)


    fields={}


    for i in range(fn):

        if h+i*2+2 > len(data):
            break


        v = struct.unpack(
            "<H",
            data[h+i*2:h+i*2+2]
        )[0]


        if v == 0:

            if b+4 > len(data):
                break


            size = struct.unpack(
                "<I",
                data[b:b+4]
            )[0]


            fields[i] = data[
                b+4:b+4+size
            ]


            b += 4+size


        elif v > 1:

            fields[i] = (v//2)-1


    return fields



# =========================
# CREATE ACCOUNT
# =========================

def create_account():

    while True:

        length = random.randint(12,16)

        uid = random.choice(
            ["67","68","69"]
        )


        uid += "".join(
            str(random.randint(0,9))
            for _ in range(length-2)
        )


        if uid not in accounts:
            break



    pass_len = random.randint(8,13)


    password = "".join(
        str(random.randint(0,9))
        for _ in range(pass_len)
    )


    accounts[uid] = password

    save_accounts()


    print(
        "[NEW ACCOUNT]",
        uid,
        password
    )


    return uid,password



# =========================
# CLIENT
# =========================

def client_handler(conn,addr):

    print("[+] Connected:",addr)


    try:

        while True:

            head = conn.recv(2)

            if not head:
                break


            size = struct.unpack(
                ">H",
                head
            )[0]


            data=b""


            while len(data)<size:

                part=conn.recv(
                    size-len(data)
                )

                if not part:
                    break

                data+=part



            raw=sproto_unpack(data)


            pkg=decode_sproto(raw,0)


            msg_type=pkg.get(0)

            session=pkg.get(1)



            print(
                "[PACKET]",
                msg_type,
                session
            )


            body_offset = 2 + (
                struct.unpack(
                    "<H",
                    raw[:2]
                )[0]*2
            )


            body=decode_sproto(
                raw,
                body_offset
            )



 # NEW USER

if msg_type == 234:
    print("[INIT PACKET RECEIVED - WAITING FOR VISITOR]")
    continue


if msg_type == 2:

    uid,password=create_account()

    

    


                resp=encode_sproto(
                    [
                        (0,uid),
                        (1,password),
                        (2,0)
                    ],
                    3
                )


                header=encode_sproto(
                    [
                        (1,session)
                    ],
                    2
                )


                packet=sproto_pack(
                    header+resp
                )


                conn.sendall(
                    struct.pack(">H",len(packet))
                    +packet
                )




            # VERIFY

            elif msg_type == 3:


                uid=body.get(
                    0,b""
                ).decode(
                    errors="ignore"
                )


                password=body.get(
                    1,b""
                ).decode(
                    errors="ignore"
                )


                print(
                    "[VERIFY]",
                    uid
                )


                state=0


                if uid not in accounts:
                    state=1

                elif accounts[uid] != password:
                    state=1



                server=encode_sproto(
                    [
                        (0,1),
                        (1,"Vice City Main"),
                        (2,GAME_HOST),
                        (3,GAME_PORT)
                    ],
                    5
                )


                resp=encode_sproto(
                    [
                        (0,state),
                        (2,server)
                    ],
                    3
                )


                header=encode_sproto(
                    [
                        (1,session)
                    ],
                    2
                )


                packet=sproto_pack(
                    header+resp
                )


                conn.sendall(
                    struct.pack(">H",len(packet))
                    +packet
                )




            elif msg_type == 218:

                header=encode_sproto(
                    [
                        (1,session)
                    ],
                    2
                )


                packet=sproto_pack(header)


                conn.sendall(
                    struct.pack(">H",len(packet))
                    +packet
                )


    except Exception as e:

        print("[ERROR]",e)


    finally:

        conn.close()



# =========================
# START
# =========================

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

    c,a=server.accept()

    threading.Thread(
        target=client_handler,
        args=(c,a),
        daemon=True
    ).start()
