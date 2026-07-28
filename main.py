import json
import os
import random
import socket
import struct
import threading
import traceback

PORT = int(os.environ.get("PORT", 9777))
DB_FILE = "accounts.json"
GAME_HOST = "tokaido.proxy.rlwy.net"
GAME_PORT = 48282


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
            header.append((1 if value else 0) * 2)
        elif isinstance(value, int):
            if 0 <= value <= 32766:
                header.append((value + 1) * 2)
            else:
                header.append(0)
                if -2147483648 <= value <= 2147483647:
                    body += struct.pack("<I", 4) + struct.pack("<i", value)
                else:
                    body += struct.pack("<I", 8) + struct.pack("<q", value)
        elif isinstance(value, (str, bytes, bytearray, list, dict)):
            header.append(0)
            if isinstance(value, str):
                v = value.encode('utf-8')
            elif isinstance(value, list):
                if value and isinstance(value[0], int):
                    v = b"\x04" + b"".join([struct.pack("<i", item) for item in value])
                else:
                    items = []
                    for item in value:
                        if isinstance(item, str): item = item.encode('utf-8')
                        elif isinstance(item, (bytes, bytearray)): pass
                        else: item = str(item).encode('utf-8')
                        items.append(struct.pack("<I", len(item)) + item)
                    v = b"".join(items)
            elif isinstance(value, dict):
                items = []
                for item in value.values():
                    if isinstance(item, str): item = item.encode('utf-8')
                    if isinstance(item, (bytes, bytearray)):
                        items.append(struct.pack("<I", len(item)) + item)
                    else:
                        items.append(struct.pack("<I", 1) + (b'\x01' if item else b'\x00'))
                v = b"".join(items)
            else:
                v = value
            body += struct.pack("<I", len(v)) + v

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
    # Matches SprotoType.game_server (Tags 0-10) and ServerData table
    return encode_sproto([
        (0, server_id),   # serverId
        (1, name),        # serverName
        (2, host),        # serverIP
        (3, port),        # serverPort
        (4, 1),           # serverState: 1=Normal (Yellow in GameDefine.cs)
        (5, -4),          # serverPlayerState: -4=Normal load
        (6, area),        # serverArea: 1=Europe, 0=America, 2=Asia
        (7, 1),           # serverRank
        (8, timezone),    # serverTimeZone
        (9, 1),           # serverWeight
        (10, 0),          # newServer: 0=Old
    ])


def build_visitor_response(uid, key, state=0):
    return encode_sproto([(0, uid), (1, key), (2, state)])


def build_verify_response(session, game_servers, state=0):
    return encode_sproto([
        (0, state),
        (1, session),
        (2, [struct.pack("<I", len(s)) + s for s in game_servers]),
        (3, "302#303"), # Recommended Europe servers
        (5, "1.012.017"),
        (6, "200"),
        (7, 0),
        (8, "Welcome to Auto Theft Revival!"),
    ])


def build_update_game_server_response(game_servers):
    return encode_sproto([(2, [struct.pack("<I", len(s)) + s for s in game_servers])])


