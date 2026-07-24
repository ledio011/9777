import socket, struct, threading, random, json, os, time, traceback

# Railway/Local Config
PORT = int(os.environ.get("PORT", 9777))
DB_FILE = "accounts.json"
GAME_HOST = "autotheftserver-production.up.railway.app" # Lidhja te serveri i lojes 9555
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

def generate_unique_id():
    while True:
        prefix = random.choice(["67", "68", "69"])
        uid = prefix + "".join([str(random.randint(0, 9)) for _ in range(12)])
        if uid not in accounts: return uid

def generate_unique_password():
    return "".join([str(random.randint(0, 9)) for _ in range(12)])

def get_random_name():
    names = ["John", "Mary", "William", "Smith", "Michael", "James", "David", "Chris", "Lisa", "Robert", 
             "Linda", "Barbara", "Richard", "Susan", "Joseph", "Thomas", "Charles", "Karen", "Christopher", "Nancy"]
    sur = ["Wallace", "Smith", "Grant", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson", "Martinez", "Anderson"]
    return f"{random.choice(names)}_{random.choice(sur)}"

def sproto_pack(data):
    out = bytearray()
    i = 0
    while i < len(data):
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
                if chunk[j] != 0: out.append(chunk[j])
        i += 8
    return bytes(out)

def sproto_unpack(data):
    out = bytearray(); i = 0
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
    header = [1] * fn; body = bytearray(); field_dict = {f[0]: f[1] for f in fields}
    for tag in range(fn):
        if tag in field_dict:
            val = field_dict[tag]
            if val is None: header[tag] = 1
            elif isinstance(val, int):
                if 0 <= val <= 32766: header[tag] = (val + 1) * 2
                else: header[tag] = 0; body += struct.pack("<I", 8) + struct.pack("<q", val)
            elif isinstance(val, (str, bytes, bytearray)):
                if isinstance(val, str): v = val.encode('utf-8')
                else: v = val
                header[tag] = 0; body += struct.pack("<I", len(v)) + v
            elif isinstance(val, list):
                header[tag] = 0; list_bin = bytearray()
                for item in val:
                    if isinstance(item, (bytes, bytearray)): list_bin += struct.pack("<I", len(item)) + item
                    else: s = str(item).encode('utf-8'); list_bin += struct.pack("<I", len(s)) + s
                body += struct.pack("<I", len(list_bin)) + list_bin
        else: header[tag] = 1
    res = struct.pack("<H", fn)
    for h in header: res += struct.pack("<H", h)
    return bytes(res + body)

def decode_sproto(data, offset=0):
    if len(data) < offset + 2: return {}
    fn = struct.unpack("<H", data[offset:offset+2])[0]
    h_ptr, b_ptr = offset + 2, offset + 2 + fn*2
    fields, curr_tag = {}, -1
    for i in range(fn):
        curr_tag += 1; v = struct.unpack("<H", data[h_ptr + i*2 : h_ptr + i*2 + 2])[0]
        if v == 0:
            if b_ptr + 4 <= len(data):
                l = struct.unpack("<I", data[b_ptr:b_ptr+4])[0]
                fields[curr_tag] = data[b_ptr+4:b_ptr+4+l]
                b_ptr += 4 + l
        elif v == 1: pass
        elif v & 1: curr_tag += (v >> 1)
        else: fields[curr_tag] = (v >> 1) - 1
    return fields

def handle_http_request(conn, addr, initial_data):
    try:
        request_text = initial_data.decode('utf-8', 'ignore')
        while "\r\n\r\n" not in request_text:
            chunk = conn.recv(1024)
            if not chunk: break
            request_text += chunk.decode('utf-8', 'ignore')
        lines = request_text.split("\r\n")
        if not lines: return
        first_line = lines[0].split(" ")
        if len(first_line) < 2: return
        path = first_line[1].lstrip("/")
        print(f"[HTTP] GET /{path} from {addr}")
        clean_path = os.path.normpath(path).replace("..", "")
        if os.path.exists(clean_path) and os.path.isfile(clean_path):
            with open(clean_path, "rb") as f: content = f.read()
            response = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(content)).encode() + b"\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n\r\n"
            conn.sendall(response + content)
        else:
            conn.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
    except Exception: traceback.print_exc()
    finally: conn.close()

