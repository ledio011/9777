import socket
import struct
import threading
import random
import json
import os

PORT = 9777
DB_FILE = "accounts.json"

# Konfigurimi i Railway që dërgove
GAME_SERVER_HOST = "tokaido.proxy.rlwy.net"
GAME_SERVER_PORT = 48282

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
    """Implementim i saktë i SprotoPack.cs të Unity"""
    out = bytearray()
    n = len(data)
    for i in range(0, n, 8):
        chunk = data[i:i+8]
        if len(chunk) < 8:
            chunk += b'\x00' * (8 - len(chunk))

        mask = 0
        values = bytearray()
        for j in range(8):
            if chunk[j] != 0:
                mask |= (1 << j)
                values.append(chunk[j])

        if mask == 0xFF: # Optimization for literals (similair to SprotoPack.cs)
            out.append(0xFF)
            out.append(0) # 0 means 1 chunk of 8 bytes
            out.extend(chunk)
        else:
            out.append(mask)
            out.extend(values)
    return bytes(out)

def encode_sproto(fields, is_root=False):
    """
    fields: lista e tuplave (tag, value)
    is_root: True nëse është mesazhi kryesor (ka fn header), False për objekte nested
    """
    if not fields: return struct.pack("<H", 0) if is_root else b""
    fields.sort(key=lambda x: x[0])

    header = bytearray()
    body = bytearray()
    last_tag = -1

    for tag, value in fields:
        skip = tag - last_tag - 1
        if skip > 0:
            header += struct.pack("<H", (skip - 1) * 2 + 1)

        if value is None:
            header += struct.pack("<H", 0)
        elif isinstance(value, int):
            if 0 <= value <= 32766:
                header += struct.pack("<H", (value + 1) * 2)
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
            for item in value:
                # Sproto obj_list: çdo element ka 4-byte length prefix
                list_bin += struct.pack("<I", len(item)) + item
            body += struct.pack("<I", len(list_bin)) + list_bin
        last_tag = tag

    res = bytearray()
    if is_root:
        res += struct.pack("<H", len(header) // 2)
    res += header
    res += body
    return bytes(res)

def decode_header(data):
    if len(data) < 2: return None, None
    try:
        fn = struct.unpack("<H", data[:2])[0]
        header = data[2:2+fn*2]
        msg_type, session = None, None
        idx, curr_tag = 0, 0
        while idx < len(header):
            val = struct.unpack("<H", header[idx:idx+2])[0]
            if val & 1:
                curr_tag += (val >> 1) + 1
            else:
                real_val = (val >> 1) - 1
                if curr_tag == 0: msg_type = real_val
                if curr_tag == 1: session = real_val
                curr_tag += 1
            idx += 2
        return msg_type, session
    except: return None, None

def client_handler(conn, addr):
    print(f"[+] Login Client: {addr}")
    try:
        while True:
            h = conn.recv(2)
            if not h: break
            size = struct.unpack(">H", h)[0]
            data = b""
            while len(data) < size:
                part = conn.recv(size - len(data))
                if not part: break
                data += part

            # Sproto unpack (missing from simplified version)
            # For now we use data directly since we aren't using literal packing yet
            # In a real scenario, sproto_unpack would go here.

            # Simplified decode for requests
            msg_type, session = decode_header(data)
            if msg_type is None: continue

            if msg_type == 2: # Visitor Request (AUTOMATIC NEW ACCOUNT)
                prefix = random.choice(["68", "69"])
                uid = prefix + "".join([str(random.randint(0, 9)) for _ in range(10)])
                key = "".join([str(random.randint(0, 9)) for _ in range(10)])
                accounts[uid] = key
                save_accounts(accounts)
                print(f"[NEW PLAYER] Generated Account: ID={uid} PASS={key}")

                resp = encode_sproto([(0, uid), (1, key), (2, 0)])
                pkg_h = encode_sproto([(1, session)], is_root=True)
                full_pkt = sproto_pack(pkg_h + resp)
                conn.sendall(struct.pack(">H", len(full_pkt)) + full_pkt)

            elif msg_type == 3: # Verify Request (EXISTING ACCOUNT)
                # Këtu pranojmë çdo ID që ka klienti për të shmangur humbjen e aksesit
                # Nëse dëshiron verifikim strikt, mund të shtosh kontrollin e 'accounts' këtu
                srv = encode_sproto([(0, 1), (1, "Main Server"), (2, GAME_SERVER_HOST), (3, GAME_SERVER_PORT), (4, 1), (10, 1)])

                resp = encode_sproto([
                    (0, 0),             # state (0 = Success)
                    (1, session),       # session
                    (2, [srv]),         # game_server list
                    (3, "1"),           # user_server
                    (5, "1.012.017"),    # versionCode
                    (6, "0"),           # dataVersionCode
                    (7, 0)              # downloadFlag
                ])
                pkg_h = encode_sproto([(1, session)], is_root=True)
                full_pkt = sproto_pack(pkg_h + resp)
                conn.sendall(struct.pack(">H", len(full_pkt)) + full_pkt)

            elif msg_type == 218: # Heartbeat
                pkg_h = encode_sproto([(1, session)], is_root=True)
                full_pkt = sproto_pack(pkg_h)
                conn.sendall(struct.pack(">H", len(full_pkt)) + full_pkt)

    except Exception as e:
        print(f"Login Error: {e}")
    finally:
        conn.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT))
server.listen(10)
print(f"LOGIN SERVER 9777 ON (Railway TCP Proxy Mode)")
while True:
    c, a = server.accept()
    threading.Thread(target=client_handler, args=(c, a), daemon=True).start()