def handle_message(msg, session, body=None):
    if msg == 2:
        uid = "68" + "".join(str(random.randint(0, 9)) for _ in range(12))
        key = "".join(str(random.randint(0, 9)) for _ in range(12))
        accounts[uid] = key
        save_accounts(accounts)
        return build_visitor_response(uid, key, 0)

    if msg == 3:
        # Data from ServerData table
        servers = [
            # Europe (Area 1)
            build_game_server(302, "EU-001(UTC+1)", GAME_HOST, GAME_PORT, 1, 1),
            build_game_server(303, "EU-002(UTC+1)", GAME_HOST, GAME_PORT, 1, 1),
            build_game_server(304, "EU-003(UTC+1)", GAME_HOST, GAME_PORT, 1, 1),
            build_game_server(305, "EU-004(UTC+1)", GAME_HOST, GAME_PORT, 1, 1),
            # Asia (Area 2)
            build_game_server(602, "AS-001(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(603, "AS-002(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(604, "AS-003(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(605, "AS-004(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(606, "AS-005(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(607, "AS-006(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            # America (Area 0)
            build_game_server(11, "AM-001(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
            build_game_server(12, "AM-002(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
            build_game_server(13, "AM-003(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
            build_game_server(14, "AM-004(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
            build_game_server(15, "AM-005(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
        ]
        return build_verify_response(session, servers, 0)

    if msg == 4:
        # Matches login.response (Tag 4)
        return encode_sproto([
            (0, 2),              # type: 2=Login Success
            (1, "1.012.017"),    # versionCode
            (2, "200"),          # dataVersionCode
            (3, 1)               # serverLevel
        ])

    if msg == 7:
        # Matches update_game_server (Tag 7)
        # Data from ServerData table
        servers = [
            # Europe (Area 1)
            build_game_server(302, "EU-001(UTC+1)", GAME_HOST, GAME_PORT, 1, 1),
            build_game_server(303, "EU-002(UTC+1)", GAME_HOST, GAME_PORT, 1, 1),
            build_game_server(304, "EU-003(UTC+1)", GAME_HOST, GAME_PORT, 1, 1),
            build_game_server(305, "EU-004(UTC+1)", GAME_HOST, GAME_PORT, 1, 1),
            # Asia (Area 2)
            build_game_server(602, "AS-001(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(603, "AS-002(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(604, "AS-003(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(605, "AS-004(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(606, "AS-005(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            build_game_server(607, "AS-006(UTC+6)", GAME_HOST, GAME_PORT, 2, 6),
            # America (Area 0)
            build_game_server(11, "AM-001(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
            build_game_server(12, "AM-002(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
            build_game_server(13, "AM-003(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
            build_game_server(14, "AM-004(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
            build_game_server(15, "AM-005(UTC-4)", GAME_HOST, GAME_PORT, 0, -4),
        ]
        return build_update_game_server_response(servers)

    if msg == 118:
        names = ["John", "Mary", "William", "Smith", "Michael", "James", "David", "Chris", "Lisa", "Robert"]
        name = f"{random.choice(names)}_{random.randint(100, 999)}"
        return encode_sproto([(0, name)])

    if msg == 218:
        return encode_sproto([])

    return encode_sproto([])


def handle_http_request(conn, addr, initial_data):
    try:
        request_text = initial_data.decode("utf-8", "ignore")
        while "\r\n\r\n" not in request_text:
            chunk = conn.recv(1024)
            if not chunk:
                break
            request_text += chunk.decode("utf-8", "ignore")
        lines = request_text.split("\r\n")
        if not lines:
            return
        path = lines[0].split(" ")[1].lstrip("/")
        print(f"[HTTP] GET /{path}")

        # Priority: exact path, then assets/path
        full_path = path
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            full_path = os.path.join("assets", path)

        if os.path.exists(full_path) and os.path.isfile(full_path):
            with open(full_path, "rb") as f:
                content = f.read()
            response = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(content)).encode() + b"\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n\r\n"
            conn.sendall(response + content)
        else:
            print(f"[HTTP] 404: {path} (tried {full_path})")
            conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")
    except Exception:
        traceback.print_exc()
    finally:
        conn.close()


def client_handler(conn, addr):
    print(f"[+] Login Connection from: {addr}")
    try:
        peek = conn.recv(4, socket.MSG_PEEK)
        if peek.startswith(b"GET "):
            handle_http_request(conn, addr, b"")
            return

        while True:
            h_bytes = conn.recv(2)
            if not h_bytes:
                break
            size = struct.unpack(">H", h_bytes)[0]
            data = b""
            while len(data) < size:
                data += conn.recv(size - len(data))

            raw = sproto_unpack(data)
            pkg = decode_sproto(raw, 0)
            msg = pkg.get(0)
            session = pkg.get(1)
            print(f"[RX] MSG {msg} Session {session} RawLen {len(raw)}")

            response_body = handle_message(msg, session, None)
            print("[TX BODY]", response_body.hex(), "LEN", len(response_body))

            response = encode_sproto([
                (1, session)
            ]) + response_body

            full = sproto_pack(response)
            conn.sendall(struct.pack(">H", len(full)) + full)
    except Exception:
        traceback.print_exc()
    finally:
        conn.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(20)
    print(f"ORIGINAL LOGIN SERVER READY ON {PORT}")
    while True:
        client, addr = server.accept()
        threading.Thread(target=client_handler, args=(client, addr), daemon=True).start()


if __name__ == "__main__":
    start_server()
