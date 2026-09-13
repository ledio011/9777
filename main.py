import json
import os
import random
import socket
import struct
import threading
import time
import traceback

PORT = int(os.environ.get("PORT", 9777))
DB_FILE = "accounts.json"
GAME_HOST = "s16.serv00.com"
GAME_PORT = 15678

# APK Source of Truth
GAME_VERSION = "1.012.017"
DATA_VERSION = "205"

def load_accounts():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_accounts(accs):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(accs, f, indent=4)
    except Exception:
        pass

accounts = load_accounts()

def encode_sproto(fields, fn=None):
    if not fields:
        return struct.pack("<H", 0)

    fields = sorted(fields, key=lambda item: item[0])
    header = []
    body = bytearray()
    last_tag = -1

    for tag, value in fields:
        skip = tag - last_tag - 1
        if skip > 0:
            header.append(2 * (skip - 1) + 1)

        if value is None:
            header.append(1)
        elif isinstance(value, bool):
            header.append((1 if value else 0) * 2 + 2)
        elif isinstance(value, int):
            if 0 <= value <= 32766:
                header.append((value + 1) * 2)
            else:
                header.append(0)
                if -2147483648 <= value <= 2147483647:
                    body += struct.pack("<I", 4) + struct.pack("<i", value)
                else:
                    body += struct.pack("<I", 8) + struct.pack("<q", value)
        elif isinstance(value, str):
            header.append(0)
            payload = value.encode("utf-8")
            body += struct.pack("<I", len(payload)) + payload
        elif isinstance(value, (bytes, bytearray)):
            header.append(0)
            payload = bytes(value)
            body += struct.pack("<I", len(payload)) + payload
        elif isinstance(value, list):
            header.append(0)
            payload = b"".join(value)
            body += struct.pack("<I", len(payload)) + payload
        else:
            header.append(0)
            payload = str(value).encode("utf-8")
            body += struct.pack("<I", len(payload)) + payload

        last_tag = tag

    res = struct.pack("<H", len(header))
    for item in header:
        res += struct.pack("<H", item)
    return res + body

def decode_sproto(data, offset=0):
    if len(data) < offset + 2:
        return {}

    fn = struct.unpack("<H", data[offset:offset + 2])[0]
    h_ptr, b_ptr = offset + 2, offset + 2 + fn * 2
    fields, curr_tag = {}, -1
    for i in range(fn):
        v = struct.unpack("<H", data[h_ptr + i * 2: h_ptr + i * 2 + 2])[0]
        if v == 0:
            curr_tag += 1
            if b_ptr + 4 <= len(data):
                l = struct.unpack("<I", data[b_ptr:b_ptr + 4])[0]
                fields[curr_tag] = data[b_ptr + 4:b_ptr + 4 + l]
                b_ptr += 4 + l
        elif v == 1:
            curr_tag += 1
        elif v & 1:
            curr_tag += (v >> 1) + 1
        else:
            curr_tag += 1
            fields[curr_tag] = (v >> 1) - 1
    return fields

def sproto_pack(data):
    out = bytearray()
    for i in range(0, len(data), 8):
        chunk = data[i:i + 8]
        if len(chunk) < 8:
            chunk += b"\x00" * (8 - len(chunk))
        mask = 0
        for j in range(8):
            if chunk[j] != 0:
                mask |= (1 << j)
        if mask == 0xFF:
            out.append(0xFF)
            out.append(0)
            out.extend(chunk)
        else:
            out.append(mask)
            for j in range(8):
                if mask & (1 << j):
                    out.append(chunk[j])
    return bytes(out)

def sproto_unpack(data):
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        mask = data[i]
        i += 1
        if mask == 0xFF:
            if i >= n:
                break
            count = (data[i] + 1) * 8
            i += 1
            out.extend(data[i:i + count])
            i += count
        else:
            for bit in range(8):
                if mask & (1 << bit):
                    if i < n:
                        out.append(data[i])
                        i += 1
                else:
                    out.append(0)
    return bytes(out)

def build_game_server(server_id, name, host, port, area, timezone):
    # Matches SprotoType.game_server (Tags 0-10)
    return encode_sproto([
        (0, server_id), (1, name), (2, host), (3, port),
        (4, 1), (5, -4), (6, area), (7, 1), (8, timezone), (9, 1), (10, 0),
    ])

