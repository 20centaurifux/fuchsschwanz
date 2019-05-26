"""
    project............: Fuchsschwanz
    description........: ICB server
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
import di
import session
import broker
import validate
import tld
from actions import ACTION
import actions.away
import actions.beep
import actions.group
import actions.messagebox
import actions.motd
import actions.openmessage
import actions.ping
import actions.privatemessage
import actions.registration
import actions.usersession
import actions.list
import actions.admin
import actions.help
from textutils import decode_ascii
from exception import TldErrorException, TldResponseException

def code(id):
    def decorator(cls):
        cls.code = id

        return cls

    return decorator

def textfields(fn):
    def wrapper(session_id, fields):
        fn(session_id, [decode_ascii(b).strip(" \0") for b in fields])

    return wrapper

def loginrequired(fn):
    def wrapper(session_id, fields):
        sessions = di.default_container.resolve(session.Store)

        state = sessions.get(session_id)

        if not state.nick or not state.group:
            raise TldErrorException("Login required.")

        fn(session_id, fields)

    return wrapper

def catchtldexceptions(fn):
    def wrapper(session_id, fields):
        try:
            fn(session_id, fields)

        except TldResponseException as ex:
            b = di.default_container.resolve(broker.Broker)

            b.deliver(session_id, ex.response)

    return wrapper

def fieldslength(count=0, min=0, max=0):
    def decorator(fn):
        def wrapper(session_id, fields):
            if count > 0 and len(fields) != count:
                raise TldErrorException("Malformed message, wrong number of fields.")

            if len(fields) < min:
                raise TldErrorException("Malformed message, missing fields.")

            if max > min and len(fields) > max:
                raise TldErrorException("Malformed message, too many fields.")

            fn(session_id, fields)

        return wrapper

    return decorator

def arglength(at=0, min=0, max=0, display="Argument"):
    def decorator(fn):
        def wrapper(session_id, fields):
            val = fields[at]

            if len(val) < min:
                if min == 1:
                    raise TldErrorException("%s cannot be empty." % display)

                raise TldErrorException("%s requires at least %d characters." % (display, min))

            if max > min and len(val) > max:
                raise TldErrorException("%s exceeds allowed maximum length (%d characters)." % (display, max))

            fn(session_id, fields)

        return wrapper

    return decorator

def command(name):
    def decorator(cls):
        cls.command = name

        return cls

    return decorator

@code("a")
class Login:
    @staticmethod
    @textfields
    @fieldslength(min=5, max=7)
    def process(session_id, fields):
        fn = None
        args = []

        if fields[3] == "login":
            fn = ACTION(actions.usersession.UserSession).login
            password = fields[4] if len(fields) >= 5 else ""
            status = fields[5] if len(fields) >= 6 else ""
            args = [session_id, fields[0], fields[1], password, fields[2], status]
        elif fields[3] == "w":
            fn = ACTION(actions.list.List).list_and_quit
            args = [session_id]

        if not fn:
            raise TldErrorException("Unsupported login type: '%s'" % fields[3])

        fn(*args)

@code("b")
class OpenMessage:
    @staticmethod
    @loginrequired
    @textfields
    @catchtldexceptions
    @fieldslength(count=1)
    def process(session_id, fields):
        ACTION(actions.openmessage.OpenMessage).send(session_id, fields[0])

@command("g")
class ChangeGroup:
    @staticmethod
    @loginrequired
    @fieldslength(count=1)
    @arglength(display="Group name", min=validate.GROUP_MIN, max=validate.GROUP_MAX)
    def process(session_id, fields):
        ACTION(actions.usersession.UserSession).join(session_id, fields[0])

@command("name")
class Rename:
    @staticmethod
    @loginrequired
    @fieldslength(count=1)
    @arglength(display="Nick Name", min=validate.NICK_MIN, max=validate.NICK_MAX)
    def process(session_id, fields):
        ACTION(actions.usersession.UserSession).rename(session_id, fields[0])

@command("p")
class Register:
    @staticmethod
    @loginrequired
    @fieldslength(count=1)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).register(session_id, fields[0])

@command("cp")
class ChangePassword:
    @staticmethod
    @loginrequired
    @fieldslength(count=1)
    def process(session_id, fields):
        msg_fields = fields[0].split(" ")

        if len(msg_fields) == 2:
            old_pwd, new_pwd = msg_fields

            ACTION(actions.registration.Registration).change_password(session_id, old_pwd, new_pwd)
        else:
            raise TldErrorException("Usage: /cp old_password new_password")

def msgid(fields):
    return fields[1] if len(fields) == 2 else ""

@command("secure")
class EnableSecurity:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).set_security_mode(session_id, enabled=True, msgid=msgid(fields))

@command("nosecure")
class DisableSecurity:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).set_security_mode(session_id, enabled=False, msgid=msgid(fields))

@command("rname")
class ChangeRealname:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    @arglength(display="Real Name", min=validate.REALNAME_MIN, max=validate.REALNAME_MAX)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).change_field(session_id, "real_name", fields[0], msgid=msgid(fields))

@command("addr")
class ChangeAddress:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    @arglength(display="Address", min=validate.ADDRESS_MIN, max=validate.ADDRESS_MAX)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).change_field(session_id, "address", fields[0], msgid=msgid(fields))

@command("phone")
class ChangePhone:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    @arglength(display="Phone Number", min=validate.PHONE_MIN, max=validate.PHONE_MAX)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).change_field(session_id, "phone", fields[0], msgid=msgid(fields))

@command("email")
class ChangeEmail:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    @arglength(display="E-Mail address", min=validate.EMAIL_MIN, max=validate.EMAIL_MAX)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).change_field(session_id, "email", fields[0], msgid=msgid(fields))

@command("text")
class ChangeText:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    @arglength(display="Text", min=validate.TEXT_MIN, max=validate.TEXT_MAX)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).change_field(session_id, "text", fields[0], msgid=msgid(fields))

@command("www")
class ChangeWebsite:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    @arglength(display="WWW", min=validate.WWW_MIN, max=validate.WWW_MAX)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).change_field(session_id, "www", fields[0], msgid=msgid(fields))

@command("delete")
class DeleteNick:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).delete(session_id, fields[0], msgid=msgid(fields))

@command("whois")
class Whois:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    @arglength(display="Nick Name", min=validate.NICK_MIN, max=validate.NICK_MAX)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).whois(session_id, fields[0], msgid=msgid(fields))

@command("write")
class WriteMessage:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        msg_fields = fields[0].split(" ", 1)

        if len(msg_fields) == 2:
            receiver, message = [f.strip() for f in msg_fields]
        else:
            raise TldErrorException("Usage: /write nick message text")

        ACTION(actions.messagebox.MessageBox).send_message(session_id, receiver, message)

@command("m")
class WritePrivateMessage:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        msg_fields = fields[0].split(" ", 1)

        if len(msg_fields) == 2:
            receiver, message = [f.strip() for f in msg_fields]
        else:
            raise TldErrorException("Usage: /m nick message text")

        ACTION(actions.privatemessage.PrivateMessage).send(session_id, receiver, message)

@command("read")
class ReadMessages:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0]:
            raise TldErrorException("Usage: /read")

        ACTION(actions.messagebox.MessageBox).read_messages(session_id, msgid=msgid(fields))

@command("whereis")
class Whereis:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise TldErrorException("Usage: /whereis nick")

        ACTION(actions.usersession.UserSession).whereis(session_id, fields[0], msgid(fields))

@command("beep")
class Beep:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise TldErrorException("Usage: /beep nick")

        ACTION(actions.beep.Beep).beep(session_id, fields[0])

@command("nobeep")
class NoBeep:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise TldErrorException("Usage: /nobeep on/off/verbose")

        ACTION(actions.beep.Beep).set_mode(session_id, fields[0])

@command("away")
class Away:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        ACTION(actions.away.Away).away(session_id, fields[0])

@command("noaway")
class NoAway:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0]:
            raise TldErrorException("Usage: /noaway")

        ACTION(actions.away.Away).noaway(session_id)

@command("w")
class Userlist:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0]:
            if fields[0] == "-s":
                ACTION(actions.list.List).shortlist(session_id, with_members=True, msgid=msgid(fields))
            elif fields[0] == "-g":
                ACTION(actions.list.List).shortlist(session_id, with_members=False, msgid=msgid(fields))
            else:
                ACTION(actions.list.List).list_group(session_id, fields[0], msgid(fields))
        else:
            ACTION(actions.list.List).list(session_id, msgid=msgid(fields))

@command("motd")
class Motd:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0]:
            raise TldErrorException("Usage: /motd")

        ACTION(actions.motd.Motd).receive(session_id, msgid(fields))

@command("topic")
class ChangeTopic:
    @staticmethod
    @loginrequired
    @fieldslength(count=1)
    @arglength(display="Topic", min=validate.TOPIC_MIN, max=validate.TOPIC_MAX)
    def process(session_id, fields):
        if fields[0]:
            ACTION(actions.group.Group).set_topic(session_id, fields[0])
        else:
            ACTION(actions.group.Group).topic(session_id, msgid(fields))

@command("status")
class Status:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0]:
            ACTION(actions.group.Group).change_status(session_id, fields[0])
        else:
            ACTION(actions.group.Group).status(session_id, msgid(fields))

@command("invite")
class Invite:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        usage = "Usage: invite {-q} {-r} {-n nickname | -s address}"

        try:
            opts, nick = tld.get_opts(fields[0], quiet="q", registered="r", mode="ns")

            if not nick:
                raise TldErrorException(usage)

        except:
            raise TldErrorException(usage)

        ACTION(actions.group.Group).invite(session_id, nick, **opts)

@command("cancel")
class Cancel:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        usage = "Usage: cancel {-q} {-n nickname | -s address}"

        try:
            opts, nick = tld.get_opts(fields[0], quiet="q", mode="ns")

            if not nick:
                raise TldErrorException(usage)

        except:
            raise TldErrorException(usage)

        ACTION(actions.group.Group).cancel(session_id, nick, **opts)

@command("talk")
class Talk:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        usage = "Usage: talk {-q} {-d} {-r} {-n nickname | -s address}"

        try:
            opts, nick = tld.get_opts(fields[0], quiet="q", delete="d", registered="r", mode="ns")

            if not nick:
                raise TldErrorException(usage)

        except:
            raise TldErrorException(usage)

        ACTION(actions.group.Group).talk(session_id, nick, **opts)

@command("boot")
class Boot:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise TldErrorException("Usage: /boot nick")

        ACTION(actions.group.Group).boot(session_id, fields[0])

@command("pass")
class Pass:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0]:
            ACTION(actions.group.Group).pass_over(session_id, fields[0])
        else:
            ACTION(actions.group.Group).relinquish(session_id)

@command("reputation")
class Reputation:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise TldErrorException("Usage: /reputation nick")

        ACTION(actions.admin.Admin).get_reputation(session_id, fields[0], msgid(fields))

@command("help")
class Help:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0]:
            ACTION(actions.help.Help).query(session_id, fields[0], msgid(fields))
        else:
            ACTION(actions.help.Help).introduction(session_id, msgid(fields))


COMMANDS = {cls.command: cls() for cls in filter(lambda cls: isinstance(cls, type) and "command" in cls.__dict__,
                                                 sys.modules[__name__].__dict__.values())}

@code("h")
class Command:
    @staticmethod
    @loginrequired
    @textfields
    @catchtldexceptions
    @fieldslength(min=1, max=3)
    def process(session_id, fields):
        cmd = COMMANDS.get(fields[0])

        if not cmd:
            raise TldErrorException("Unsupported command: '%s'" % fields[0])

        cmd.process(session_id, fields[1:])

@code("l")
class Ping:
    @staticmethod
    @loginrequired
    @textfields
    @catchtldexceptions
    @fieldslength(min=0, max=1)
    def process(session_id, fields):
        ACTION(actions.ping.Ping).ping(session_id, msgid(fields))

@code("m")
class Pong:
    @staticmethod
    @loginrequired
    @textfields
    @catchtldexceptions
    def process(session_id, fields):
        pass
