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
                body += struct.pack("<I", 4) + struct.pack("<I", value & 0xFFFFFFFF)
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
    records = []
    for idx in range(fn):
        pos = offset + 2 + idx * 2
        records.append(struct.unpack("<H", data[pos:pos + 2])[0])

    body_pos = offset + 2 + fn * 2
    fields = {}
    current_tag = -1

    for record in records:
        current_tag += 1
        if record == 1:
            fields[current_tag] = None
            continue
        if record & 1:
            current_tag += record // 2
            continue
        if record == 0:
            size = struct.unpack("<I", data[body_pos:body_pos + 4])[0]
            body_pos += 4
            fields[current_tag] = data[body_pos:body_pos + size]
            body_pos += size
        else:
            fields[current_tag] = record // 2 - 1

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


def build_game_server(server_id, name, host, port, state=0):
    return encode_sproto([
        (0, server_id),
        (1, name),
        (2, host),
        (3, port),
        (4, state),
        (6, 1),
        (7, 1),
    ])


def build_visitor_response(uid, key, state=0):
    return encode_sproto([(0, uid), (1, key), (2, state)])


def build_verify_response(session, game_servers, state=0):
    return encode_sproto([
        (0, state),
        (1, session),
        (3, "1"),
        (4, 0),
        (5, "1.012.017"),
        (6, "200"),
        (7, 0),
        (8, "Welcome!"),
        (9, "1.0"),
    ])


def build_update_game_server_response(game_servers):
    return encode_sproto([(2, game_servers)])


def handle_message(msg, session, body=None):
    if msg == 2:
        uid = "68" + "".join(str(random.randint(0, 9)) for _ in range(12))
        key = "".join(str(random.randint(0, 9)) for _ in range(12))
        accounts[uid] = key
        save_accounts(accounts)
        return build_visitor_response(uid, key, 0)

    if msg == 3:
        servers = [
            build_game_server(1, "Europe", GAME_HOST, 48282, 0),
            build_game_server(2, "Asia", GAME_HOST, 48282, 0),
            build_game_server(3, "America", GAME_HOST, 48282, 0),
        ]
        return build_verify_response(session, servers, 0)

    if msg == 4:
        return encode_sproto([
            (0, 1),
            (1, "1.012.017"),
            (2, "200"),
            (3, 0)
        ])

    if msg == 7:
        servers = [
            build_game_server(1, "Europe", GAME_HOST, 48282, 0),
            build_game_server(2, "Asia", GAME_HOST, 48282, 0),
            build_game_server(3, "America", GAME_HOST, 48282, 0),
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
        if os.path.exists(path) and os.path.isfile(path):
            with open(path, "rb") as f:
                content = f.read()
            response = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(content)).encode() + b"\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n\r\n"
            conn.sendall(response + content)
        else:
            conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")
    except Exception:
        pass
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
