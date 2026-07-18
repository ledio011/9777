import socket
import struct
import random
import threading


PORT = 9777


# -------------------------
# SPROTO SERIALIZER
# -------------------------

class SprotoSerializer:

    def __init__(self):
        self.fields = []

    def write_integer(self, tag, value):
        # small integer
        self.fields.append((tag, "int", value))

    def write_string(self, tag, value):
        self.fields.append((tag, "str", value))


    def encode(self):

        header = bytearray()
        body = bytearray()

        header_count = len(self.fields)

        header.extend(struct.pack("<H", header_count))


        for tag, typ, value in self.fields:

            if typ == "int":

                # small integer optimization
                if value < 32767:
                    data = (value + 1) * 2
                    header.extend(struct.pack("<H", data))
                else:
                    header.extend(struct.pack("<H",0))
                    body.extend(struct.pack("<I",4))
                    body.extend(struct.pack("<I",value))


            elif typ == "str":

                header.extend(struct.pack("<H",0))

                raw = value.encode()

                body.extend(struct.pack("<I",len(raw)))
                body.extend(raw)


        return bytes(header + body)



# -------------------------
# SPROTO PACK
# -------------------------

def sproto_pack(data):

    out = bytearray()

    for i in range(0,len(data),8):

        chunk=data[i:i+8]

        chunk=chunk.ljust(8,b"\x00")

        mask=0
        values=[]

        for j,b in enumerate(chunk):

            if b != 0:
                mask |= (1<<j)
                values.append(b)


        out.append(mask)

        out.extend(values)


    return bytes(out)



# -------------------------
# CREATE VISITOR RESPONSE
# -------------------------

def create_visitor_response(session,id,key):


    # Package header
    package=SprotoSerializer()

    # tag 1 = session
    package.write_integer(1,session)

    package_data=package.encode()



    # visitor.response

    visitor=SprotoSerializer()


    # tag 0 = id
    visitor.write_string(
        0,
        id
    )


    # tag 1 = key
    visitor.write_string(
        1,
        key
    )


    # tag 2 = state
    visitor.write_integer(
        2,
        0
    )


    visitor_data=visitor.encode()



    final_data = package_data + visitor_data


    packed=sproto_pack(final_data)


    packet = struct.pack(
        ">H",
        len(packed)
    ) + packed


    return packet



# -------------------------
# RANDOM ACCOUNT
# -------------------------

def create_id():

    length=random.randint(15,18)

    return "".join(
        random.choice("0123456789")
        for _ in range(length)
    )


def create_key():

    length=random.randint(12,15)

    return "".join(
        random.choice("0123456789")
        for _ in range(length)
    )



# -------------------------
# SESSION READ
# -------------------------

def get_session(data):

    try:

        # për paketat që kemi parë
        # session zakonisht është byte i fundit

        return data[-1]

    except:

        return 1



# -------------------------
# CLIENT HANDLER
# -------------------------

def handle_client(client,address):

    print("[+] Client:",address)

    try:

        while True:

            data=client.recv(2048)


            if not data:
                break



            print("RX:",
                  data.hex())



            # visitor request
            if b"\x15\x02" in data:


                session=get_session(data)


                player_id=create_id()

                player_key=create_key()



                print("===================")
                print("ID :",player_id)
                print("KEY:",player_key)
                print("===================")



                response=create_visitor_response(
                    session,
                    player_id,
                    player_key
                )


                print(
                    "RAW RESPONSE:",
                    response.hex()
                )


                client.sendall(response)


                print(
                    "visitor.response SENT"
                )



            else:

                print(
                    "Unknown packet"
                )



    except Exception as e:

        print(
            "ERROR:",
            e
        )


    finally:

        client.close()

        print(
            "Disconnected",
            address
        )



# -------------------------
# SERVER START
# -------------------------

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


print("===================")
print("9777 SERVER RUNNING")
print("===================")



while True:

    client,address=server.accept()


    t=threading.Thread(
        target=handle_client,
        args=(client,address)
    )

    t.start()
