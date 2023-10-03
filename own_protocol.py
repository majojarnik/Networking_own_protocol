import socket
import struct
from io import StringIO
from random import choice
from string import ascii_letters
import time
import os
import math
import sys
import msvcrt

SUBOR = 1
SPRAVA = 2
HLAVICKA = 13

ZACNI_POSIELAT = b'0'
ZACIATOK_SPOJENIA = b'1'
KONIEC_SPOJENIA = b'2'
DOBRY_FRAGMENT = b'3'
CHYBNY_FRAGMENT = b'4'
PRIDE_SPRAVA = b'5'
PRIDE_SUBOR = b'6'
POSLEDNY_FRAGMENT = b'7'
NEPOSLEDNY_FRAGMENT = b'8'
KEEP_ALIVE = b'9'

#funkciu crc16 som skopiroval zo stackoverflow
def crc16(data):
    checksum = 0
    data_len = len(data)
    if data_len % 2:
        data_len += 1
        data += struct.pack('!B', 0)

    for i in range(0, data_len, 2):
        w = (data[i] << 8) + (data[i + 1])
        checksum += w

    checksum = (checksum >> 16) + (checksum & 0xFFFF)
    checksum = ~checksum & 0xFFFF
    return checksum


def posli(pos_objekt, object, adr_prij, vel_frag, chyb_frag):
    if pos_objekt == SUBOR:
        pocet_frag = int(math.ceil(os.path.getsize(object) / (vel_frag - HLAVICKA)))
        start_frag = struct.pack('iic', vel_frag, pocet_frag + 1, PRIDE_SUBOR)
        start_frag = start_frag + object.encode()
    else:
        pocet_frag = int(math.ceil(len(object) / (vel_frag - HLAVICKA)))
        start_frag = struct.pack('iic', vel_frag, pocet_frag + 1, PRIDE_SPRAVA)

    print("Pocet fragmentov: ", pocet_frag, " + ukoncovaci")

    data = None
    while data != ZACNI_POSIELAT:
        sock.sendto(start_frag, adr_prij)
        data, addr = sock.recvfrom(10)

    print("Zacinam posielat")

    f = None
    if pos_objekt == SUBOR:
        f = open(object, 'rb')
    elif pos_objekt == SPRAVA:
        f = StringIO(object)

    list_frag = []
    data = f.read(vel_frag - HLAVICKA)
    por_cislo = 1
    koniec = False
    dlzka = vel_frag - HLAVICKA
    pos_koniec = False

    while True:
        if data and len(list_frag) < 10:
            if pos_objekt == SPRAVA:
                data_frag = data.encode()
            else:
                data_frag = data
            crc = crc16(data_frag)

            hlavicka = struct.pack('iiic', dlzka, por_cislo, crc, NEPOSLEDNY_FRAGMENT)
            frag = hlavicka + data_frag
            list_frag.append(frag)

            if chyb_frag and por_cislo == int(math.floor(pocet_frag / 2)):
                print("Chyba vo fragmente ", por_cislo)
                frag = hlavicka + ("".join(choice(ascii_letters) for i in range(vel_frag - HLAVICKA))).encode()

            por_cislo += 1
            sock.sendto(frag, adr_prij)
            print("Poslal som ", por_cislo - 1, ". fragment")
            data = f.read(vel_frag - HLAVICKA)

        elif not pos_koniec and not data and len(list_frag) < 10:
            hlavicka = struct.pack('iiic', 0, por_cislo, 0, POSLEDNY_FRAGMENT)
            frag = hlavicka + "*".encode()
            list_frag.append(frag)
            sock.sendto(frag, adr_prij)
            print("Poslal som ", por_cislo, ". fragment, ukoncovaci")
            pos_koniec = True

        else:
            i = 0
            while len(list_frag) > 0:
                try:
                    prij_data, lentak = sock.recvfrom(6)
                    kont_cislo, kont_status, koniec = struct.unpack('ic?', prij_data)
                    if koniec:
                        print("Dokoncenie posielania")
                        break
                    for frag in list_frag:
                        hlavicka = frag[:HLAVICKA]
                        k_dlzka, k_por_cislo, k_crc, k_typ = struct.unpack('iiic', hlavicka)
                        if kont_cislo == k_por_cislo:
                            if kont_status == DOBRY_FRAGMENT:
                                list_frag.remove(frag)
                                if len(list_frag) == 0 and k_typ == POSLEDNY_FRAGMENT:
                                    print("Dokoncenie posielania")
                                    break
                            else:
                                print("Znovuodosielam chybny fragment ", k_por_cislo)
                                sock.sendto(frag, adr_prij)
                except:
                    i += 1
                    time.sleep(1)
                    if i == 100:
                        hlavicka = struct.pack('iiic', 0, 10, 0, NEPOSLEDNY_FRAGMENT)
                        frag = hlavicka + "*".encode()
                        sock.sendto(frag, adr_prij)
                    break

        if koniec:
            break


