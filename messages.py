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
import commands, di, broker
from exception import TldStatusException, TldErrorException, TldResponseException

def code(code):
    def decorator(cls):
        cls.code = code

        return cls

    return decorator

def textfields(fn):
    def wrapper(self, session_id, fields):
        fn(self, session_id, [b.decode("ascii").strip(" \0") for b in fields])

    return wrapper

def catchtldexceptions(fn):
    def wrapper(self, session_id, fields):
        try:
            fn(self, session_id, fields)

        except TldResponseException as ex:
            b = di.default_container.resolve(broker.Broker)

            b.deliver(session_id, ex.response)

    return wrapper

def fields(count=0, min=0, max=0):
    def decorator(fn):
        def wrapper(self, session_id, fields):
            if count > 0:
                pass
            else:
                if len(fields) < min:
                    raise TldErrorException("Malformed message, missing fields.")

                if max > min and len(fields) > max:
                    raise TldErrorException("Malformed message, too many fields.")

            fn(self, session_id, fields)
            
        return wrapper

    return decorator

def Cache():
    m = {}

    return lambda T: m.get(T, T())

INSTANCE = Cache()

@code("a")
class Login:
    @textfields
    @fields(min=5, max=7)
    def process(self, session_id, fields):
        fn = None
        args = []

        if fields[3] == "login":
            fn = INSTANCE(commands.User).login
            args = [session_id, fields[0], fields[1], fields[4] if len(fields) >= 5 else "", fields[2]]

        if fn is None:
            raise TldErrorException("Unknown login type: \"%s\"" % fields[3])

        fn(*args)

@code("b")
class OpenMessage:
    @textfields
    @catchtldexceptions
    @fields(count=1)
    def process(self, session_id, fields):
        INSTANCE(commands.OpenMessage).send(session_id, fields[0])

@code("h")
class Command:
    @textfields
    @catchtldexceptions
    @fields(min=1, max=3)
    def process(self, session_id, fields):
        arg = fields[1] if len(fields) >= 2 else ""
        print(fields[0])
        if fields[0] == "g":
            INSTANCE(commands.User).join(session_id, arg)
        elif fields[0] == "name":
            INSTANCE(commands.User).rename(session_id, arg)
        elif fields[0] == "topic":
            INSTANCE(commands.Group).set_topic(session_id, arg)
        else:
            raise TldErrorException("Unknown command: %s" % fields[0])

@code("l")
class Ping:
    @textfields
    @catchtldexceptions
    @fields(min=0, max=1)
    def process(self, session_id, fields):
        INSTANCE(commands.Ping).ping(session_id, fields[0] if len(fields) == 1 else "")
