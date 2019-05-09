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
import sys
import commands, di, broker, validate
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

def fieldslength(count=0, min=0, max=0):
    def decorator(fn):
        def wrapper(self, session_id, fields):
            if count > 0 and len(fields) != count:
                    raise TldErrorException("Malformed message, wrong number of fields.")
            else:
                if len(fields) < min:
                    raise TldErrorException("Malformed message, missing fields.")

                if max > min and len(fields) > max:
                    raise TldErrorException("Malformed message, too many fields.")

            fn(self, session_id, fields)
            
        return wrapper

    return decorator

def arglength(at=0, min=0, max=0, display="Argument"):
    def decorator(fn):
        def wrapper(self, session_id, fields):
            val = fields[at]

            if len(val) < min:
                if min == 1:
                    raise TldErrorException("%s cannot be empty." % display)
                else:
                    raise TldErrorException("%s requires at least %d characters." % (display, min))

            if max > min and len(val) > max:
                raise TldErrorException("%s exceeds allowed maximum length (%d characters)." % (display, max))

            fn(self, session_id, fields)
            
        return wrapper

    return decorator

def command(command):
    def decorator(cls):
        cls.command = command

        return cls

    return decorator

def Cache():
    m = {}

    return lambda T: m.get(T, T())

INSTANCE = Cache()

@code("a")
class Login:
    @textfields
    @fieldslength(min=5, max=7)
    def process(self, session_id, fields):
        fn = None
        args = []

        if fields[3] == "login":
            fn = INSTANCE(commands.UserSession).login
            args = [session_id, fields[0], fields[1], fields[4] if len(fields) >= 5 else "", fields[2]]

        if not fn:
            raise TldErrorException("Unsupported login type: \"%s\"" % fields[3])

        fn(*args)

@code("b")
class OpenMessage:
    @textfields
    @catchtldexceptions
    @fieldslength(count=1)
    def process(self, session_id, fields):
        INSTANCE(commands.OpenMessage).send(session_id, fields[0])

@command("g")
class ChangeGroup:
    @fieldslength(count=1)
    @arglength(display="Group name", min=validate.GROUP_MIN, max=validate.GROUP_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.UserSession).join(session_id, fields[0])

@command("name")
class Rename:
    @fieldslength(count=1)
    @arglength(display="Nick Name", min=validate.NICK_MIN, max=validate.NICK_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.UserSession).rename(session_id, fields[0])

@command("p")
class Register:
    @fieldslength(count=1)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).register(session_id, fields[0])

@command("cp")
class ChangePassword:
    @fieldslength(count=1)
    def process(self, session_id, fields):
        msg_fields = fields[0].split(" ")

        if len(msg_fields) == 2:
            old_pwd, new_pwd = msg_fields

            INSTANCE(commands.Registration).change_password(session_id, old_pwd, new_pwd)
        else:
            raise TldErrorException("Usage: /cp old_password new_password")

def msgid(fields):
    return fields[1] if len(fields) == 2 else ""

@command("secure")
class EnableSecurity:
    @fieldslength(min=1, max=2)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).set_security_mode(session_id, enabled=True, msgid=msgid(fields))

@command("nosecure")
class DisableSecurity:
    @fieldslength(min=1, max=2)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).set_security_mode(session_id, enabled=False, msgid=msgid(fields))

@command("rname")
class ChangeRealname:
    @fieldslength(min=1, max=2)
    @arglength(display="Real Name", min=validate.REALNAME_MIN, max=validate.REALNAME_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).change_field(session_id, "real_name", fields[0], msgid=msgid(fields))

@command("addr")
class ChangeAddress:
    @fieldslength(min=1, max=2)
    @arglength(display="Address", min=validate.ADDRESS_MIN, max=validate.ADDRESS_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).change_field(session_id, "address", fields[0], msgid=msgid(fields))

@command("phone")
class ChangePhone:
    @fieldslength(min=1, max=2)
    @arglength(display="Phone Number", min=validate.PHONE_MIN, max=validate.PHONE_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).change_field(session_id, "phone", fields[0], msgid=msgid(fields))

@command("email")
class ChangeEmail:
    @fieldslength(min=1, max=2)
    @arglength(display="E-Mail address", min=validate.EMAIL_MIN, max=validate.EMAIL_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).change_field(session_id, "email", fields[0], msgid=msgid(fields))

@command("text")
class ChangeText:
    @fieldslength(min=1, max=2)
    @arglength(display="Text", min=validate.TEXT_MIN, max=validate.TEXT_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).change_field(session_id, "text", fields[0], msgid=msgid(fields))

@command("www")
class ChangeWebsite:
    @fieldslength(min=1, max=2)
    @arglength(display="WWW", min=validate.WWW_MIN, max=validate.WWW_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).change_field(session_id, "www", fields[0], msgid=msgid(fields))

@command("delete")
class DeleteNick:
    @fieldslength(min=1, max=2)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).delete(session_id, fields[0], msgid=msgid(fields))

@command("whois")
class Whois:
    @fieldslength(min=1, max=2)
    @arglength(display="Nick Name", min=validate.NICK_MIN, max=validate.NICK_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.Registration).whois(session_id, fields[0], msgid=msgid(fields))

@command("write")
class WriteMessage:
    @fieldslength(min=1, max=2)
    def process(self, session_id, fields):
        msg_fields = fields[0].split(" ", 1)

        if len(msg_fields) == 2:
            receiver, message = [f.strip() for f in msg_fields]
        else:
            raise TldErrorException("Usage: /write nick message text")

        INSTANCE(commands.MessageBox).send_message(session_id, receiver, message)

@command("read")
class ReadMessages:
    @fieldslength(min=1, max=2)
    def process(self, session_id, fields):
        if fields[0]:
            raise TldErrorException("Usage: /read")

        INSTANCE(commands.MessageBox).read_messages(session_id, msgid=msgid(fields))

@command("whereis")
class Whereis:
    @fieldslength(min=1, max=2)
    def process(self, session_id, fields):
        if not fields[0]:
            raise TldErrorException("Usage: /whereis nick")

        INSTANCE(commands.UserSession).whereis(session_id, fields[0], msgid(fields))

@command("topic")
class ChangeTopic:
    @fieldslength(count=1)
    @arglength(display="Topic", min=validate.TOPIC_MIN, max=validate.TOPIC_MAX)
    def process(self, session_id, fields):
        INSTANCE(commands.Group).set_topic(session_id, fields[0])

COMMANDS = {cls.command: cls() for cls in filter(lambda cls: isinstance(cls, type) and "command" in cls.__dict__,
                                                 sys.modules[__name__].__dict__.values())}

@code("h")
class Command:
    @textfields
    @catchtldexceptions
    @fieldslength(min=1, max=3)
    def process(self, session_id, fields):
        cmd = COMMANDS.get(fields[0])

        if not cmd:
            raise TldErrorException("Unsupported command: %s" % fields[0])

        cmd.process(session_id, fields[1:])

@code("l")
class Ping:
    @textfields
    @catchtldexceptions
    @fieldslength(min=0, max=1)
    def process(self, session_id, fields):
        INSTANCE(commands.Ping).ping(session_id, fields[0] if len(fields) == 1 else "")

