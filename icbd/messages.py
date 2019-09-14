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
import ltd
from actions import ACTION
import actions.away
import actions.group
import actions.messagebox
import actions.motd
import actions.beep
import actions.echoback
import actions.hush
import actions.notification
import actions.openmessage
import actions.ping
import actions.privatemessage
import actions.registration
import actions.usersession
import actions.list
import actions.admin
import actions.help
import actions.info
import textutils
from exception import LtdErrorException, LtdResponseException

def code(id):
    def decorator(cls):
        cls.code = id

        return cls

    return decorator

def textfields(fn):
    def wrapper(session_id, fields):
        fn(session_id, [textutils.decode(b).strip(" \0") for b in fields])

    return wrapper

def loginrequired(fn):
    def wrapper(session_id, fields):
        sessions = di.default_container.resolve(session.Store)

        state = sessions.get(session_id)

        if not state.loggedin:
            raise LtdErrorException("Login required.")

        fn(session_id, fields)

    return wrapper

def catchltdexceptions(fn):
    def wrapper(session_id, fields):
        try:
            fn(session_id, fields)

        except LtdResponseException as ex:
            b = di.default_container.resolve(broker.Broker)

            b.deliver(session_id, ex.response)

    return wrapper

def fieldslength(count=0, min=0, max=0):
    def decorator(fn):
        def wrapper(session_id, fields):
            if count > 0 and len(fields) != count:
                raise LtdErrorException("Malformed message, wrong number of fields.")

            if len(fields) < min:
                raise LtdErrorException("Malformed message, missing fields.")

            if max > min and len(fields) > max:
                raise LtdErrorException("Malformed message, too many fields.")

            fn(session_id, fields)

        return wrapper

    return decorator

def arglength(at=0, min=0, max=0, display="Argument"):
    def decorator(fn):
        def wrapper(session_id, fields):
            val = fields[at]

            if len(val) < min:
                if min == 1:
                    raise LtdErrorException("%s cannot be empty." % display)

                raise LtdErrorException("%s requires at least %d characters." % (display, min))

            if max > min and len(val) > max:
                raise LtdErrorException("%s exceeds allowed maximum length (%d characters)." % (display, max))

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
            raise LtdErrorException("Unsupported login type: '%s'" % fields[3])

        fn(*args)

@code("b")
class OpenMessage:
    @staticmethod
    @loginrequired
    @textfields
    @catchltdexceptions
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
    @fieldslength(count=1)
    def process(session_id, fields):
        msg_fields = fields[0].split(" ")

        if len(msg_fields) == 2:
            old_pwd, new_pwd = msg_fields

            ACTION(actions.registration.Registration).change_password(session_id, old_pwd, new_pwd)
        else:
            raise LtdErrorException("Usage: /cp {old password} {new password}")

@command("newpasswd")
class ResetPassword:
    @staticmethod
    @fieldslength(count=1)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).reset_password(session_id, fields[0])

@command("passwd")
class ChangeUserPassword:
    @staticmethod
    @loginrequired
    @fieldslength(count=1)
    def process(session_id, fields):
        msg_fields = fields[0].split(" ")

        if len(msg_fields) == 2:
            nick, password = msg_fields

            ACTION(actions.admin.Admin).change_password(session_id, nick, password)
        else:
            raise LtdErrorException("Usage: /passwd {nick} {new password}")

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

@command("avatar")
class ChangeAvatar:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    @arglength(display="Avatar", min=validate.AVATAR_MIN, max=validate.AVATAR_MAX)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).change_field(session_id, "avatar", fields[0], msgid=msgid(fields))

@command("forward")
class EnableForwarding:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).enable_forwarding(session_id, enabled=True, msgid=msgid(fields))

@command("noforward")
class DisableForwarding:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).enable_forwarding(session_id, enabled=False, msgid=msgid(fields))

@command("protect")
class EnableProtection:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).set_protected(session_id, protected=True, msgid=msgid(fields))

