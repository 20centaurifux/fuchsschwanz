"""
    project............: Fuchsschwanz
    description........: icbd server implementation
    date...............: 05/2019
    copyright..........: Sebastian Fedrau

    Permission is hereby granted, free of charge, to any person obtaining
    a copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to
    the following conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
    OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
    OTHER DEALINGS IN THE SOFTWARE.
"""
class Encoder:
    def __init__(self, T):
        self.__T = T
        self.__d = bytearray()

    def add_field(self, data):
        if self.__d:
            self.__d.append(1)

        self.__d.extend(data)

    def add_field_str(self, text, append_null=False):
        self.add_field(text.encode("ascii", "ignore"))

        if append_null:
            self.__d.append(0)

    def encode(self):
        pkg = bytearray()

        if len(self.__d) >= 255:
            raise OverflowError

        pkg.append(len(self.__d) + 1)
        pkg.append(ord(self.__T))
        pkg.extend(self.__d)

        return pkg

def encode_str(T, text):
    e = Encoder(T)

    e.add_field_str(text, append_null=True)

    return e.encode()

def encode_status_msg(category, message):
    e = Encoder("d")

    e.add_field_str(category, append_null=False)
    e.add_field_str(message, append_null=True)

    return e.encode()

def encode_empty_cmd(T):
    return encode_str(T, "")

def encode_co_output(text, msgid=""):
    e = Encoder("i")

    e.add_field_str("co", append_null=False)

    if msgid:
        e.add_field_str(text, append_null=False)
        e.add_field_str(msgid, append_null=True)
    else:
        e.add_field_str(text, append_null=True)

    return e.encode()

class Decoder:
    def __init__(self):
        self.__buffer = bytearray()
        self.__listeners = []

    def add_listener(self, listener):
        self.__listeners.append(listener)

    def remove_listener(self, listener):
        self.__listeners.remove(listener)

    def write(self, data):
        self.__buffer.extend(data)
        self.__process__()

    def __process__(self):
        length = len(self.__buffer)

        if length >= 2 and length - 1 >= self.__buffer[0]:
            p_length = self.__buffer[0]

            for f in self.__listeners:
                f(chr(self.__buffer[1]), self.__buffer[2:p_length + 1])

            self.__buffer = self.__buffer[p_length + 1:]
            self.__process__()

def split(payload):
    fields = []
    field = []

    for b in payload:
        if b == 1:
            fields.append(bytearray(field))
            field = []
        else:
            field.append(b)

    fields.append(bytearray(field))

    return fields

def get_opts(line, **opts):
    m = {}
    tail = None

    line = line.strip(" \0")

    i = 0
    read_opts = False

    while i < len(line) and not tail:
        c = line[i]

        if read_opts:
            if line[i] == " ":
                read_opts = False
            else:
                opt = next((kv[0] for kv in opts.items() if c in kv[1]), None)

                if not opt:
                    raise Exception("Unknown flag: %s" % c)

                if opt in m:
                    raise Exception("Option '%s' already set." % opt)

                m[opt] = c

        elif c == "-":
            read_opts = True
        else:
            tail = line[i:]

        i += 1

    return m, tail
