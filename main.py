import socket, struct, threading, random, json, os, time, traceback

PORT = int(os.environ.get("PORT", 9777))
DB_FILE = "accounts.json"
GAME_HOST = "127.0.0.1"
GAME_PORT = 9555

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

def encode_sproto(fields, fn=None):
    if not fields: return struct.pack("<H", 0)
    fields.sort(key=lambda x: x[0])
    header = []; body = bytearray(); last_tag = -1
    for tag, val in fields:
        skip = tag - last_tag - 1
        if skip > 0: header.append(2 * (skip - 1) + 3)
        if val is None: header.append(1)
        elif isinstance(val, int):
            if 0 <= val <= 32766: header.append((val + 1) * 2)
            else:
                header.append(0)
                body += struct.pack("<I", 8) + struct.pack("<q", val)
        elif isinstance(val, (str, bytes, bytearray, list, dict)):
            header.append(0)
            if isinstance(val, str): v = val.encode('utf-8')
            elif isinstance(val, list):
                # Sproto object lists are just concatenated encoded objects
                v = b"".join(val)
            elif isinstance(val, dict):
                # Sproto maps are lists of objects
                v = b"".join(val.values())
            else: v = val
            body += struct.pack("<I", len(v)) + v
        last_tag = tag
    res = struct.pack("<H", len(header))
    for h in header: res += struct.pack("<H", h)
    return res + body

def sproto_pack(data):
    out = bytearray()
    for i in range(0, len(data), 8):
        chunk = data[i:i+8]
        if len(chunk) < 8: chunk += b'\x00' * (8 - len(chunk))
        mask = 0
        for j in range(8):
            if chunk[j] != 0: mask |= (1 << j)
        if mask == 0xFF:
            out.append(0xFF); out.append(0); out.extend(chunk)
        else:
            out.append(mask)
            for j in range(8):
                if mask & (1 << j): out.append(chunk[j])
    return bytes(out)

def sproto_unpack(data):
    out = bytearray(); i = 0; n = len(data)
    while i < n:
        mask = data[i]; i += 1
        if mask == 0xFF:
            if i >= n: break
            count = (data[i] + 1) * 8; i += 1
            out.extend(data[i:i+count]); i += count
        else:
            for bit in range(8):
                if mask & (1 << bit):
                    if i < n: out.append(data[i]); i += 1
                else: out.append(0)
    return bytes(out)

def handle_http_request(conn, addr, initial_data):
    try:
        request_text = initial_data.decode('utf-8', 'ignore')
        while "\r\n\r\n" not in request_text:
            chunk = conn.recv(1024)
            if not chunk: break
            request_text += chunk.decode('utf-8', 'ignore')
        lines = request_text.split("\r\n")
        if not lines: return
        path = lines[0].split(" ")[1].lstrip("/")
        print(f"[HTTP] GET /{path}")
        if os.path.exists(path) and os.path.isfile(path):
            with open(path, "rb") as f: content = f.read()
            response = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(content)).encode() + b"\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n\r\n"
            conn.sendall(response + content)
        else: conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")
    except: pass
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
            raw = sproto_unpack(data); pkg = decode_sproto(raw, 0)
            msg, session = pkg.get(0), pkg.get(1)
            body = decode_sproto(raw, 2 + (struct.unpack("<H", raw[:2])[0] * 2))

            if msg == 2: # visitor
                uid = "68" + "".join([str(random.randint(0,9)) for _ in range(12)])
                key = "".join([str(random.randint(0,9)) for _ in range(12)])
                accounts[uid] = key; save_accounts(accounts)
                resp = encode_sproto([(0, uid), (1, key), (2, 0)])
                full = sproto_pack(encode_sproto([(1, session)]) + resp)
                conn.sendall(struct.pack(">H", len(full)) + full)

            elif msg == 3: # verify (FULL ORIGINAL SERVER LIST)
                s_am1 = encode_sproto([(0,11),(1,"America-01"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,0)], 11)
                s_am2 = encode_sproto([(0,12),(1,"America-02"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,0)], 11)
                s_am3 = encode_sproto([(0,13),(1,"America-03"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,0)], 11)
                s_am4 = encode_sproto([(0,14),(1,"America-04"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,0)], 11)
                s_am5 = encode_sproto([(0,15),(1,"America-05"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,0)], 11)
                s_eu1 = encode_sproto([(0,302),(1,"Europe-01"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,1)], 11)
                s_eu2 = encode_sproto([(0,303),(1,"Europe-02"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,1)], 11)
                s_eu3 = encode_sproto([(0,304),(1,"Europe-03"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,1)], 11)
                s_eu4 = encode_sproto([(0,305),(1,"Europe-04"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,1)], 11)
                s_as1 = encode_sproto([(0,602),(1,"Asia-01"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,2)], 11)
                s_as2 = encode_sproto([(0,603),(1,"Asia-02"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,2)], 11)
                s_as3 = encode_sproto([(0,604),(1,"Asia-03"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,2)], 11)
                s_as4 = encode_sproto([(0,605),(1,"Asia-04"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,2)], 11)
                s_as5 = encode_sproto([(0,606),(1,"Asia-05"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,2)], 11)
                s_as6 = encode_sproto([(0,607),(1,"Asia-06"),(2,GAME_HOST),(3,GAME_PORT),(4,1),(5,1),(6,2)], 11)
                resp = encode_sproto([
                    (0,0), (1,session), (2,[s_am1, s_am2, s_am3, s_am4, s_am5, s_eu1, s_eu2, s_eu3, s_eu4, s_as1, s_as2, s_as3, s_as4, s_as5, s_as6]),
                    (5,"1.012.017"), (6,"167"), (7,0), (8,"Original Server List Restored")
                ])
                full = sproto_pack(encode_sproto([(1, session)]) + resp)
                conn.sendall(struct.pack(">H", len(full)) + full)

            elif msg == 118: # random name
                names = ["John", "Mary", "William", "Smith", "Michael", "James", "David", "Chris", "Lisa", "Robert"]
                name = f"{random.choice(names)}_{random.randint(100,999)}"
                full = sproto_pack(encode_sproto([(1, session)]) + encode_sproto([(0, name)]))
                conn.sendall(struct.pack(">H", len(full)) + full)

            elif msg == 218: # heartbeat
                full = sproto_pack(encode_sproto([(1, session)]))
                conn.sendall(struct.pack(">H", len(full)) + full)
    except: pass
    finally: conn.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM); server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT)); server.listen(20)
print(f"ORIGINAL LOGIN SERVER READY ON {PORT}")
while True: c, a = server.accept(); threading.Thread(target=client_handler, args=(c, a), daemon=True).start()