def client_handler(conn, addr):
    try:
        peek_data = conn.recv(4, socket.MSG_PEEK)
        if peek_data.startswith(b"GET "):
            handle_http_request(conn, addr, b"")
            return
            
        print(f"[+] Sproto Connection: {addr}")
        while True:
            h = conn.recv(2)
            if not h: break
            size = struct.unpack(">H", h)[0]
            data = b""
            while len(data) < size:
                chunk = conn.recv(size - len(data))
                if not chunk: break
                data += chunk
            
            raw = sproto_unpack(data); pkg = decode_sproto(raw, 0)
            msg_type, session = pkg.get(0), pkg.get(1)
            body_off = 2 + (struct.unpack("<H", raw[:2])[0] * 2); body = decode_sproto(raw, body_off)

            if msg_type == 2: # visitor
                uid = generate_unique_id(); key = generate_unique_password()
                accounts[uid] = key; save_accounts(accounts)
                print(f"[REGISTER] {uid}")
                resp = encode_sproto([(0, uid), (1, key), (2, 0)], fn=3)
                pkg_h = encode_sproto([(1, session)], fn=2)
                full = sproto_pack(pkg_h + resp); conn.sendall(struct.pack(">H", len(full)) + full)

            elif msg_type == 3: # verfiy (Full Original Server List)
                req_id = body.get(0, b"").decode('utf-8', 'ignore')
                req_key = body.get(1, b"").decode('utf-8', 'ignore')
                print(f"[VERIFY] {req_id}")
                resp_state = 0 if req_id in accounts and accounts[req_id] == req_key else 1
                
                # Ndërtimi i listës së serverave origjinalë
                server_list = [
                    encode_sproto([(0,11),(1,"America-01"),(2,GAME_HOST),(3,GAME_PORT),(4,1)], fn=11),
                    encode_sproto([(0,302),(1,"Europe-01"),(2,GAME_HOST),(3,GAME_PORT),(4,1)], fn=11),
                    encode_sproto([(0,602),(1,"Asia-01"),(2,GAME_HOST),(3,GAME_PORT),(4,1)], fn=11),
                    encode_sproto([(0,12),(1,"America-02"),(2,GAME_HOST),(3,GAME_PORT),(4,1)], fn=11),
                    encode_sproto([(0,303),(1,"Europe-02"),(2,GAME_HOST),(3,GAME_PORT),(4,1)], fn=11)
                ]
                
                # Tag 7=0 (Internal Assets) për të shmangur bllokimin në 90%
                resp = encode_sproto([
                    (0,resp_state), (1,random.randint(1000,9999)), (2,server_list),
                    (5,"1.012.017"), (6,"167"), (7,0), (8,"Welcome to Revival")
                ], fn=12)
                pkg_h = encode_sproto([(1, session)], fn=2)
                full = sproto_pack(pkg_h + resp); conn.sendall(struct.pack(">H", len(full)) + full)

            elif msg_type == 118: # random_name
                name = get_random_name()
                print(f"[RANDOM NAME] {name}")
                resp = encode_sproto([(0, name)], fn=1)
                pkg_h = encode_sproto([(1, session)], fn=2)
                full = sproto_pack(pkg_h + resp); conn.sendall(struct.pack(">H", len(full)) + full)

            elif msg_type == 218: # heartbeat
                pkg_h = encode_sproto([(1, session)], fn=2)
                full = sproto_pack(pkg_h); conn.sendall(struct.pack(">H", len(full)) + full)

    except Exception: pass
    finally: conn.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM); server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT)); server.listen(20)
print(f"LOGIN SERVER READY ON {PORT}")
print(f"HTTP ASSET SERVER READY")
while True:
    c, a = server.accept(); threading.Thread(target=client_handler, args=(c, a), daemon=True).start()
