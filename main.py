import socket
import struct
import threading
import random
import json
import os
import time

# Config
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
        print("[DB] Accounts updated.")
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
                mask |= (1 << j); values.append(chunk[j])
        if mask == 0xFF:
            out.extend([0xFF, 0]); out.extend(chunk)
        else:
            out.append(mask); out.extend(values)
    return bytes(out)

def sproto_unpack(data):
    out = bytearray()
    i = 0
    while i < len(data):
        mask = data[i]; i += 1
        if mask == 0xFF:
            if i >= len(data): break
            n = (data[i] + 1) * 8; i += 1
            out.extend(data[i:i+n]); i += n
        else:
            for bit in range(8):
                if mask & (1 << bit):
                    if i < len(data): out.append(data[i]); i += 1
                else: out.append(0)
    return bytes(out)

def encode_sproto(fields, fn=None):
    if not fields: return struct.pack("<H", 0)
    fields.sort(key=lambda x: x[0])
    if fn is None: fn = fields[-1][0] + 1
    header = [0] * fn
    body = bytearray()
    field_dict = {f[0]: f[1] for f in fields}
    for tag in range(fn):
        if tag in field_dict:
            val = field_dict[tag]
            if val is None: header[tag] = 1
            elif isinstance(val, int):
                if 0 <= val <= 32766: header[tag] = (val + 1) * 2
                else:
                    header[tag] = 0
                    body += struct.pack("<I", 8) + struct.pack("<q", val)
            elif isinstance(val, (str, bytes, bytearray)):
                if isinstance(val, str): val = val.encode('utf-8')
                header[tag] = 0
                body += struct.pack("<I", len(val)) + val
            elif isinstance(val, list):
                header[tag] = 0
                list_bin = bytearray()
                for item in val: list_bin += struct.pack("<I", len(item)) + item
                body += struct.pack("<I", len(list_bin)) + list_bin
        else: header[tag] = 1
    res = struct.pack("<H", fn)
    for h in header: res += struct.pack("<H", h)
    res += body
    return bytes(res)

def decode_sproto(data, offset=0):
    if len(data) < offset + 2: return {}
    fn = struct.unpack("<H", data[offset:offset+2])[0]
    h_ptr, b_ptr, curr_tag = offset + 2, offset + 2 + fn*2, 0
    fields = {}
    for i in range(fn):
        v = struct.unpack("<H", data[h_ptr + i*2:h_ptr + i*2+2])[0]
        if v == 0:
            if b_ptr + 4 <= len(data):
                l = struct.unpack("<I", data[b_ptr:b_ptr+4])[0]
                fields[curr_tag] = data[b_ptr+4:b_ptr+4+l]; b_ptr += 4 + l
        elif v == 1: pass
        elif v & 1: curr_tag += (v >> 1)
        else: fields[curr_tag] = (v >> 1) - 1
        curr_tag += 1
    return fields

def client_handler(conn, addr):
    print(f"[+] Login Connect: {addr}")
    try:
        while True:
            h = conn.recv(2)
            if not h: break
            size = struct.unpack(">H", h)[0]
            data = b""
            while len(data) < size: data += conn.recv(size - len(data))
            raw = sproto_unpack(data)
            
            header = decode_sproto(raw, 0)
            msg_type, session = header.get(0), header.get(1)
            
            body_off = 2 + (struct.unpack("<H", raw[:2])[0] * 2)
            body = decode_sproto(raw, body_off)

            if msg_type == 2: # visitor

    while True:
        length = random.randint(12,16)

        uid = random.choice(["67","68","69"]) + "".join(
            str(random.randint(0,9)) for _ in range(length-2)
        )

        if uid not in accounts:
            break

    key_length = random.randint(8,13)

    key = "".join(
        str(random.randint(0,9)) for _ in range(key_length)
    )

    accounts[uid] = key
    save_accounts(accounts)

    print(f"[GUEST] Account Created: {uid} / {key}")

    resp = encode_sproto(
        [(0, uid), (1, key), (2, 0)],
        fn=3
    )

    pkg_h = encode_sproto([(1, session)], fn=2)

    full = sproto_pack(pkg_h + resp)

    conn.sendall(
        struct.pack(">H", len(full)) + full
    )

            elif msg_type == 3: # verfiy
                req_id = body.get(0, b"").decode('utf-8', 'ignore')
                req_key = body.get(1, b"").decode('utf-8', 'ignore')
                print(f"[VERIFY] ID: {req_id}")
                
                resp_state = 0 if req_id in accounts and accounts[req_id] == req_key else 1
                s1 = encode_sproto([(0,1),(1,"Vice City Main"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(10,1)], fn=11)
                
                resp = encode_sproto([(0, resp_state), (1, random.randint(100,999)), (2, [s1]), (3, "1"), (5, "1.012.017"), (6, "167"), (7, 0)], fn=12)
                pkg_h = encode_sproto([(1, session)], fn=2)
                conn.sendall(struct.pack(">H", len(sproto_pack(pkg_h+resp))) + sproto_pack(pkg_h+resp))

            elif msg_type == 218: # heartbeat
                pkg_h = encode_sproto([(1, session)], fn=2)
                full = sproto_pack(pkg_h); conn.sendall(struct.pack(">H", len(full)) + full)

    except Exception as e: print(f"Login Error: {e}")
    finally: conn.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT))
server.listen(10)
print(f"LOGIN SERVER RUNNING ON {PORT}")
while True:
    c, a = server.accept(); threading.Thread(target=client_handler, args=(c, a), daemon=True).start()
