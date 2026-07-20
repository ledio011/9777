import socket
import struct
import threading
import random
import json
import os

PORT = 9777
DB_FILE = "accounts.json"

def load_accounts():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_accounts(accounts):
    with open(DB_FILE, "w") as f:
        json.dump(accounts, f, indent=4)

accounts = load_accounts()

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

def encode_object(fields):
    header = bytearray()
    body = bytearray()
    last = -1
    for tag, value in fields:
        skip = tag - last - 1
        if skip > 0:
            header += struct.pack("<H", (skip - 1) * 2 + 1)

        if value is None: # Empty List/Object
            header += struct.pack("<H", 0)
            body += struct.pack("<I", 0)
        elif isinstance(value, int):
            header += struct.pack("<H", (value + 1) * 2)
        elif isinstance(value, str):
            header += struct.pack("<H", 0)
            b = value.encode("utf-8")
            body += struct.pack("<I", len(b)) + b
        elif isinstance(value, bytes):
            header += struct.pack("<H", 0)
            body += struct.pack("<I", len(value)) + value
        last = tag
    return struct.pack("<H", len(header) // 2) + header + body

def decode_header(data):
    if len(data) < 2: return None, None
    h_len = struct.unpack("<H", data[:2])[0]
    header = data[2:2+h_len*2]
    msg_type, session = None, None
    idx, curr_tag = 0, 0
    while idx < len(header):
        val = struct.unpack("<H", header[idx:idx+2])[0]
        if val & 1: curr_tag += (val >> 1) + 1
        else:
            real_val = (val >> 1) - 1
            if curr_tag == 0: msg_type = real_val
            if curr_tag == 1: session = real_val
            curr_tag += 1
        idx += 2
    return msg_type, session

def client_handler(conn, addr):
    print(f"[+] Login Client: {addr}")
    try:
        while True:
            h = conn.recv(2)
            if not h: break
            size = struct.unpack(">H", h)[0]
            data = b""
            while len(data) < size:
                data += conn.recv(size - len(data))

            raw = sproto_unpack(data)
            msg_type, session = decode_header(raw)
            print(f"Login RX Type: {msg_type}")

            if msg_type == 2: # Visitor
                uid = str(random.randint(100000, 999999))
                key = str(random.randint(100000, 999999))
                accounts[uid] = key
                save_accounts(accounts)
                body = encode_object([(0, uid), (1, key), (2, 0)])
                header = encode_object([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(header + body))) + sproto_pack(header + body))

            elif msg_type == 3: # Verify
                # Shto nje server ne liste qe loja te kete ku te lidhet
                srv = encode_object([(0,1), (1,"Local Server"), (2,"127.0.0.1"), (3,9555), (4,1), (6,1)])
                body = encode_object([(0, 0), (1, session), (2, srv), (3,"1"), (5,"1.012.017")])
                header = encode_object([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(header + body))) + sproto_pack(header + body))

            elif msg_type == 7: # Update Game Server
                srv = encode_object([(0,1), (1,"Local Server"), (2,"127.0.0.1"), (3,9555), (4,1), (6,1)])
                # Tag 2 eshte lista e serverave ne update_game_server.response
                body = encode_object([(2, srv)])
                header = encode_object([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(header + body))) + sproto_pack(header + body))

    except Exception as e:
        print(f"Login Error: {e}")
    finally:
        conn.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT))
server.listen(10)
print(f"LOGIN SERVER {PORT} ON")
while True:
    c, a = server.accept()
    threading.Thread(target=client_handler, args=(c, a), daemon=True).start()
