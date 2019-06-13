import socket
import sys
import secrets
import random
import string
import threading
import time
import ltd
from timer import Timer

SERVER_ADDRESS = ('127.0.0.1', 7326)

class ClientThread(threading.Thread):
    def __init__(self, group, min, max):
        super().__init__()

        self.__group = group
        self.__min = min
        self.__max = max

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            sock.connect(SERVER_ADDRESS)

            sock.settimeout(1)

            nick = secrets.token_hex(6)
            loginid = "".join([secrets.choice(string.ascii_letters) for _ in range(12)])

            e = ltd.Encoder("a")

            e.add_field_str(loginid, append_null=False)
            e.add_field_str(nick, append_null=False)
            e.add_field_str(self.__group, append_null=False)
            e.add_field_str("login", append_null=False)
            e.add_field_str("", append_null=True)

            sock.sendall(e.encode())

            t = Timer()

            data = sock.recv(255)

            timeout = random.randint(self.__min, self.__max)

            while True:
                try:
                    sock.recv(255)

                except socket.timeout: pass

                if t.elapsed() > timeout:
                    t = Timer()

                    pkg = ltd.encode_str("b", secrets.token_hex(random.randint(2, 32)))

                    sock.sendall(pkg)

                timeout = random.randint(self.__min, self.__max)
        except Exception as e:
            print(e)

try:
    for i in range(2000):
        print("Starting thread %d" % (i + 1))

        c = ClientThread("d", 90, 300)
        c.start()

        time.sleep(0.1)

    while True:
        print("Threads: %d" % threading.active_count())
        time.sleep(5)

except Exception as e:
    print(e)
