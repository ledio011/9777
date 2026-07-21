import socket
import struct
import threading
import random
import json
import os
import time

PORT = int(os.environ.get("PORT", 9777))
DB_FILE = "accounts.json"
GAME_HOST = "tokaido.proxy.rlwy.net"
GAME_PORT = 48282

def load_accounts():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_accounts(accs):
    try:
        with open(DB_FILE, "w") as f: json.dump(accs, f, indent=4)
    except: pass

accounts = load_accounts()

def sproto_pack(data):
    out = bytearray()
    for i in range(0, len(data), 8):
        chunk = data[i:i+8]
        if len(chunk) < 8: chunk += b'\x00' * (8 - len(chunk))
        mask, values = 0, bytearray()
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
            n = (data[i] + 1) * 8
            i += 1
            out.extend(data[i:i+n])
            i += n
        else:
            for bit in range(8):
                if mask & (1 << bit):
                    out.append(data[i]); i += 1
                else: out.append(0)
    return bytes(out)

def encode_sproto(fields, fn=None):
    if not fields: return struct.pack("<H", 0)
    fields.sort(key=lambda x: x[0])
    if fn is None: fn = fields[-1][0] + 1
    header, body = bytearray(), bytearray()
    last_tag = -1
    for tag, value in fields:
        skip = tag - last_tag - 1
        if skip > 0: header += struct.pack("<H", (skip - 1) * 2 + 1)
        if value is None: header += struct.pack("<H", 0)
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
            list_bin = bytearray()
            for item in value: list_bin += struct.pack("<I", len(item)) + item
            body += struct.pack("<I", len(list_bin)) + list_bin
        last_tag = tag
    while (len(header) // 2) < fn: header += struct.pack("<H", 0); # Fill missing tags
    return struct.pack("<H", len(header) // 2) + header + body

def decode_header(data):
    if len(data) < 2: return None, None
    fn = struct.unpack("<H", data[:2])[0]
    header = data[2:2+fn*2]
    msg_type, session, idx, curr_tag = None, None, 0, 0
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
            while len(data) < size: data += conn.recv(size - len(data))
            raw = sproto_unpack(data)
            msg_type, session = decode_header(raw)
            if msg_type is None: continue

            if msg_type == 2: # Visitor
                uid = random.choice(["68", "69"]) + str(int(time.time()))[-10:]
                key = str(random.randint(1000000000, 9999999999))
                accounts[uid] = key; save_accounts(accounts)
                print(f"[NEW ACC] ID={uid} PASS={key}")
                # visitor.response fn=3: id(0), key(1), state(2)
                resp = encode_sproto([(0, uid), (1, key), (2, 0)], fn=3)
                pkg_h = encode_sproto([(1, session)], fn=2)
                full = sproto_pack(pkg_h + resp)
                conn.sendall(struct.pack(">H", len(full)) + full)

            elif msg_type == 3: # Verify
                # Europe, America, Asia. Tags: id(0), name(1), ip(2), port(3), state(4), new(10)
                s1 = encode_sproto([(0,1),(1,"Europe"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(10,1)], fn=11)
                s2 = encode_sproto([(0,2),(1,"America"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(10,1)], fn=11)
                s3 = encode_sproto([(0,3),(1,"Asia"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(10,1)], fn=11)
                # verify.response fn=12: state(0), session(1), game_server(2), user_server(3), version(5), data(6), flag(7)
                resp = encode_sproto([(0,0),(1,session),(2,[s1,s2,s3]),(3,"1"),(5,"1.012.017"),(6,"0"),(7,0)], fn=12)
                pkg_h = encode_sproto([(1, session)], fn=2)
                full = sproto_pack(pkg_h + resp)
                conn.sendall(struct.pack(">H", len(full)) + full)

            elif msg_type == 218: # Heartbeat
                pkg_h = encode_sproto([(1, session)], fn=2)
                full = sproto_pack(pkg_h); conn.sendall(struct.pack(">H", len(full)) + full)

    except Exception as e: print(f"Login Error: {e}")
    finally: conn.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT))
server.listen(10)
print(f"LOGIN SERVER ON PORT {PORT}")
while True:
    c, a = server.accept(); threading.Thread(target=client_handler, args=(c, a), daemon=True).start()
