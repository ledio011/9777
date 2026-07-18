import socket
import threading
import struct
import random
import string


PORT = 9777


# =========================
# SPROTO SERIALIZER
# =========================

class SprotoSerialize:

    def __init__(self):
        self.fields = []
        self.data = bytearray()
        self.last_tag = -1


    def write_tag(self, tag, value):

        skip = tag - self.last_tag - 1

        if skip > 0:
            self.fields.append(((skip - 1) * 2) + 1)

        self.fields.append(value)
        self.last_tag = tag


    def write_integer(self, value, tag):

        # small integer optimization
        encoded = (value + 1) * 2

        self.write_tag(tag, encoded)


    def write_string(self, value, tag):

        self.write_tag(tag, 0)

        b = value.encode("utf-8")

        self.data.extend(
            struct.pack("<I", len(b))
        )

        self.data.extend(b)



    def build(self):

        result = bytearray()

        # field count
        result.extend(
            struct.pack("<H", len(self.fields))
        )


        # header fields
        for f in self.fields:
            result.extend(
                struct.pack("<H", f)
            )


        # body
        result.extend(self.data)


        return bytes(result)



# =========================
# SPROTO PACK
# =========================

def sproto_pack(data):

    out = bytearray()

    for i in range(0,len(data),8):

        block = data[i:i+8]

        block = block.ljust(8,b"\x00")


        mask = 0
        values = []


        for j,b in enumerate(block):

            if b != 0:

                mask |= (1 << j)
                values.append(b)



        out.append(mask)

        out.extend(values)


    return bytes(out)



# =========================
# CREATE VISITOR RESPONSE
# =========================

def create_visitor_response(session):


    guest_id = str(
        random.randint(
            100000000000,
            999999999999
        )
    )


    key = ''.join(
        random.choice(
            string.ascii_letters + string.digits
        )
        for _ in range(10)
    )


    print("===================")
    print("NEW ACCOUNT")
    print("ID :", guest_id)
    print("KEY:", key)
    print("===================")



    # Package header
    pkg = SprotoSerialize()

    # tag 1 = session
    pkg.write_integer(
        session,
        1
    )


    package = pkg.build()



    # visitor.response

    visitor = SprotoSerialize()


    # tag 0 id
    visitor.write_string(
        guest_id,
        0
    )


    # tag 1 key
    visitor.write_string(
        key,
        1
    )


    # tag 2 state
    visitor.write_integer(
        0,
        2
    )


    body = visitor.build()



    final = package + body


    packed = sproto_pack(final)



    packet = (
        struct.pack(">H",len(packed))
        +
        packed
    )


    return packet




# =========================
# CLIENT HANDLER
# =========================

def handle_client(client,address):

    print("[+] Client:",address)


    try:

        while True:

            data = client.recv(1024)


            if not data:
                break



            print("RX:",
                  data.hex()
            )


            # visitor request
            if data.hex().endswith("020604"):


                # nga paketa jote:
                # 0004 1502 0604
                #
                # session = 1


                response = create_visitor_response(1)


                client.send(response)


                print(
                    "visitor.response SENT"
                )



    except Exception as e:

        print(
            "[ERROR]",
            e
        )


    finally:

        client.close()

        print(
            "Disconnected",
            address
        )




# =========================
# SERVER
# =========================


server = socket.socket(
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


print("======================")
print("9777 SERVER RUNNING")
print("======================")


while True:


    client,address = server.accept()


    threading.Thread(
        target=handle_client,
        args=(client,address)
    ).start()
