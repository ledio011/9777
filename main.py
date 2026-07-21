import socket
import struct
import threading
import random
import json
import os
import time

# Porta dinamike e Railway
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

def decode_header(data):
    if len(data) < 2: return None, None, 0
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
    return msg_type, session, 2 + fn*2

def decode_body(data, offset):
    if len(data) < offset + 2: return {}
    fn = struct.unpack("<H", data[offset:offset+2])[0]
    h_start, b_ptr, curr_tag = offset + 2, offset + 2 + fn*2, 0
    fields = {}
    for i in range(fn):
        v = struct.unpack("<H", data[h_start + i*2:h_start + i*2+2])[0]
        if v == 0:
            if b_ptr + 4 <= len(data):
                l = struct.unpack("<I", data[b_ptr:b_ptr+4])[0]
                b_ptr += 4
                fields[curr_tag] = data[b_ptr:b_ptr+l].decode('utf-8', 'ignore')
                b_ptr += l
        elif v > 1: fields[curr_tag] = (v >> 1) - 1
        curr_tag += 1
    return fields

def client_handler(conn, addr):
    print(f"[+] Connection: {addr}")
    try:
        while True:
            h = conn.recv(2)
            if not h: break
            size = struct.unpack(">H", h)[0]
            data = b""
            while len(data) < size: data += conn.recv(size - len(data))
            raw = sproto_unpack(data)
            msg_type, session, offset = decode_header(raw)
            if msg_type is None: continue

            if msg_type == 2: # visitor (Tag 2)
                # Gjenerojme nje ID numerike 10-shifrore qe nuk ekziston
                while True:
                    uid = str(random.randint(1000000000, 9999999999))
                    if uid not in accounts: break
                
                key = str(random.randint(1000000000, 9999999999))
                accounts[uid] = key; save_accounts(accounts)
                print(f"[AUTO REG] New Unique Account: ID={uid} KEY={key}")

                # visitor.response: id(0:string), key(1:string), state(2:integer)
                resp = encode_sproto([(0, uid), (1, key), (2, 0)], fn=3)
                pkg_h = encode_sproto([(1, session)], fn=2)
                full = sproto_pack(pkg_h + resp)
                conn.sendall(struct.pack(">H", len(full)) + full)

            elif msg_type == 3: # verfiy (Tag 3)
                req_fields = decode_body(raw, offset)
                req_id = str(req_fields.get(0, ""))
                req_key = str(req_fields.get(1, ""))
                
                print(f"[VERIFY] Client ID: {req_id} KEY: {req_key}")
                
                # Kontrollojme nese ID ekziston dhe nese KEY perputhet
                resp_state = 0 # OK
                if req_id not in accounts or accounts[req_id] != req_key:
                    print(f"[VERIFY] Invalid or Not Found. Forcing RE-REGISTRATION.")
                    resp_state = 1 # State 1 e detyron Unity-n te therrase visitor.request automatikisht
                else:
                    print(f"[VERIFY] Access Granted.")

                s1 = encode_sproto([(0,1),(1,"Vice City Main"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(10,1)], fn=11)
                
                # verfiy.response: state(0), session(1), game_server(2:list), etc.
                resp = encode_sproto([
                    (0, resp_state), 
                    (1, random.randint(100000, 999999)), 
                    (2, [s1]), 
                    (3, "1"), 
                    (5, "1.012.017"), 
                    (6, "167"), 
                    (7, 0)
                ], fn=12)
                
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
