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
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: return {}
    return {}

def save_accounts(accounts):
    with open(DB_FILE, "w") as f:
        json.dump(accounts, f, indent=4)

accounts = load_accounts()

def sproto_pack(data):
    padding = (8 - (len(data) % 8)) % 8
    data += b'\x00' * padding
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

def encode_sproto(fields):
    if not fields: return struct.pack("<H", 0)
    fields.sort(key=lambda x: x[0])
    header = bytearray()
    body = bytearray()
    last_tag = -1
    for tag, value in fields:
        skip = tag - last_tag - 1
        if skip > 0: header += struct.pack("<H", (skip - 1) * 2 + 1)
        if value is None:
            header += struct.pack("<H", 0)
            body += struct.pack("<I", 0)
        elif isinstance(value, int):
            if 0 <= value <= 32766: header += struct.pack("<H", (value + 1) * 2)
            else:
                header += struct.pack("<H", 0)
                body += struct.pack("<I", 8) + struct.pack("<q", value)
        elif isinstance(value, (str, bytes, bytearray)):
            if isinstance(value, str): value = value.encode('utf-8')
            header += struct.pack("<H", 0)
            body += struct.pack("<I", len(value)) + value
        elif isinstance(value, list):
            header += struct.pack("<H", 0)
            list_data = bytearray()
            for item in value:
                if isinstance(item, (bytes, bytearray)):
                    list_data += struct.pack("<I", len(item)) + item
            body += struct.pack("<I", len(list_data)) + list_data
        last_tag = tag
    return struct.pack("<H", len(header) // 2) + header + body

def decode_header(data):
    if len(data) < 2: return None, None
    fn = struct.unpack("<H", data[:2])[0]
    header = data[2:2+fn*2]
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
    is_new = False
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

            if msg_type == 2: # Visitor
                uid = str(random.randint(10**12, 10**15 - 1))
                key = str(random.randint(10**8, 10**12 - 1))
                while uid in accounts: uid = str(random.randint(10**12, 10**15 - 1))
                accounts[uid] = key
                save_accounts(accounts)
                is_new = True
                print(f"NEW ACC: ID={uid} PASS={key}")
                resp = encode_sproto([(0, uid), (1, key), (2, 0)])
                pkg_h = encode_sproto([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(pkg_h + resp))) + sproto_pack(pkg_h + resp))

            elif msg_type == 3: # Verify
                if is_new:
                    resp = encode_sproto([(0, 3), (1, session)]) # Force UI Sync
                    is_new = False
                else:
                    srv = encode_sproto([(0, 1), (1, "Official Server"), (2, "127.0.0.1"), (3, 9555), (4, 1), (6, 1)])
                    resp = encode_sproto([(0, 0), (1, session), (2, [srv]), (5, "1.012.017"), (6, "0")])

                pkg_h = encode_sproto([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(pkg_h + resp))) + sproto_pack(pkg_h + resp))

            elif msg_type == 218 or msg_type == 7: # Heartbeat
                pkg_h = encode_sproto([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(pkg_h))) + sproto_pack(pkg_h))

    except: pass
    finally: conn.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT))
server.listen(10)
print(f"LOGIN SERVER {PORT} READY")
while True:
    c, a = server.accept()
    threading.Thread(target=client_handler, args=(c, a), daemon=True).start()
