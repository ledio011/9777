# ==========================================================
# AUTO THEFT GANGSTERS REVIVAL - STABLE v13 FINAL GAMEPLAY
# GAME SERVER 9555
# ==========================================================
import socket, struct, threading, random, json, os, time, traceback

PORT = int(os.environ.get("PORT", 9555))
CHAR_DB = "characters_final.json"
server_session_counter = 8000

def load_chars():
    if os.path.exists(CHAR_DB):
        try:
            with open(CHAR_DB, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_chars(data):
    try:
        with open(CHAR_DB, "w") as f: json.dump(data, f, indent=4)
    except: pass

all_accounts_chars = load_chars()

def generate_unique_char_id():
    global all_accounts_chars
    existing_ids = set()
    for acc in all_accounts_chars.values():
        for c in acc:
            existing_ids.add(c['id'])
    while True:
        new_id = random.randint(1000000, 9999999)
        if new_id not in existing_ids:
            return new_id

def encode_sproto(fields, fn=None):
    if not fields: return struct.pack("<H", 0)
    fields.sort(key=lambda x: x[0])
    header = []; body = bytearray(); last_tag = -1
    for tag, val in fields:
        skip = tag - last_tag - 1
        if skip > 0: header.append(2 * (skip - 1) + 1)

        if val is None:
            header.append(1)
        elif isinstance(val, bool):
            header.append((1 if val else 0) * 2 + 2)
        elif isinstance(val, int):
            if 0 <= val <= 32766:
                header.append((val + 1) * 2)
            else:
                header.append(0)
                body += struct.pack("<I", 8) + struct.pack("<q", val)
        elif isinstance(val, (str, bytes, bytearray, list, dict)):
            header.append(0)
            if isinstance(val, str):
                v = val.encode('utf-8')
            elif isinstance(val, list):
                # Sproto array of structs/strings: each item must have its own 4-byte length prefix
                v = b"".join([struct.pack("<I", len(item)) + item if isinstance(item, (bytes, bytearray)) else item for item in val])
            elif isinstance(val, dict):
                # Sproto maps are encoded as arrays of objects (structs)
                v = b"".join([struct.pack("<I", len(item)) + item if isinstance(item, (bytes, bytearray)) else item for item in val.values()])
            else:
                v = val
            body += struct.pack("<I", len(v)) + v
        last_tag = tag

    fn_val = fn if fn is not None else len(header)
    res = struct.pack("<H", fn_val)
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

def decode_sproto(data, offset=0):
    if len(data) < offset + 2: return {}
    fn = struct.unpack("<H", data[offset:offset+2])[0]
    h_ptr, b_ptr = offset + 2, offset + 2 + fn*2
    fields, curr_tag = {}, -1
    for i in range(fn):
        v = struct.unpack("<H", data[h_ptr + i*2 : h_ptr + i*2 + 2])[0]
        if v == 0:
            curr_tag += 1
            if b_ptr + 4 <= len(data):
                l = struct.unpack("<I", data[b_ptr:b_ptr+4])[0]
                fields[curr_tag] = data[b_ptr+4:b_ptr+4+l]
                b_ptr += 4 + l
        elif v == 1:
            curr_tag += 1
        elif v & 1:
            curr_tag += (v >> 1) + 1
        else:
            curr_tag += 1
            fields[curr_tag] = (v >> 1) - 1
    return fields

def get_visual(name, prof):
    m = {0:{"m":"XD_A","h":"XD_A_T","b":"XD_A_S","l":"XD_A_X","w":"XD_A_WQ"},
         1:{"m":"QJ_A","h":"QJ_A_T","b":"QJ_A_S","l":"QJ_A_X","w":"QJ_A_WQ"},
         2:{"m":"NQS_A","h":"NQS_A_T","b":"NQS_A_S","l":"NQS_A_X","w":"NQS_A_WQ"}}
    v = m.get(prof, m[1])
    return encode_sproto([(0, name), (1, v["m"]), (2, v["h"]), (3, v["b"]), (4, v["l"]), (5, v["w"]), (10, 0)])

def get_general(c):
    return encode_sproto([
        (0, c['name']),
        (1, c.get('prof', 0)),
        (2, 1), # lineIndex
        (3, "11"), # mapInfoId
        (4, 1) # tutorial finish
    ])

def get_movement(x, y, z):
    # Matches SprotoType.position (Tags 0-3: x, y, z, o) and MapInfoData BirthPos
    pos = encode_sproto([(0, x), (1, y), (2, z), (3, 0)])
    return encode_sproto([(0, pos), (1, pos)])

def get_char_ov(c):
    gen = get_general(c)
    attr = encode_sproto([(0, 1), (1, 5000)]) # level, combValue
    return encode_sproto([
        (0, c['id']),
        (1, gen),
        (2, attr),
        (3, get_visual(c['name'], c.get('prof', 0))),
        (4, int(time.time())),
        (5, 0) # forbidden
    ])

def get_full_char(c):
    gen = get_general(c)
    # attribute_other: hp(0), exp(1), level(2), combValue(3), camp(15)
    # Matches BaseLvData for Level 1: HP 3000
    attr_oth = encode_sproto([(0, 3000), (1, 0), (2, 1), (3, 5000), (15, 1)])
    # property: money tags 13-18
    prop = encode_sproto([(13, 1000), (14, 1000), (15, 1000), (16, 1000), (17, 1000), (18, 1000)])
    # BirthPos from MapInfoData Map ID 11: 7007, 100, 5033
    mv = get_movement(7007, 100, 5033)
    # runtime_agent: attribute(6) -> max_hp(0), atk(2), def(3)
    # Matches BaseLvData Level 1 Warrior: HP 3000, ATK 300, DEF 35
    attr_run = encode_sproto([(0, 3000), (2, 300), (3, 35)])
    # attribute_all: mov(13) is required for speed calculation
    attr_all = encode_sproto([(0, 3000), (2, 300), (3, 35), (13, 500)])
    run = encode_sproto([(6, attr_run), (7, attr_all)])

    return encode_sproto([
        (0, c['id']),
        (1, gen),
        (2, attr_oth),
        (5, prop),
        (6, get_visual(c['name'], c.get('prof', 0))),
        (7, mv),
        (12, 0), # potionIndex
        (13, run),
        (15, 2)  # download finish
    ])

def get_char_aoi(c):
    # character_aoi: id(0), visual(1), general(2), attribute_other(3), movement(5), runtime(6)
    attr_oth = encode_sproto([(0, 3000), (2, 1)])
    # BirthPos from MapInfoData Map ID 11: 7007, 100, 5033
    mv = get_movement(7007, 100, 5033)
    attr_run = encode_sproto([(0, 3000)])
    attr_all = encode_sproto([(0, 3000), (13, 500)])
    run = encode_sproto([(6, attr_run), (7, attr_all)])
    return encode_sproto([
        (0, c['id']),
        (1, get_visual(c['name'], c.get('prof', 0))),
        (2, get_general(c)),
        (3, attr_oth),
        (5, mv),
        (6, run)
    ])

def client_handler(conn, addr):
    print(f"[+] Connected: {addr}"); acc_id = "0"; picked_char = None
    global server_session_counter

    def send_rpc_push(tag, data):
        try:
            global server_session_counter
            server_session_counter += 1
            ph_p = encode_sproto([(0, tag), (1, server_session_counter)])
            pf_p = sproto_pack(ph_p + data)
            conn.sendall(struct.pack(">H", len(pf_p)) + pf_p)
            print(f"[TX] PUSH TAG={tag} SIZE={len(data)}")
        except Exception: pass

    try:
        while True:
            h_bytes = conn.recv(2)
            if not h_bytes: break
            size = struct.unpack(">H", h_bytes)[0]
            data = b""
            while len(data) < size:
                chunk = conn.recv(size - len(data))
                if not chunk: break
                data += chunk
            if len(data) < size: break

            raw = sproto_unpack(data); pkg = decode_sproto(raw, 0)
            msg, session = pkg.get(0), pkg.get(1)
            print(f"[RX] MSG={msg} SESSION={session}")
            off = 2 + (struct.unpack("<H", raw[:2])[0] * 2); body = decode_sproto(raw, off)
            print("BODY =", body)

            if msg == 4: # login
                acc_id = body.get(1, b"").decode('utf-8') if isinstance(body.get(1), bytes) else str(body.get(1))
                resp = encode_sproto([
                    (0, 2),
                    (1, "1.012.017"),
                    (2, "200"),
                    (3, 1)
                ])
                ph = encode_sproto([(1, session)])
                pf = sproto_pack(ph + resp)
                conn.sendall(struct.pack(">H", len(pf)) + pf)

            elif msg == 103: # character_list
                chars = all_accounts_chars.get(acc_id, [])

                if not chars:
                    cid = generate_unique_char_id()
                    nc = {
                        "id": cid,
                        "name": "Survivor",
                        "prof": 1
                    }
                    all_accounts_chars[acc_id] = [nc]
                    save_chars(all_accounts_chars)
                    chars = [nc]

                resp = encode_sproto([
                    (0, [get_char_ov(c) for c in chars])
                ])
                ph = encode_sproto([(1, session)])
                pf = sproto_pack(ph + resp)
                conn.sendall(struct.pack(">H", len(pf)) + pf)

            elif msg == 104: # character_create
                c_data = decode_sproto(body.get(0, b""))
                name = c_data.get(0, b"").decode('utf-8') if isinstance(c_data.get(0), bytes) else "Hero"
                prof = c_data.get(1, 0)
                cid = generate_unique_char_id()
                if acc_id not in all_accounts_chars: all_accounts_chars[acc_id] = []
                nc = {'id': cid, 'name': name, 'prof': prof}
                all_accounts_chars[acc_id].append(nc); save_chars(all_accounts_chars)
                resp = encode_sproto([(0, get_char_ov(nc)), (1, 0)])
                ph = encode_sproto([(1, session)])
                pf = sproto_pack(ph + resp)
                conn.sendall(struct.pack(">H", len(pf)) + pf)

            elif msg == 105: # character_pick
                char_id = body.get(0)
                print("CHAR PICK REQUEST ID =", char_id)

                if isinstance(char_id, bytes):
                    char_id = int.from_bytes(char_id, "little")

                picked_char = next(
                    (c for c in all_accounts_chars.get(acc_id, [])
                     if c['id'] == char_id),
                    None
                )

                if picked_char:
                    print("CHARACTER PICK SUCCESS:", picked_char)
                    resp = encode_sproto([(0, 1)]) # Success
                else:
                    print("CHARACTER NOT FOUND")
                    resp = encode_sproto([(0, 0)]) # Error

                ph = encode_sproto([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(ph + resp))) + sproto_pack(ph + resp))
                if picked_char:
                    # 1. enter_map
                    send_rpc_push(503, encode_sproto([(0, "11"), (1, 1), (2, 1)]))
                    # 2. main_player_create (Must happen before map_ready to unblock loading)
                    send_rpc_push(504, encode_sproto([(0, get_full_char(picked_char))]))
                    # 3. aoi_add
                    send_rpc_push(505, encode_sproto([(0, get_char_aoi(picked_char))]))
                    # 4. sync_common_data
                    send_rpc_push(614, encode_sproto([(0, int(time.time())), (13, 1)]))
                    # 5. start_enter_game
                    send_rpc_push(654, encode_sproto([(0, 1)]))

            elif msg == 100: # map_ready
                if picked_char:
                    print("[*] Map Ready received. World entry confirmed.")

            elif msg == 118: # random name
                names = ["John", "Mary", "William", "Smith", "Michael", "James", "Lisa", "Robert"]
                name = f"{random.choice(names)}_{random.randint(100,999)}"
                resp = encode_sproto([(0, name)])
                ph = encode_sproto([(1, session)])
                pf = sproto_pack(ph + resp)
                conn.sendall(struct.pack(">H", len(pf)) + pf)

            elif msg == 218: # heart_beat
                resp = encode_sproto([(0, body.get(0, 0)), (1, int(time.time() * 1000))])
                ph = encode_sproto([(1, session)])
                pf = sproto_pack(ph + resp)
                conn.sendall(struct.pack(">H", len(pf)) + pf)

            else:
                ph = encode_sproto([(1, session)])
                pf = sproto_pack(ph + encode_sproto([]))
                conn.sendall(struct.pack(">H", len(pf)) + pf)

    except: traceback.print_exc()
    finally: conn.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM); server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT)); server.listen(20)
print(f"GAME SERVER 9555 READY (STABLE v13 FINAL GAMEPLAY)");
while True: cl, ad = server.accept(); threading.Thread(target=client_handler, args=(cl, ad), daemon=True).start()