def build_verify_response(session, game_servers, state=0):
    return encode_sproto([
        (0, state),
        (1, session),
        (2, [struct.pack("<I", len(s)) + s for s in game_servers]),
        (3, "302#303"),      # Recommended
        (5, GAME_VERSION),   # versionCode
        (6, DATA_VERSION),   # dataVersionCode
        (7, 1),              # downloadFlag
        (8, "Welcome back to Auto Theft Gangster!"),
        (9, "1"),
    ])

def handle_message(msg, session, body=None):
    if msg == 2: # visitor
        uid = "68" + "".join(str(random.randint(0, 9)) for _ in range(12))
        key = "".join(str(random.randint(0, 9)) for _ in range(12))
        accounts[uid] = key
        save_accounts(accounts)
        return encode_sproto([(0, uid), (1, key), (2, 0)])

    if msg == 3: # verify
        servers = [
            build_game_server(302, "Europe-1", GAME_HOST, GAME_PORT, 1, 1),
            build_game_server(303, "Europe-2", GAME_HOST, GAME_PORT, 1, 1),
            build_game_server(602, "Asia-1", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(11, "America-1", GAME_HOST, GAME_PORT, 0, -4),
        ]
        return build_verify_response(session, servers, 0)

    if msg == 4: # login
        return encode_sproto([
            (0, 2), (1, GAME_VERSION), (2, DATA_VERSION), (3, 1)
        ])

    if msg == 7: # update_game_server
        servers = [build_game_server(302, "Europe-1", GAME_HOST, GAME_PORT, 1, 1)]
        return encode_sproto([(2, [struct.pack("<I", len(s)) + s for s in servers])])

    if msg == 118: # random_name
        names = ["Hunter", "Shadow", "Rogue", "Cobra", "Titan", "Viper", "Outlaw", "Legend"]
        return encode_sproto([(0, f"{random.choice(names)}_{random.randint(100, 999)}")])

    if msg == 218: # heart_beat
        t1 = body.get(0, 0) if body else 0
        return encode_sproto([(0, t1), (1, int(time.time()))])

    return encode_sproto([])

def handle_http_request(conn, addr, initial_data):
    try:
        request_text = initial_data.decode("utf-8", "ignore")
        while "\r\n\r\n" not in request_text:
            chunk = conn.recv(1024)
            if not chunk: break
            request_text += chunk.decode("utf-8", "ignore")
        lines = request_text.split("\r\n")
        if not lines: return
        path = lines[0].split(" ")[1].lstrip("/")
        
        search_paths = [
            os.path.join("assets", "RES_200", path),
            os.path.join("assets", path),
            os.path.join("assets", "Bundle", path),
        ]
        
        local_path = None
        for p in search_paths:
            p = p.replace("//", "/")
            if os.path.exists(p) and os.path.isfile(p):
                local_path = p; break
        
        if local_path:
            with open(local_path, "rb") as f: content = f.read()
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(content)).encode() + b"\r\n\r\n" + content)
        else:
            conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")
    except Exception: pass
    finally: conn.close()

def client_handler(conn, addr):
    try:
        peek = conn.recv(4, socket.MSG_PEEK)
        if peek.startswith(b"GET "):
            handle_http_request(conn, addr, b"")
            return

        while True:
            h_bytes = conn.recv(2)
            if not h_bytes: break
            size = struct.unpack(">H", h_bytes)[0]
            data = b""
            while len(data) < size: data += conn.recv(size - len(data))

            raw = sproto_unpack(data)
            pkg = decode_sproto(raw, 0)
            msg, session = pkg.get(0), pkg.get(1)
            
            off = 2 + (struct.unpack("<H", raw[:2])[0] * 2)
            response_body = handle_message(msg, session, decode_sproto(raw, off))

            response = encode_sproto([(1, session)]) + response_body
            full = sproto_pack(response)
            conn.sendall(struct.pack(">H", len(full)) + full)
    except Exception: pass
    finally: conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(20)
    print(f"ATG LOGIN SERVER ON {PORT}")
    while True:
        cl, ad = server.accept()
        threading.Thread(target=client_handler, args=(cl, ad), daemon=True).start()

if __name__ == "__main__":
    start_server()
