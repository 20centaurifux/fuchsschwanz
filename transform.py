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
import config, tld
from utils import decode_ascii
from logger import log

def transform(type_id, payload):
    # tranform private message to server to command:
    if type_id == "h":
        fields = [decode_ascii(f).strip() for f in tld.split(payload)]

        if len(fields) >= 2 and fields[0] == "m":
            args = [arg.rstrip(" \0") for arg in fields[1].split(" ", 2)]

            if args[0] == config.NICKSERV:
                type_id = "h"

                payload = bytearray()

                payload.extend(args[1].encode())
                payload.append(1)

                if len(args) == 3:
                    payload.extend(args[2].encode())

                payload.append(0)

                log.debug("Message transformed: type='%s', command='%s'" % (type_id, args[1]))

    return type_id, payload
