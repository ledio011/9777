# ==========================================================
# AUTO THEFT GANGSTERS REVIVAL
# GAME SERVER 9555
# FINAL MAP ENTRY FIX
# PART 1/3
# ==========================================================

import socket
import struct
import threading
import random
import json
import os
import time
import traceback


PORT = int(os.environ.get("PORT", 9555))

CHAR_DB = "characters.json"

server_session_counter = 5000


# ==========================================================
# DATABASE
# ==========================================================

def load_chars():

    if os.path.exists(CHAR_DB):

        try:
            with open(CHAR_DB, "r") as f:
                return json.load(f)

        except:
            return {}

    return {}



def save_chars(data):

    try:

        with open(CHAR_DB, "w") as f:
            json.dump(data, f, indent=4)

    except:

        pass



characters = load_chars()



# ==========================================================
# SPROTO PACK
# ==========================================================

def sproto_pack(data):

    out = bytearray()

    i = 0


    while i < len(data):

        chunk = data[i:i+8]


        if len(chunk) < 8:

            chunk += b"\x00" * (8-len(chunk))


        mask = 0


        for j in range(8):

            if chunk[j] != 0:

                mask |= (1 << j)



        out.append(mask)


        for j in range(8):

            if mask & (1 << j):

                out.append(chunk[j])


        i += 8


    return bytes(out)



# ==========================================================
# SPROTO UNPACK
# ==========================================================

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



# ==========================================================
# SPROTO ENCODE
# ==========================================================

def encode_sproto(fields, fn=None):

    fields = sorted(fields, key=lambda x:x[0])


    if fn is None:

        fn = fields[-1][0] + 1 if fields else 0



    header = [1] * fn

    body = bytearray()



    values = {tag:value for tag,value in fields}



    for tag in range(fn):


        if tag not in values:

            continue



        val = values[tag]



        if isinstance(val,int):


            if 0 <= val <= 32766:

                header[tag] = (val + 1) * 2


            else:

                header[tag] = 0

                body += struct.pack("<I",8)

                body += struct.pack("<q",val)



        elif isinstance(val,str):


            raw = val.encode("utf-8")


            header[tag] = 0

            body += struct.pack("<I",len(raw))

            body += raw



        elif isinstance(val,(bytes,bytearray)):


            header[tag] = 0

            body += struct.pack("<I",len(val))

            body += val



        elif isinstance(val,list):


            header[tag] = 0


            temp = bytearray()


            for item in val:


                if isinstance(item,(bytes,bytearray)):

                    temp += struct.pack("<I",len(item))

                    temp += item


                elif isinstance(item,int):

                    temp += struct.pack("<I",8)

                    temp += struct.pack("<q",item)


                else:

                    raw = str(item).encode()

                    temp += struct.pack("<I",len(raw))

                    temp += raw



            body += struct.pack("<I",len(temp))

            body += temp



        # DICT nuk dergohet me bosh
        # Sproto maps do trajtohen vec kur kemi strukturen reale



    result = struct.pack("<H",fn)


    for h in header:

        result += struct.pack("<H",h)



    result += body


    return bytes(result)



# ==========================================================
# SPROTO DECODE
# ==========================================================

def decode_sproto(data,offset=0):

    try:


        fn = struct.unpack(
            "<H",
            data[offset:offset+2]
        )[0]



        header_pos = offset + 2

        body_pos = offset + 2 + fn*2



        result = {}

        tag = 0



        for i in range(fn):


            h = struct.unpack(
                "<H",
                data[
                    header_pos+i*2:
                    header_pos+i*2+2
                ]
            )[0]



            if h == 1:

                pass



            elif h & 1:


                tag += h >> 1



            elif h != 0:


                result[tag] = (h >> 1)-1



            else:


                if body_pos+4 <= len(data):


                    size = struct.unpack(
                        "<I",
                        data[body_pos:body_pos+4]
                    )[0]


                    body_pos += 4


                    result[tag] = data[
                        body_pos:
                        body_pos+size
                    ]


                    body_pos += size



            tag += 1



        return result


    except:


        return {}

# ==========================================================
# PART 2/3
# CHARACTER STRUCTURES
# ==========================================================


def create_attribute():

    return encode_sproto([

        (0,10560),
        (1,0),
        (2,100),
        (3,50),
        (4,0),
        (5,0),
        (6,0),
        (7,0),
        (8,0),
        (9,0),
        (10,0),
        (11,0),
        (12,0),
        (13,800),
        (14,0),
        (15,0),
        (16,0),
        (17,0),
        (18,0),
        (19,0),
        (20,0),
        (21,0),
        (22,0),
        (23,0),
        (24,0)

    ],fn=25)