def prijmi():
    while True:
        data, addr = sock.recvfrom(1450)
        hlavicka = data[:9]
        nazov = data[9:].decode()
        vel_frag, pocet_frag, prij_objekt = struct.unpack('iic', hlavicka)

        if prij_objekt == PRIDE_SUBOR:
            cesta = input("Napis cestu kde chces ulozit subor aj s backslashom na konci: ")
            sock.sendto(struct.pack('c', ZACNI_POSIELAT), addr)
            break
        if prij_objekt == PRIDE_SPRAVA:
            sock.sendto(struct.pack('c', ZACNI_POSIELAT), addr)
            break
        if prij_objekt == KEEP_ALIVE:
            print("Prijaty keep alive")


    if prij_objekt == PRIDE_SUBOR:
        f = open(cesta + os.path.basename(nazov), 'wb')
    else:
        f = StringIO()

    list_frag = []
    koniec = False
    while True:
        frag, addr = sock.recvfrom(vel_frag)
        list_frag.append(frag)
        hlavicka = frag[:HLAVICKA]
        dlzka, por_cislo, crc, typ = struct.unpack('iiic', hlavicka)
        pocet_frag -= 1

        if por_cislo % 10 == 0 or pocet_frag == 0 or typ == POSLEDNY_FRAGMENT:
            i = 1
            j = 0
            while i <= 10:
                frag = list_frag[j]
                hlavicka = frag[:HLAVICKA]
                data = frag[HLAVICKA:]
                dlzka, por_cislo, crc, typ = struct.unpack('iiic', hlavicka)

                if (crc == 0 or crc == crc16(data)) and por_cislo % 10 == i % 10:
                    print("Prijaty fragment: ", por_cislo)
                    if typ == POSLEDNY_FRAGMENT:
                        sock.sendto(struct.pack('ic?', por_cislo, DOBRY_FRAGMENT, True), addr)
                        print("Prijal som posledny fragment")
                        koniec = True
                        break
                    if prij_objekt == PRIDE_SUBOR:
                        f.write(data)
                    else:
                        f.write(data.decode())
                    i += 1
                    j += 1
                    sock.sendto(struct.pack('ic?', por_cislo, DOBRY_FRAGMENT, False), addr)

                else:
                    if por_cislo % 10 == i % 10:
                        print("Chybny fragment: ", (por_cislo - 1) // 10 * 10 + i)
                    else:
                        print("Chybajuci fragment: ", (por_cislo - 1) // 10 * 10 + i)
                        j -= 1
                    sock.sendto(struct.pack('ic?', (por_cislo - 1) // 10 * 10 + i, CHYBNY_FRAGMENT, False), addr)
                    while True:
                        opr_frag, addr = sock.recvfrom(vel_frag)
                        hlavicka = opr_frag[:HLAVICKA]
                        data = opr_frag[HLAVICKA:]
                        dlzka, por_cislo, crc, typ = struct.unpack('iiic', hlavicka)
                        if crc == crc16(data) and por_cislo % 10 == i % 10:
                            print("Prijaty fragment: ", por_cislo)
                            if typ == POSLEDNY_FRAGMENT:
                                sock.sendto(struct.pack('ic?', por_cislo, DOBRY_FRAGMENT, True), addr)
                                print("Prijal som posledny fragment")
                                koniec = True
                                break
                            if prij_objekt == PRIDE_SUBOR:
                                f.write(data)
                            else:
                                f.write(data.decode())
                            i += 1
                            j += 1
                            sock.sendto(struct.pack('ic?', por_cislo, DOBRY_FRAGMENT, False), addr)
                            break
                        else:
                            sock.sendto(struct.pack('ic?', i, CHYBNY_FRAGMENT, False), addr)
                if koniec:
                    break
            list_frag.clear()
        if koniec:
            break

    if prij_objekt == PRIDE_SUBOR:
        print("Prijaty subor ulozeny ", cesta + os.path.basename(nazov))
    else:
        print("Prijata sprava: ", f.getvalue())
    f.close()

"""
# Funkciu readInput som skopiroval zo stackoverflow
def readInput( caption, default, timeout):
    start_time = time.time()
    sys.stdout.write('%s'%(caption))
    sys.stdout.flush()
    input = ''
    while True:
        if msvcrt.kbhit():
            byte_arr = msvcrt.getche()
            if ord(byte_arr) == 13: # enter_key
                break
            elif ord(byte_arr) >= 32: #space_char
                input += "".join(map(chr,byte_arr))
        if len(input) == 0 and (time.time() - start_time) > timeout:
            print("timing out, using default value.")
            break
    print('')  # needed to move to next line
    if len(input) > 0:
        return input
    else:
        return default
"""

# bez keep alive
def vyberanie(adr_prij):
    while True:
        print("1: Odosielatel")
        print("2: Prijimatel")
        print("3: Ukonci program")
        vyber = int(input())
        if vyber == 1:
            vel_frag = int(input("Velkost fragmentov (14 - 1459): "))
            chyb_frag = int(input("Chybne fragmenty (0,1): "))

            print("Co si prajete odoslat?")
            print("1: Subor")
            print("2: Sprava")

            pos_objekt = int(input())
            if pos_objekt == SUBOR:
                cesta = input("Cesta k suboru: ")
                posli(SUBOR, cesta, adr_prij, vel_frag, chyb_frag)
            elif pos_objekt == SPRAVA:
                sprava = input("Sprava: ")
                posli(SPRAVA, sprava, adr_prij, vel_frag, chyb_frag)
        elif vyber == 2:
            prijmi()
        elif vyber == 3:
            print("Ukoncujem program")
            break



"""


#s keep alive
def vyberanie(adr_prij, objekt):
    while True:

        start_time = time.time()
        print("1: Odosielatel")
        print("2: Prijimatel")
        print("3: Ukonci program")

        vyber = 0
        while vyber != 1 and vyber != 2 and vyber != 3:
            vyber = int(readInput("", "2500", 40))

            if vyber == 2500 and objekt == "server":
                start_frag = struct.pack('iic', 0, 0, KEEP_ALIVE)
                sock.sendto(start_frag, adr_prij)
                start_time = time.time()
                print("Odoslany keep alive")
            elif vyber == 2500 and objekt == "client":
                zb_data, zb_adres = sock.recvfrom(40)
                start_time = time.time()
                print("Prijaty keep alive")


        if vyber == 1:
            vel_frag = 0
            while vel_frag <= 14 or vel_frag >= 1459:
                vel_frag = int(readInput("Velkost fragmentov (14 - 1459): ", "2500", 40 - (time.time() - start_time)))

                if vel_frag == 2500:
                    start_frag = struct.pack('iic', 0, 0, KEEP_ALIVE)
                    sock.sendto(start_frag, adr_prij)
                    start_time = time.time()
                    print("Odoslany keep alive")

            #vel_frag = int(input("Velkost fragmentov (14 - 1459): "))
            #chyb_frag = int(input("Chybne fragmenty (0,1): "))
            chyb_frag = 5
            while chyb_frag != 1 and chyb_frag != 0:
                chyb_frag = int(readInput("Chybne fragmenty (0,1): ", "2500", 40 - (time.time() - start_time)))

                if chyb_frag == 2500:
                    start_frag = struct.pack('iic', 0, 0, KEEP_ALIVE)
                    sock.sendto(start_frag, adr_prij)
                    start_time = time.time()
                    print("Odoslany keep alive")

            print("Co si prajete odoslat?")
            print("1: Subor")
            print("2: Sprava")

            pos_objekt = 5
            while pos_objekt != 1 and pos_objekt != 2:
                pos_objekt = int(readInput("", "2500", 40 - (time.time() - start_time)))

                if pos_objekt == 2500:
                    start_frag = struct.pack('iic', 0, 0, KEEP_ALIVE)
                    sock.sendto(start_frag, adr_prij)
                    start_time = time.time()
                    print("Odoslany keep alive")

            #pos_objekt = int(input())

            if pos_objekt == SUBOR:
                #cesta = input("Cesta k suboru: ")
                cesta = "2500"
                while cesta == "2500":
                    cesta = readInput("Cesta: ", "2500", 40 - (time.time() - start_time))

                    if cesta == "2500":
                        start_frag = struct.pack('iic', 0, 0, KEEP_ALIVE)
                        sock.sendto(start_frag, adr_prij)
                        start_time = time.time()
                        print("Odoslany keep alive")


                posli(SUBOR, cesta, adr_prij, vel_frag, chyb_frag)
            elif pos_objekt == SPRAVA:
                sprava = ""
                while sprava == "":
                    sprava = readInput("Sprava: ", "", 40 - (time.time() - start_time))

                    if sprava == "":
                        start_frag = struct.pack('iic', 0, 0, KEEP_ALIVE)
                        sock.sendto(start_frag, adr_prij)
                        start_time = time.time()
                        print("Odoslany keep alive")

                #sprava = input("Sprava: ")
                posli(SPRAVA, sprava, adr_prij, vel_frag, chyb_frag)
        elif vyber == 2:
            prijmi()
        elif vyber == 3:
            print("Ukoncujem program")
            break
"""


def server():
    serv_port = int(input("Vas port: "))
    serv_adr = input("Vasa adresa: ")
    sock.bind((serv_adr, serv_port))
    while True:
        data, addr = sock.recvfrom(40)
        if data == ZACIATOK_SPOJENIA:
            sock.sendto(data, addr)
            print("Adresa klienta: ", addr)
            print("Zaciatok spojenia")
            break
    adr_prij = addr
    vyberanie(adr_prij)


def client():
    server_port = int(input("Port servera: "))
    server_adr = input("Adresa servera: ")
    adresa = (server_adr, server_port)
    print(adresa)
    zac_spoj = struct.pack('c', ZACIATOK_SPOJENIA)
    data = None
    while data != ZACIATOK_SPOJENIA:
        sock.sendto(zac_spoj, adresa)
        try:
            data, addr = sock.recvfrom(40)
        except:
            print("Cakam na spojenie")
            time.sleep(1)

    print("Zaciatok spojenia")
    adr_prij = adresa
    vyberanie(adr_prij)


print("1: Server")
print("2: Client")
vyb = int(input())
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

if vyb == 1:
    server()
else:
    client()
