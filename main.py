import socket
import struct
import threading
import random

PORT = 9555

def sproto_pack(data):
    padding = (8 - (len(data) % 8)) % 8
    data += b'\x00' * padding
    out = bytearray()
    for i in range(0, len(data), 8):
        chunk = data[i:i+8]
        mask = 0
        values = bytearray()
        for j, b in enumerate(chunk):
            if b != 0:
                mask |= (1 << j)
                values.append(b)
        out.append(mask)
        out.extend(values)
    return bytes(out)

def sproto_unpack(data):
    out = bytearray()
    i = 0
    while i < len(data):
        mask = data[i]
        i += 1
        for bit in range(8):
            if mask & (1 << bit):
                if i < len(data):
                    out.append(data[i])
                    i += 1
            else:
                out.append(0)
    return bytes(out)

def encode_sproto(fields):
    if not fields: return struct.pack("<H", 0)
    fields.sort(key=lambda x: x[0])
    header = bytearray()
    body = bytearray()
    last_tag = -1
    for tag, value in fields:
        skip = tag - last_tag - 1
        if skip > 0: header += struct.pack("<H", (skip - 1) * 2 + 1)
        if value is None:
            header += struct.pack("<H", 0)
            body += struct.pack("<I", 0)
        elif isinstance(value, int):
            if 0 <= value <= 32766: header += struct.pack("<H", (value + 1) * 2)
            else:
                header += struct.pack("<H", 0)
                body += struct.pack("<I", 4) + struct.pack("<i", value)
        elif isinstance(value, (str, bytes, bytearray)):
            if isinstance(value, str): value = value.encode('utf-8')
            header += struct.pack("<H", 0)
            body += struct.pack("<I", len(value)) + value
        last_tag = tag
    return struct.pack("<H", len(header) // 2) + header + body

def client_handler(conn, addr):
    print(f"[+] Game Client: {addr}")
    try:
        while True:
            h = conn.recv(2)
            if not h: break
            size = struct.unpack(">H", h)[0]
            data = b""
            while len(data) < size:
                data += conn.recv(size - len(data))
            raw = sproto_unpack(data)
            fn = struct.unpack("<H", raw[:2])[0]
            header = raw[2:2+fn*2]
            msg_type, session = None, None
            idx, curr_tag = 0, 0
            while idx < len(header):
                val = struct.unpack("<H", header[idx:idx+2])[0]
                if val & 1: curr_tag += (val >> 1) + 1
                else:
                    real_val = (val >> 1) - 1
                    if curr_tag == 0: msg_type = real_val
                    if curr_tag == 1: session = real_val
                    curr_tag += 1
                idx += 2

            print(f"Game RX: {msg_type}")

            if msg_type == 4: # Login
                resp = encode_sproto([(0, 1), (1, "1.012.017"), (2, "0"), (3, 1)])
                pkg_h = encode_sproto([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(pkg_h + resp))) + sproto_pack(pkg_h + resp))

            elif msg_type == 103: # Char List
                body = encode_sproto([(0, None)])
                pkg_h = encode_sproto([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(pkg_h + body))) + sproto_pack(pkg_h + body))

            elif msg_type == 105: # Character Pick
                # 1. Success response (pa errno)
                pkg_h = encode_sproto([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(pkg_h))) + sproto_pack(pkg_h))
                # 2. Push Enter Map (Tag 503)
                map_pkt = sproto_pack(encode_sproto([(0, 503)]) + encode_sproto([(0, "3001")]))
                conn.sendall(struct.pack(">H", len(map_pkt)) + map_pkt)

            elif msg_type == 100: # Map Ready (TAG KRITIK!)
                # 3. Push Main Player Create (Tag 504)
                # Visual (Tag 6 ne character)
                visual = encode_sproto([(1,"1001"),(2,"1001"),(3,"1001"),(4,"1001")])
                # Attr (Tag 2 ne character)
                attr = encode_sproto([(0,1000),(2,1)])
                # Property (Tag 5 ne character) - Tags 13-18 per parate!
                prop = encode_sproto([(13,1000),(14,1000)])
                # General (Tag 1 ne character)
                gen = encode_sproto([(0,"Player"),(1,0),(3,"3001")])

                char_obj = encode_sproto([(0, random.randint(1000,9999)),(1,gen),(2,attr),(5,prop),(6,visual)])
                main_pkt = sproto_pack(encode_sproto([(0, 504)]) + encode_sproto([(0, char_obj)]))
                conn.sendall(struct.pack(">H", len(main_pkt)) + main_pkt)

            elif msg_type == 218: # Heartbeat
                pkg_h = encode_sproto([(1, session)])
                conn.sendall(struct.pack(">H", len(sproto_pack(pkg_h))) + sproto_pack(pkg_h))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT))
server.listen(10)
print(f"GAME SERVER {PORT} READY")
while True:
    c, a = server.accept()
    threading.Thread(target=client_handler, args=(c, a), daemon=True).start()