@command("noprotect")
class DisableProtection:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).set_protected(session_id, protected=False, msgid=msgid(fields))

@command("confirm")
class ConfirmEmail:
    @staticmethod
    @loginrequired
    @fieldslength(min=0, max=1)
    def process(session_id, fields):
        if fields and fields[0]:
            ACTION(actions.registration.Registration).confirm(session_id, fields[0])
        else:
            ACTION(actions.registration.Registration).request_confirmation(session_id)

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

@command("display")
class DisplayAvatar:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    @arglength(display="Nick Name", min=validate.NICK_MIN, max=validate.NICK_MAX)
    def process(session_id, fields):
        ACTION(actions.registration.Registration).display_avatar(session_id, fields[0], msgid=msgid(fields))

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
            raise LtdErrorException("Usage: /write {nick} {message}")

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
            raise LtdErrorException("Usage: /m {nick} {message}")

        ACTION(actions.privatemessage.PrivateMessage).send(session_id, receiver, message)

@command("exclude")
class Exclude:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        msg_fields = fields[0].split(" ", 1)

        if len(msg_fields) == 2:
            receiver, message = [f.strip() for f in msg_fields]
        else:
            raise LtdErrorException("Usage: /exclude {nick} {message}")

        ACTION(actions.openmessage.OpenMessage).send(session_id, message, exclude=receiver)

@command("read")
class ReadMessages:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0]:
            raise LtdErrorException("Usage: /read")

        ACTION(actions.messagebox.MessageBox).read_messages(session_id, msgid=msgid(fields))

@command("whereis")
class Whereis:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        usage = "Usage: whereis {-a} {nick}"

        if fields[0]:
            try:
                opts, nick = ltd.get_opts(fields[0], mode="a")

                if not nick:
                    raise LtdErrorException(usage)

            except:
                raise LtdErrorException(usage)

            ACTION(actions.usersession.UserSession).whereis(session_id, nick, **opts, msgid=msgid(fields))
        else:
            raise LtdErrorException(usage)

@command("beep")
class Beep:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise LtdErrorException("Usage: /beep {nick}")

        ACTION(actions.beep.Beep).beep(session_id, fields[0])

@command("nobeep")
class NoBeep:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise LtdErrorException("Usage: /nobeep {on|off|verbose}")

        ACTION(actions.beep.Beep).set_mode(session_id, fields[0])

@command("echoback")
class Echoback:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise LtdErrorException("Usage: /echoback {on|off|verbose}")

        ACTION(actions.echoback.Echoback).set_mode(session_id, fields[0])

@command("hush")
class Hush:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        usage = "Usage: hush {-q} {-n nick|-s address}"

        if fields[0]:
            try:
                opts, target = ltd.get_opts(fields[0], quiet="q", mode="ns", msg_type="op")

                if not target:
                    raise LtdErrorException(usage)

            except:
                raise LtdErrorException(usage)

            ACTION(actions.hush.Hush).toggle(session_id, target, **opts)
        else:
            ACTION(actions.hush.Hush).list(session_id)

@command("notify")
class Notify:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        usage = "Usage: notify {-q} {-n nick|-s address}"

        if fields[0]:
            try:
                opts, target = ltd.get_opts(fields[0], quiet="q", mode="ns")

                if not target:
                    raise LtdErrorException(usage)

            except:
                raise LtdErrorException(usage)

            ACTION(actions.notification.Notify).toggle(session_id, target, **opts)
        else:
            ACTION(actions.notification.Notify).list(session_id)

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
            raise LtdErrorException("Usage: /noaway")

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
            raise LtdErrorException("Usage: /motd")

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
        usage = "Usage: invite {-q} {-r} {-n nick|-s address}"

        try:
            opts, nick = ltd.get_opts(fields[0], quiet="q", registered="r", mode="ns")

            if not nick:
                raise LtdErrorException(usage)

        except:
            raise LtdErrorException(usage)

        ACTION(actions.group.Group).invite(session_id, nick, **opts)