def create_attribute_other():

    return encode_sproto([

        (0,3000),
        (1,0),
        (2,1),
        (3,1000),
        (4,0),
        (5,0),
        (6,0),
        (7,0),
        (8,""),
        (9,0),
        (10,0),
        (11,0),
        (12,0),
        (13,0),
        (14,0),
        (15,0),
        (16,0),
        (17,0),
        (18,"")

    ],fn=19)



def create_property():

    return encode_sproto([

        (13,0),
        (14,0),
        (15,0),
        (16,0),
        (17,0),
        (18,0)

    ],fn=19)



# ==========================================================
# VISUAL DATA
# ==========================================================

def create_visual(name,prof):


    visual = {

        0:{
            "mode":"100",
            "head":"XD_A_T",
            "body":"XD_A_S",
            "leg":"XD_A_X",
            "weapon":"XD_A_WQ"
        },


        1:{
            "mode":"104",
            "head":"QJ_A_T",
            "body":"QJ_A_S",
            "leg":"QJ_A_X",
            "weapon":"QJ_A_WQ"
        },


        2:{
            "mode":"105",
            "head":"NQS_A_T",
            "body":"NQS_A_S",
            "leg":"NQS_A_X",
            "weapon":"NQS_A_WQ"
        }

    }


    v = visual.get(prof,visual[0])


    return encode_sproto([

        (0,name),
        (1,v["mode"]),
        (2,v["head"]),
        (3,v["body"]),
        (4,v["leg"]),
        (5,v["weapon"]),
        (10,0)

    ],fn=17)




# ==========================================================
# GENERAL DATA
# ==========================================================

def create_general(name,prof):

    return encode_sproto([

        (0,name),
        (1,prof),
        (2,1),
        (3,"101"),
        (4,0)

    ],fn=5)




# ==========================================================
# MOVEMENT
# ==========================================================

def create_movement():


    pos = encode_sproto([

        (0,1500),
        (1,500),
        (2,2000),
        (3,0)

    ],fn=4)



    return encode_sproto([

        (0,pos),
        (1,pos)

    ],fn=2)




# ==========================================================
# RUNTIME AGENT
# ==========================================================

def create_runtime():

    attr = create_attribute()


    return encode_sproto([

        (6,attr),
        (7,attr)

    ],fn=8)




# ==========================================================
# SEND FUNCTIONS
# ==========================================================

def send_packet(conn,data):

    packed = sproto_pack(data)

    conn.sendall(
        struct.pack(">H",len(packed))
        +
        packed
    )




def send_response(conn,session,body):


    header = encode_sproto([

        (1,session)

    ],fn=2)



    send_packet(
        conn,
        header+body
    )




def send_push(conn,tag,data):

    global server_session_counter


    server_session_counter += 1



    header = encode_sproto([

        (0,tag),
        (1,server_session_counter)

    ],fn=2)



    print("[PUSH]",tag)



    send_packet(

        conn,

        header+data

    )



# ==========================================================
# CREATE FULL CHARACTER
# ==========================================================

def create_character_object(c):


    name = c["name"]

    prof = c.get("prof",0)



    general = create_general(
        name,
        prof
    )


    visual = create_visual(
        name,
        prof
    )


    attr_other = create_attribute_other()


    prop = create_property()


    movement = create_movement()


    runtime = create_runtime()



    character = encode_sproto([


        (0,c["id"]),


        (1,general),


        (2,attr_other),


        (5,prop),


        (6,visual),


        (7,movement),


        (13,runtime),


        (15,2)


    ],fn=17)



    return character, movement

# ==========================================================
# PART 3/3
# NETWORK HANDLER + MAP ENTRY FLOW
# ==========================================================


