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

def textfields(cls):
    fn = cls.process

    cls.process = lambda self, session_id, fields: fn(self,
                                                      session_id,
                                                      [b.decode("ascii").strip(" \0") for b in fields])

    return cls

def catchtldexceptions(fn):
    def wrapper(*args):
        try:
            fn(*args)

        except TldResponseException as ex:
            b = di.default_container.resolve(broker.Broker)

            b.deliver(args[1], ex.response)

    return wrapper

@code("a")
@textfields
class Login:
    def process(self, session_id, fields):
        if len(fields) <= 4:
            raise TldErrorException("Malformed login message.")

        fn = None
        args = []

        if fields[3] == "login":
            fn = commands.User().login
            args = [session_id, fields[0], fields[1], fields[4] if len(fields) >= 5 else "", fields[2]]

        if fn is None:
            raise TldErrorException("Unknown login type: \"%s\"" % fields[3])

        fn(*args)

@code("b")
@textfields
class OpenMessage:
    @catchtldexceptions
    def process(self, session_id, fields):
        if len(fields) != 1:
            raise TldErrorException("Malformed open message.")

        commands.OpenMessage().send(session_id, fields[0])

@code("h")
@textfields
class Command:
    def __init__(self):
        super().__init__()

    @catchtldexceptions
    def process(self, session_id, fields):
        if len(fields) < 1:
            raise TldErrorException("Malformed command message.")

        arg = fields[1] if len(fields) >= 2 else ""

        if fields[0] == "g":
            commands.User().join(session_id, arg)
        if fields[0] == "name":
            commands.User().rename(session_id, arg)
        if fields[0] == "topic":
            commands.Group().set_topic(session_id, arg)
        else:
            raise TldErrorException("Unknown command: %s" % fields[0])

@code("l")
@textfields
class Ping:
    @catchtldexceptions
    def process(self, session_id, fields):
        if len(fields) > 1:
            raise TldErrorException("Malformed ping message.")

        commands.Ping().ping(session_id, fields[0] if len(fields) == 1 else "")
