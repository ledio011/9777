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


def load_accounts():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_accounts(accs):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(accs, f, indent=4)
        print("[DB] Saved")
    except Exception as e:
        print("[DB ERROR]", e)


accounts = load_accounts()


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

        if mask == 0xFF:
            out.extend([0xFF, 0])
            out.extend(chunk)
        else:
            out.append(mask)
            out.extend(values)

    return bytes(out)



def sproto_unpack(data):
    out = bytearray()
    i = 0

    while i < len(data):

        mask = data[i]
        i += 1

        if mask == 0xFF:
            if i >= len(data):
                break

            n = (data[i] + 1) * 8
            i += 1

            out.extend(data[i:i+n])
            i += n

        else:
            for bit in range(8):

                if mask & (1 << bit):
                    if i < len(data):
                        out.append(data[i])
                        i += 1

                else:
                    out.append(0)

    return bytes(out)



def encode_sproto(fields, fn=None):

    if fn is None:
        fn = fields[-1][0] + 1

    header = [1] * fn
    body = bytearray()

    field_dict = dict(fields)

    for tag in range(fn):

        if tag not in field_dict:
            continue

        val = field_dict[tag]

        if isinstance(val, int):

            header[tag] = (val + 1) * 2

        elif isinstance(val, str):

            val = val.encode()

            header[tag] = 0

            body += struct.pack("<I", len(val))
            body += val


        elif isinstance(val, bytes):

            header[tag] = 0

            body += struct.pack("<I", len(val))
            body += val


    result = struct.pack("<H", fn)

    for h in header:
        result += struct.pack("<H", h)

    result += body

    return result



def decode_sproto(data, offset=0):

    if len(data) < offset+2:
        return {}

    fn = struct.unpack(
        "<H",
        data[offset:offset+2]
    )[0]


    header_start = offset+2
    body_start = offset+2+(fn*2)

    fields={}

    for i in range(fn):

        v = struct.unpack(
            "<H",
            data[header_start+i*2:header_start+i*2+2]
        )[0]


        if v == 0:

            length = struct.unpack(
                "<I",
                data[body_start:body_start+4]
            )[0]

            fields[i]=data[
                body_start+4:
                body_start+4+length
            ]

            body_start += 4+length


        elif v > 1:

            fields[i]=(v//2)-1


    return fields
    def client_handler(conn, addr):

    print(f"[+] Login Connect: {addr}")

    try:

        while True:

            header = conn.recv(2)

            if not header:
                break


            size = struct.unpack(">H", header)[0]


            data = b""

            while len(data) < size:

                packet = conn.recv(size-len(data))

                if not packet:
                    break

                data += packet


            raw = sproto_unpack(data)


            pkg = decode_sproto(raw,0)

            msg_type = pkg.get(0)
            session = pkg.get(1)


            print(
                f"[PACKET] type={msg_type} session={session}"
            )


            body_offset = 2 + (
                struct.unpack("<H", raw[:2])[0] * 2
            )

            body = decode_sproto(
                raw,
                body_offset
            )


            # ==========================
            # NEW PLAYER ACCOUNT CREATE
            # ==========================

            if msg_type == 2:


                while True:

                    length = random.randint(12,16)


                    uid = random.choice(
                        ["67","68","69"]
                    ) + "".join(
                        str(random.randint(0,9))
                        for _ in range(length-2)
                    )


                    if uid not in accounts:
                        break



                password_length = random.randint(8,13)


                password = "".join(
                    str(random.randint(0,9))
                    for _ in range(password_length)
                )


                accounts[uid] = password

                save_accounts(accounts)


                print(
                    f"[GUEST CREATED] ID={uid} PASS={password}"
                )


                response = encode_sproto(
                    [
                        (0,uid),
                        (1,password),
                        (2,0)
                    ],
                    fn=3
                )


                package_header = encode_sproto(
                    [
                        (1,session)
                    ],
                    fn=2
                )


                packet = sproto_pack(
                    package_header + response
                )


                conn.sendall(
                    struct.pack(">H",len(packet))
                    + packet
                )



            # ==========================
            # VERIFY LOGIN
            # ==========================

            elif msg_type == 3:


                req_id = body.get(
                    0,b""
                ).decode(
                    "utf-8",
                    "ignore"
                )


                req_pass = body.get(
                    1,b""
                ).decode(
                    "utf-8",
                    "ignore"
                )


                print(
                    f"[VERIFY] {req_id}"
                )


                if (
                    req_id in accounts
                    and accounts[req_id] == req_pass
                ):

                    state = 0

                else:

                    state = 1



                server_info = encode_sproto(
                    [
                        (0,1),
                        (1,"Vice City Main"),
                        (2,GAME_HOST),
                        (3,GAME_PORT),
                        (4,1),
                        (10,1)
                    ],
                    fn=11
                )


                response = encode_sproto(
                    [
                        (0,state),
                        (1,random.randint(100,999)),
                        (2,[server_info]),
                        (3,"1"),
                        (5,"1.012.017"),
                        (6,"167"),
                        (7,0)
                    ],
                    fn=12
                )


                package_header = encode_sproto(
                    [
                        (1,session)
                    ],
                    fn=2
                )


                packet = sproto_pack(
                    package_header + response
                )


                conn.sendall(
                    struct.pack(">H",len(packet))
                    + packet
                )



            # ==========================
            # HEARTBEAT
            # ==========================

            elif msg_type == 218:


                package_header = encode_sproto(
                    [
                        (1,session)
                    ],
                    fn=2
                )


                packet = sproto_pack(
                    package_header
                )


                conn.sendall(
                    struct.pack(">H",len(packet))
                    + packet
                )



    except Exception as e:

        print(
            "[ERROR]",
            e
        )


    finally:

        conn.close()



# ==========================
# START SERVER
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


server.listen(20)


print(
    f"LOGIN SERVER RUNNING ON PORT {PORT}"
)


while True:

    client, addr = server.accept()

    threading.Thread(
        target=client_handler,
        args=(client,addr),
        daemon=True
    ).start()