def client_handler(conn,addr):

    print("[CONNECT]",addr)

    account="0"


    try:

        while True:


            header = conn.recv(2)


            if not header:

                break



            size = struct.unpack(
                ">H",
                header
            )[0]



            data=b""


            while len(data)<size:


                part=conn.recv(
                    size-len(data)
                )


                if not part:

                    break


                data+=part



            raw=sproto_unpack(data)


            packet=decode_sproto(raw)



            msg=packet.get(0)

            session=packet.get(1,0)



            print(
                "[RX]",
                msg,
                "SESSION",
                session
            )



            try:

                body_offset = 2 + (
                    struct.unpack(
                        "<H",
                        raw[:2]
                    )[0]*2
                )


                body=decode_sproto(
                    raw,
                    body_offset
                )


            except:

                body={}



            # ==================================================
            # LOGIN 4
            # ==================================================

            if msg==4:


                if isinstance(body.get(1),bytes):

                    account=body[1].decode(
                        "utf-8",
                        "ignore"
                    )

                else:

                    account=str(
                        body.get(1,"0")
                    )



                print(
                    "[LOGIN]",
                    account
                )



                send_response(

                    conn,

                    session,

                    encode_sproto([

                        (0,2),
                        (1,"1.012.017"),
                        (2,"1000"),
                        (3,1)

                    ],fn=4)

                )



            # ==================================================
            # CHARACTER LIST 103
            # ==================================================

            elif msg==103:


                if account in characters:


                    c=characters[account]


                    char=encode_sproto([

                        (0,c["id"]),
                        (1,c["name"])

                    ],fn=2)



                    response=encode_sproto([

                        (0,[char])

                    ],fn=1)



                else:


                    response=encode_sproto([

                        (0,[])

                    ],fn=1)




                send_response(

                    conn,

                    session,

                    response

                )




            # ==================================================
            # CHARACTER CREATE 104
            # ==================================================

            elif msg==104:


                cid=random.randint(
                    1000000,
                    9999999
                )


                characters[account]={

                    "id":cid,
                    "name":"Hero",
                    "prof":0,
                    "map":"101"

                }



                save_chars(
                    characters
                )



                send_response(

                    conn,

                    session,

                    encode_sproto([

                        (0,cid),
                        (1,0)

                    ],fn=2)

                )




            # ==================================================
            # CHARACTER PICK 105
            # ==================================================

            elif msg==105:


                print("[CHARACTER PICK]")


                # success

                send_response(

                    conn,

                    session,

                    encode_sproto([

                        (0,1)

                    ],fn=1)

                )



                # sync data 614

                send_push(

                    conn,

                    614,

                    encode_sproto([

                        (0,int(time.time())),
                        (12,12345),
                        (13,1)

                    ],fn=14)

                )



                # enter map 503

                send_push(

                    conn,

                    503,

                    encode_sproto([

                        (0,"101"),
                        (1,1),
                        (2,1)

                    ],fn=3)

                )





            # ==================================================
            # MAP READY 100
            # ==================================================

            elif msg==100:


                print("[MAP READY]")


                c=characters.get(account)



                if not c:

                    print(
                        "[ERROR] NO CHARACTER"
                    )

                    continue



                character,movement = create_character_object(c)



                # ==============================================
                # MAIN PLAYER CREATE 504
                # ==============================================


                print(
                    "[SEND] MAIN PLAYER CREATE"
                )



                send_push(

                    conn,

                    504,

                    encode_sproto([

                        (0,character),
                        (1,movement)

                    ],fn=2)

                )



                time.sleep(0.5)



                # ==============================================
                # START ENTER GAME 654
                # ==============================================


                print(
                    "[SEND] START ENTER GAME"
                )


                send_push(

                    conn,

                    654,

                    encode_sproto([

                        (0,1)

                    ],fn=1)

                )




            # ==================================================
            # HEARTBEAT 218
            # ==================================================

            elif msg==218:


                send_response(

                    conn,

                    session,

                    encode_sproto([

                        (0,body.get(0,0)),
                        (1,int(time.time()))

                    ],fn=2)

                )



            # ==================================================
            # INVENTORY 141
            # ==================================================

            elif msg==141:


                send_response(

                    conn,

                    session,

                    encode_sproto([

                        (0,[])

                    ],fn=1)

                )




            # ==================================================
            # RANDOM NAME 118
            # ==================================================

            elif msg==118:


                name="Hero_"+str(
                    random.randint(100,999)
                )



                send_response(

                    conn,

                    session,

                    encode_sproto([

                        (0,name)

                    ],fn=1)

                )




            # ==================================================
            # EXTRA MAP REQUESTS
            # ==================================================

            elif msg in [121,139,145,540]:


                send_response(

                    conn,

                    session,

                    encode_sproto([],fn=0)

                )




    except Exception:

        traceback.print_exc()



    finally:

        conn.close()

        print(
            "[DISCONNECT]",
            addr
        )





# ==========================================================
# SERVER START
# ==========================================================


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



print(
    "AUTO THEFT GANGSTERS GAME SERVER 9555 READY"
)



while True:


    client,addr=server.accept()


    threading.Thread(

        target=client_handler,

        args=(client,addr),

        daemon=True

    ).start()