@command("cancel")
class Cancel:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        usage = "Usage: cancel {-q} {-n nick|-s address}"

        try:
            opts, nick = ltd.get_opts(fields[0], quiet="q", mode="ns")

            if not nick:
                raise LtdErrorException(usage)

        except:
            raise LtdErrorException(usage)

        ACTION(actions.group.Group).cancel(session_id, nick, **opts)

@command("talk")
class Talk:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        usage = "Usage: talk {-q} {-d} {-r} {-n nick|-s address}"

        try:
            opts, nick = ltd.get_opts(fields[0], quiet="q", delete="d", registered="r", mode="ns")

            if not nick:
                raise LtdErrorException(usage)

        except:
            raise LtdErrorException(usage)

        ACTION(actions.group.Group).talk(session_id, nick, **opts)

@command("boot")
class Boot:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise LtdErrorException("Usage: /boot {nick}")

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
            raise LtdErrorException("Usage: /reputation {nick}")

        ACTION(actions.admin.Admin).get_reputation(session_id, fields[0], msgid(fields))

@command("wall")
class Wall:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise LtdErrorException("Usage: /wall {message}")

        ACTION(actions.admin.Admin).wall(session_id, fields[0])

@command("log")
class Log:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0] and not fields[0].isdigit():
            raise LtdErrorException("Usage: /log {level}")

        if fields[0]:
            ACTION(actions.admin.Admin).set_log_level(session_id, int(fields[0]), msgid(fields))
        else:
            ACTION(actions.admin.Admin).log_level(session_id, msgid(fields))

@command("drop")
class Drop:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if not fields[0]:
            raise LtdErrorException("Usage: /drop {nicknames}")

        nicks = [n.strip() for n in fields[0].split(" ")]

        ACTION(actions.admin.Admin).drop(session_id, nicks)

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

@command("v")
class Version:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0]:
            raise LtdErrorException("Usage: /v")

        ACTION(actions.info.Info).version(session_id, msgid(fields))

@command("stats")
class Stats:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        usage = "Usage: /stats {-s|-t|-m|-y|-a}"

        try:
            opts, rest = ltd.get_opts(fields[0], timeframe="stmya")

            if rest:
                raise LtdErrorException(usage)

            ACTION(actions.info.Info).stats(session_id, **opts, msgid=msgid(fields))
        except LtdErrorException as ex:
            raise ex
        except:
            raise LtdErrorException(usage)

@command("news")
class News:
    @staticmethod
    @loginrequired
    @fieldslength(min=1, max=2)
    def process(session_id, fields):
        if fields[0] and not fields[0].isdigit():
            raise LtdErrorException("Usage: /news {item}")

        if fields[0]:
            ACTION(actions.info.Info).news_item(session_id, int(fields[0]), msgid(fields))
        else:
            ACTION(actions.info.Info).all_news(session_id, msgid(fields))

COMMANDS = {cls.command: cls() for cls in filter(lambda cls: isinstance(cls, type) and "command" in cls.__dict__,
                                                 sys.modules[__name__].__dict__.values())}

@code("h")
class Command:
    @staticmethod
    @loginrequired
    @textfields
    @catchltdexceptions
    @fieldslength(min=1, max=3)
    def process(session_id, fields):
        cmd = COMMANDS.get(fields[0])

        if not cmd:
            raise LtdErrorException("Unsupported command: '%s'" % fields[0])

        cmd.process(session_id, fields[1:])

@code("l")
class Ping:
    @staticmethod
    @loginrequired
    @textfields
    @catchltdexceptions
    @fieldslength(min=0, max=1)
    def process(session_id, fields):
        ACTION(actions.ping.Ping).ping(session_id, msgid(fields))

@code("m")
class Pong:
    @staticmethod
    @loginrequired
    def process(session_id, fields):
        pass

@code("n")
class Noop:
    @staticmethod
    @loginrequired
    def process(session_id, fields):
        pass
