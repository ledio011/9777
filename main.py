import socket
import struct
import threading
import random


PORT = 9777


def sproto_pack(data):
    packed = bytearray()

    for i in range(0, len(data), 8):
        chunk = data[i:i+8]

        if len(chunk) < 8:
            chunk += b'\x00' * (8-len(chunk))

        mask = 0
        values = bytearray()

        for j in range(8):
            if chunk[j] != 0:
                mask |= (1 << j)
                values.append(chunk[j])

        packed.append(mask)
        packed.extend(values)

    return bytes(packed)



def sproto_string(text):
    b=text.encode()
    return struct.pack("<I",len(b))+b



def make_header(fields):

    out=struct.pack("<H",len(fields))

    for x in fields:
        if x is None:
            out += struct.pack("<H",1)
        elif isinstance(x,int):
            out += struct.pack("<H",(x+1)*2)
        else:
            out += struct.pack("<H",0)

    return out



def visitor_response(session):

    pkg = make_header([
        None,
        session
    ])


    body = make_header([
        "",
        "",
        0
    ])

    body += sproto_string(
        str(random.randint(100000000000000000,
                           999999999999999999))
    )

    body += sproto_string(
        str(random.randint(100000000000,
                           999999999999))
    )


    data=pkg+body

    packed=sproto_pack(data)

    return struct.pack(">H",len(packed))+packed




def verify_response(session):


    pkg = make_header([
        None,
        session
    ])



    # verfiy.response fields 0-11

    response = make_header([

        0,      # state
        999,    # session
        "",     # game_server list
        None,
        None,
        "1.012.017",
        "1.012.017",
        0,
        "Welcome",
        "1"

    ])


    # game_server object

    server = make_header([

        1,
        "",
        "",
        9555,
        0

    ])

    server += sproto_string("Revival Server")
    server += sproto_string("127.0.0.1")


    # list length + object

    response += struct.pack("<I",len(server))
    response += server


    data=pkg+response

    packed=sproto_pack(data)

    return struct.pack(">H",len(packed))+packed





def client_thread(c,a):

    print("[+] Client",a)

    try:

        while True:

            data=c.recv(4096)

            if not data:
                break


            print("RX:",data.hex())


            # visitor request
            if b'\x15\x02' in data:

                print("Visitor request")

                c.sendall(
                    visitor_response(1)
                )

                print("visitor.response SENT")


            # verify request
            else:

                print("Verify request")

                c.sendall(
                    verify_response(2)
                )

                print("verfiy.response SENT")


    except Exception as e:
        print(e)


    c.close()
    print("Disconnected",a)




server=socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

server.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

server.bind(
    ("0.0.0.0",PORT)
)

server.listen(20)


print("LOGIN SERVER 9777 RUNNING")


while True:

    c,a=server.accept()

    threading.Thread(
        target=client_thread,
        args=(c,a)
    ).start()
