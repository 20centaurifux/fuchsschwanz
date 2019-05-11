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
import config, di, session, broker, groups, validate
import database, nickdb, tld, validate, motd
import re, sys, secrets
from utils import Cache
from textwrap import wrap
from datetime import datetime
from exception import TldResponseException, TldStatusException, TldErrorException
from logger import log

class Injected(di.Injected):
    def __init__(self):
        super().__init__()

    def inject(self,
               session: session.Store,
               broker: broker.Broker,
               groups: groups.Store,
               db_connection: database.Connection,
               nickdb: nickdb.NickDb):
        self.session = session
        self.broker = broker
        self.groups = groups
        self.db_connection = db_connection
        self.nickdb = nickdb

INSTANCE = Cache()

class UserSession(Injected):
    def __init__(self):
        super().__init__()

    def login(self, session_id, loginid, nick, password, group):
        log.debug("User login: loginid='%s', nick='%s', password='%s'" % (loginid, nick, password))

        if not validate.is_valid_loginid(loginid):
            raise TldErrorException("loginid is invalid. Length must be between %d and %d characters)." % (validate.LOGINID_MIN, LOGINID_MAX))

        if not validate.is_valid_nick(nick):
            raise TldErrorException("Nickname is invalid. Length must be between %d and %d characters)." % (validate.NICK_MIN, validate.NICK_MAX))

        self.broker.deliver(session_id, tld.encode_empty_cmd("a"))

        if nick == config.NICKSERV:
            raise TldStatusException("Register", "Nick already in use.")

        INSTANCE(Motd).receive(session_id)

        registered = config.ENABLE_UNSECURE_LOGIN and self.__try_login_unsecure__(session_id, loginid, nick)

        if not registered:
            if len(password) == 0:
                self.__login_no_password__(session_id, loginid, nick)
            else:
                registered = self.__login_password__(session_id, loginid, nick, password)

        self.session.update(session_id, signon=datetime.utcnow())

        registration = INSTANCE(Registration)

        if registered:
            registration.mark_registered(session_id)

        registration.notify_messagebox(session_id)

        if not group:
            group = config.DEFAULT_GROUP

        self.join(session_id, group)

    def __try_login_unsecure__(self, session_id, loginid, nick):
        log.debug("Testing unsecure authentication.")

        registered = False

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                log.debug("Nick found, testing security level.")

                if not self.nickdb.is_secure(scope, nick):
                    log.debug("Nick allows auto-register.")

                    lastlogin = self.nickdb.get_lastlogin(scope, nick)

                    if lastlogin:
                        state = self.session.get(session_id)
                        registered = (lastlogin[0] == loginid and lastlogin[1] == state.host)
                    else:
                       log.debug("First login, skipping auto-register.")
                else:
                    log.debug("Nick doesn't allow auto-register.")
        
        if registered:
            loggedin_session = self.session.find_nick(nick)

            if loggedin_session:
                self.__auto_rename__(loggedin_session)

            self.session.update(session_id, loginid=loginid, nick=nick)

        return registered

    def __login_no_password__(self, session_id, loginid, nick):
        log.debug("No password given, skipping authentication.")

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session:
            log.debug("'%s' already logged in, aborting login." % nick)

            raise TldStatusException("Register", "Nick already in use.")

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                if self.nickdb.is_admin(scope, nick):
                    raise TldErrorException("You need a password to login as administrator.")
                else:
                    self.broker.deliver(session_id, tld.encode_status_msg("Register", "Send password to authenticate your nickname."))
            else:
                self.broker.deliver(session_id, tld.encode_status_msg("No-Pass", "Your nickname does not have a password."))
                self.broker.deliver(session_id, tld.encode_status_msg("No-Pass", "For help type /m server ?"))

        self.session.update(session_id, loginid=loginid, nick=nick)

    def __login_password__(self, session_id, loginid, nick, password):
        log.debug("Password set, trying to authenticate '%s'." % nick)

        registered = False
        is_admin = False

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                registered = self.nickdb.check_password(scope, nick, password)
                is_admin = self.nickdb.is_admin(scope, nick)

            if not registered:
                log.debug("Password is invalid.")

                self.broker.deliver(session_id, tld.encode_str("e", "Authorization failure"))
                self.broker.deliver(session_id, tld.encode_status_msg("Register", "Send password to authenticate your nickname."))

                if is_admin:
                    raise TldErrorException("You need a password to login as administrator.")

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session and not registered:
            log.debug("'%s' already logged in, aborting login." % nick)

            raise TldStatusException("Register", "Nick already in use.")

        if loggedin_session:
            self.__auto_rename__(loggedin_session)

        self.session.update(session_id, loginid=loginid, nick=nick)

        return registered

    def __auto_rename__(self, session_id):
        state = self.session.get(session_id)

        prefix, _ = self.__split_name__(state.nick)
        new_nick = self.__guess_nick__(prefix, 1)

        if not new_nick:
            prefix, _ = self.__split_name__(state.loginid)
            new_nick = self.__guess_nick__(prefix, 1)

        while not new_nick:
            new_nick = self.__guess_nick__(secrets.token_hex(8), 1)

        self.rename(session_id, new_nick)

    def __split_name__(self, name):
        prefix = name
        suffix = 1

        m = re.match("(.*)-([0-9]+)$", name)

        if m:
            prefix = m.group(1)
            suffix = int(m.group(2))

        return prefix, suffix

    def __guess_nick__(self, name, suffix):
        nick = "%s-%d" % (name, suffix)
        guessed = None

        if validate.is_valid_nick(nick):
            if not self.session.find_nick(nick):
                guessed = nick
            elif suffix != 10:
                guessed = self.__guess_nick__(name, suffix + 1)

        return guessed

    def rename(self, session_id, nick):
        if not validate.is_valid_nick(nick):
            raise TldErrorException("Nick is invalid.")

        state = self.session.get(session_id)

        old_nick = state.nick
        was_authenticated = False

        if old_nick:
            log.info("Renaming '%s' to '%s'" % (old_nick, nick))

            was_authenticated = state.authenticated

            if self.session.find_nick(nick):
                raise TldErrorException("Nick already in use.")

            if state.group:
                log.debug("Renaming '%s' to '%s' in channel '%s'." % (old_nick, nick, state.group))

                self.broker.to_channel(state.group, tld.encode_status_msg("Name", "%s changed nickname to %s" % (old_nick, nick)))

                if self.groups.get(state.group).moderator == session_id:
                    self.broker.to_channel(state.group, tld.encode_status_msg("Pass", "%s is now mod." % nick))

            self.session.update(session_id, nick=nick, authenticated=False)

            registered = False
            is_admin = False

            with self.db_connection.enter_scope() as scope:
                if was_authenticated and self.nickdb.exists(scope, old_nick):
                    self.nickdb.set_signoff(scope, old_nick)

                if self.nickdb.exists(scope, nick):
                    is_admin = self.nickdb.is_admin(scope, nick)

                    if self.nickdb.is_secure(scope, nick):
                        self.broker.deliver(session_id, tld.encode_status_msg("Register", "Send password to authenticate your nickname."))
                    else:
                        log.debug("Nick not secure, trying to register automatically.")

                        lastlogin = self.nickdb.get_lastlogin(scope, nick)

                        if lastlogin:
                            log.debug("Last login: %s@%s" % (lastlogin[0], lastlogin[1]))

                            registered = (lastlogin[0] == state.loginid and lastlogin[1] == state.host)
                else:
                    self.broker.deliver(session_id, tld.encode_status_msg("No-Pass", "To register your nickname type /m server p password"))

            registration = INSTANCE(Registration)
            change_failed = False

            if registered:
                registration.mark_registered(session_id)
            else:
                change_failed = is_admin

            if change_failed:
                self.broker.deliver(session_id, tld.encode_str("e", "Registration failed, please login to admin account with password."))

                self.__auto_rename__(session_id)
            else:               
                registration.notify_messagebox(session_id)
                self.session.update(session_id, signon=datetime.utcnow())
            
    def sign_off(self, session_id):
        state = self.session.get(session_id)

        if state.nick:
            log.debug("Dropping session: '%s'" % session_id)

            if state.authenticated:
                with self.db_connection.enter_scope() as scope:
                    self.nickdb.set_signoff(scope, state.nick)

                    scope.complete()

            if state.group:
                log.debug("Removing '%s' from channel '%s'." % (state.nick, state.group))

                if self.broker.part(session_id, state.group):
                    info = self.groups.get(state.group)

                    if info.volume != groups.Volume.QUIET:
                        self.broker.to_channel_from(session_id,
                                                    state.group,
                                                    tld.encode_status_msg("Sign-off", "%s (%s@%s) has signed off." % (state.nick, state.loginid, state.host)))

                    if info.moderator == session_id:
                        if info.volume != groups.Volume.QUIET:
                            self.broker.to_channel_from(session_id,
                                                        state.group,
                                                        tld.encode_status_msg("Sign-off", "Your group moderator signed off. (No timeout)"))

                        new_mod = {}
                        min_elapsed = -1

                        for sub_id in self.broker.get_subscribers(state.group):
                            sub_state = self.session.get(sub_id)
                            elapsed = sub_state.t_recv.elapsed()

                            if min_elapsed == -1 or elapsed < min_elapsed:
                                min_elapsed = elapsed
                                new_mod = [sub_id, sub_state.nick]

                        self.broker.to_channel(state.group, tld.encode_status_msg("Pass", "%s is now mod." % new_mod[1]))

                        info.moderator = new_mod[0]
                else:
                    self.groups.delete(state.group)

            log.debug("Removing nick '%s' from session '%s'." % (state.nick, session_id))

            self.session.update(session_id, nick=None, authenticated=False)

    def join(self, session_id, group):
        state = self.session.get(session_id)

        log.info("'%s' joins group '%s'." % (state.nick, group))

        old_group = state.group
        
        if old_group == group:
            raise TldErrorException("You are already in that group.")

        group = self.__resolve_user_group_name__(group)
        visibility, group = self.__extract_visibility_from_groupname__(group)

        if not validate.is_valid_group(group):
            raise TldErrorException("Invalid group name.")

        info = self.groups.get(group)

        if info.control == groups.Control.RESTRICTED:
            pass # TODO
        else:
            if self.broker.join(session_id, group):
                log.info("Group '%s' created." % group)

                info.visibility = visibility

                if group == config.DEFAULT_GROUP:
                    info.control = groups.Control.PUBLIC
                    info.topic = config.DEFAULT_TOPIC
                elif group == config.IDLE_GROUP:
                    info.control = groups.Control.PUBLIC
                    info.visibility = groups.Visibility.VISIBLE
                    info.volume = groups.Volume.QUIET
                    info.topic = config.IDLE_TOPIC
                else:
                    info.control = groups.Control.MODERATED
                    info.moderator = session_id

                self.groups.set(group, info)

            msg = "You are now in group %s" % group

            if info.moderator == session_id:
                msg += " as moderator"

            self.broker.deliver(session_id, tld.encode_status_msg("Status", msg))

        if info.volume != groups.Volume.QUIET:
            category = "Sign-on" if not old_group else "Arrive"
            self.broker.to_channel_from(session_id,
                                        group,
                                        tld.encode_status_msg(category, "%s (%s@%s) entered group" % (state.nick, state.loginid, state.host)))

        self.session.update(session_id, group=group)

        if old_group:
            info = self.groups.get(old_group)

            log.debug("Removing '%s' from channel '%s'." % (state.nick, old_group))

            if self.broker.part(session_id, old_group):
                if info.volume != groups.Volume.QUIET:
                    self.broker.to_channel_from(session_id,
                                                old_group,
                                                tld.encode_status_msg("Depart", "%s (%s@%s) just left" % (state.nick, state.loginid, state.host)))
            else:
                self.groups.delete(old_group)

    def __resolve_user_group_name__(self, group):
        if group.startswith("@"):
            session_id = self.session.find_nick(group[1:])

            if not session_id:
                raise TldErrorException("User not found.")

            state = self.session.get(session_id)

            if not state.group or self.groups.get(state.group).visibility != groups.Visibility.VISIBLE:
                raise TldErrorException("User not found.")

            group = state.group

        return group

    def __extract_visibility_from_groupname__(self, group):
        visibility = groups.Visibility.VISIBLE

        if group.startswith(".."):
            visibility = groups.Visibility.SUPERSECRET
            group = group[2:]
        elif group.startswith("."):
            visibility = groups.Visibility.SECRET
            group = group[1:]

        return visibility, group

    def whereis(self, session_id, nick, msgid=""):
        loggedin_session = self.session.find_nick(nick)

        if loggedin_session:
            state = self.session.get(loggedin_session)

            self.broker.deliver(session_id, tld.encode_co_output("%-16s %s (%s)" % (nick, state.host, state.ip), msgid))
        else:
            self.broker.deliver(session_id, tld.encode_co_output("Nickname not found.", msgid))

    def list(self, session_id, msgid=""):
        log.debug("Sending session list.")

        logins = self.session.get_logins()
        groups = {g: self.groups.get(g) for g in self.groups.get_groups()}

        for group, info in sorted(groups.items(), key=lambda kv: kv[0].lower()):
            self.broker.deliver(session_id, tld.encode_co_output("Group: %-27s Mod: %-16s" % (group, logins[info.moderator].nick if info.moderator else "(None)"), msgid))
            self.broker.deliver(session_id, tld.encode_co_output("Topic: %s" % info.topic if info.topic else "(None)", msgid))
            self.broker.deliver(session_id, tld.encode_co_output("Nickname           Idle            Signon (UTC)      Account", msgid))

            for sub_id, state in sorted([[sub_id, logins[sub_id]] for sub_id in self.broker.get_subscribers(group)], key=lambda arg: arg[1].nick.lower()):
                total_seconds = int(state.t_recv.elapsed())
                total_minutes = int(total_seconds / 60)
                total_hours = int(total_minutes / 60)
                minutes = total_minutes - (total_hours * 60)

                if total_hours > 0:
                    idle = "%dh%dm"  % (total_hours, minutes)
                elif total_minutes > 0:
                    idle = "%dm"  % minutes
                else:
                    idle = "%ds"  % minutes

                admin_flag = "*" if info.moderator == sub_id else " "

                self.broker.deliver(session_id, tld.encode_co_output("%s  %-16s%-16s%-18s%s@%s" % (admin_flag, state.nick, idle, state.signon.strftime("%Y/%m/%d %H:%M"), state.loginid, state.host), msgid))

            self.broker.deliver(session_id, tld.encode_co_output("", msgid))

        logins_n = len(logins) - 1
        logins_suffix = "" if logins_n == 1 else "s"

        groups_n = len(groups)
        groups_suffix = "" if groups_n == 1 else "s"

        self.broker.deliver(session_id, tld.encode_co_output("Total: %d user%s in %d group%s" % (logins_n, logins_suffix, groups_n, groups_suffix), msgid))

class OpenMessage(Injected):
    def __init__(self):
        super().__init__()

    def send(self, session_id, message):
        state = self.session.get(session_id)
        
        if state.group:
            info = self.groups.get(state.group)

            if info.volume == groups.Volume.QUIET:
                raise TldErrorException("Open messages are not permitted in quiet groups.")

            e = tld.Encoder("b")

            e.add_field_str(state.nick, append_null=False)
            e.add_field_str(message, append_null=True)

            if self.broker.to_channel_from(session_id, state.group, e.encode()) == 0:
                raise TldErrorException("No one else in group!")
        else:
            log.warning("Cannot send open message, session '%s' not logged in." % session_id)

            raise TldErrorException("Login required.")

class PrivateMessage(Injected):
    def __init__(self):
        super().__init__()

    def send(self, session_id, receiver, message):
        loggedin_session = self.session.find_nick(receiver)

        if loggedin_session:
            state = self.session.get(session_id)

            e = tld.Encoder("c")

            e.add_field_str(state.nick, append_null=False)
            e.add_field_str(message, append_null=True)

            self.broker.deliver(loggedin_session, e.encode())
        else:
            raise TldErrorException("%s is not signed on." % receiver)

class Ping(Injected):
    def __init__(self):
        super().__init__()

    def ping(self, session_id, message_id=""):
        state = self.session.get(session_id)
        
        if state.group:
            self.broker.deliver(session_id, encode_str("m", message_id))

class Group(Injected):
    def __init__(self):
        super().__init__()

    def set_topic(self, session_id, topic):
        log.debug("Setting topic.")

        name, info = self.__get_group_if_can_moderate__(session_id)

        if name in [config.DEFAULT_GROUP, config.IDLE_GROUP]:
            raise TldErrorException("You can't change this group's topic.")

        if not validate.is_valid_topic(topic):
            raise TldErrorException("Topic is invalid.")

        info.topic = topic

        self.groups.set(name, info)

        if info.volume != groups.Volume.QUIET:
            self.broker.to_channel(name, tld.encode_status_msg("Topic", "%s changed the topic to \"%s\"" % (self.session.get(session_id).nick, topic)))

    def __get_group__(self, session_id):
        state = self.session.get(session_id)
        
        if not state.group:
            log.warning("Cannot set topic, session '%s' not logged in." % session_id)

            raise TldErrorException("Login required.")

        return state.group, self.groups.get(state.group)

    def __get_group_if_can_moderate__(self, session_id):
        name, info = self.__get_group__(session_id)

        log.debug("Group's moderator: %s" % info.moderator)

        if info.moderator and info.moderator != session_id:
            log.debug("User isn't moderator, testing administrative privileges.")

            with self.db_connection.enter_scope() as scope:
                state = self.session.get(session_id)

                if not self.nickdb.exists(scope, state.nick) or not self.nickdb.is_admin(scope, state.nick):
                    raise TldErrorException("You aren't the moderator.")

        return name, info

class Registration(Injected):
    def __init__(self):
        super().__init__()

    def register(self, session_id, password):
        log.debug("Starting user registration.")

        state = self.session.get(session_id)

        if not state.nick:
            raise TldErrorException("Login required.")

        registered = False

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, state.nick):
                log.debug("Nick found, validating password.")

                if not self.nickdb.check_password(scope, state.nick, password):
                    raise TldErrorException("Authorization failure")

                registered = True
            else:
                log.info("Creating new user profile for '%s'." % state.nick)

                if not validate.is_valid_password(password):
                    raise TldStatusException("Register",
                                             "Password format not valid. Passwords length must be between %d and %d characters." % (validate.PASSWORD_MIN, validate.PASSWORD_MAX))

                self.nickdb.create(scope, state.nick)
                self.nickdb.set_secure(scope, state.nick, True)
                self.nickdb.set_admin(scope, state.nick, False)
                self.nickdb.set_password(scope, state.nick, password)

                registered = True

                scope.complete()

        if registered:
            self.mark_registered(session_id)
            self.notify_messagebox(session_id)

    def mark_registered(self, session_id):
        with self.db_connection.enter_scope() as scope:
            state = self.session.get(session_id)

            self.nickdb.set_lastlogin(scope, state.nick, state.loginid, state.host)

            now = datetime.utcnow()

            self.nickdb.set_signon(scope, state.nick, now)

            self.session.update(session_id, signon=now, authenticated=True)

            self.broker.deliver(session_id, tld.encode_status_msg("Register", "Nick registered"))

            scope.complete()

    def notify_messagebox(self, session_id):
        with self.db_connection.enter_scope() as scope:
            state = self.session.get(session_id)

            if self.nickdb.exists(scope, state.nick):
                count = self.nickdb.count_messages(scope, state.nick)

                if count > 0:
                    self.broker.deliver(session_id, tld.encode_status_msg("Message", "You have %d message%s." % (count, "" if count == 1 else "s")))

                if count >= config.MBOX_QUOTAS.get(state.nick, config.MBOX_DEFAULT_LIMIT):
                    self.broker.deliver(session_id, tld.encode_status_msg("Message", "User mailbox is full."))

    def change_password(self, session_id, old_pwd, new_pwd):
        log.debug("Changing user password.")

        state = self.session.get(session_id)

        if not state.nick:
            raise TldErrorException("Login required.")

        with self.db_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, state.nick):
                raise TldErrorException("Authorization failure")

            log.debug("Nick found, validating password.")

            if not self.nickdb.check_password(scope, state.nick, old_pwd):
                raise TldErrorException("Authorization failure")

            self.nickdb.set_password(scope, state.nick, new_pwd)

            self.broker.deliver(session_id, tld.encode_status_msg("Pass", "Password changed"))

            scope.complete()

    def set_security_mode(self, session_id, enabled, msgid=""):
        log.debug("Setting security flag: %s" % enabled)

        state = self.session.get(session_id)

        if not state.authenticated:
            raise TldErrorException("You must be registered to change your security.")

        with self.db_connection.enter_scope() as scope:
            self.nickdb.set_secure(scope, state.nick, enabled)

            if enabled:
                self.broker.deliver(session_id, tld.encode_co_output("Security set to password required.", msgid))
            else:
                self.broker.deliver(session_id, tld.encode_co_output("Security set to automatic.", msgid))

            scope.complete()

    def change_field(self, session_id, field, text, msgid=""):
        log.debug("Setting field '%s' to '%s'" % (field, text))

        state = self.session.get(session_id)

        if not state.authenticated:
            raise TldErrorException("You must be registered to change your security.")

        if not self.__validate_field__(field, text):
            raise TldResponseException("Invalid attribute.", tld.encode_co_output("'%s' format not valid." % self.__map_field__(field), msgid))

        with self.db_connection.enter_scope() as scope:
            details = self.nickdb.lookup(scope, state.nick)

            setattr(details, field, text)

            self.nickdb.update(scope, state.nick, details)

            self.broker.deliver(session_id, tld.encode_co_output("%s set to '%s'" % (self.__map_field__(field), text), msgid))

            scope.complete()

    def __map_field__(self, field):
        if field == "real_name":
            return "Real Name"
        elif field == "address":
            return "Address"
        elif field == "phone":
            return "Phone Number"
        elif field == "email":
            return "E-Mail"
        elif field == "text":
            return "Message text"
        elif field == "www":
            return "WWW"

    def __validate_field__(self, field, text):
        if field == "real_name":
            return validate.is_valid_realname(text)
        elif field == "address":
            return validate.is_valid_address(text)
        elif field == "phone":
            return validate.is_valid_phone(text)
        elif field == "email":
            return validate.is_valid_email(text)
        elif field == "text":
            return validate.is_valid_text(text)
        elif field == "www":
            return validate.is_valid_www(text)

    def delete(self, session_id, password, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise TldErrorException("You must be registered to delete your entry.")

        if not password:
            raise TldErrorException("Password required.")

        with self.db_connection.enter_scope() as scope:
            if not self.nickdb.check_password(scope, state.nick, password):
                raise TldErrorException("Password incorrect.")

            self.nickdb.delete(scope, state.nick)

            self.broker.deliver(session_id, tld.encode_co_output("Record Deleted", msgid))

            self.session.update(session_id, authentication=False)

            scope.complete()

    def whois(self, session_id, nick, msgid=""):
        state = self.session.get(session_id)

        if not nick:
            raise TldErrorException("Nickname to lookup not specified.")

        with self.db_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, nick):
                raise TldErrorException("%s is not in the database." % nick)

            signon = self.nickdb.get_signon(scope, nick)
            signoff = self.nickdb.get_signoff(scope, nick)

            details = self.nickdb.lookup(scope, nick)

        login = None
        loggedin_session = self.session.find_nick(nick)

        if loggedin_session:
            loggedin_state = self.session.get(loggedin_session)

            login = "%s@%s" % (loggedin_state.loginid, loggedin_state.host)

        msgs = bytearray()

        def display_value(text):
            if not text:
                text = "(None)"

            return text

        msgs.extend(tld.encode_co_output("Nickname:       %-24s Address:      %s" % (nick, display_value(login)), msgid))
        msgs.extend(tld.encode_co_output("Phone Number:   %-24s Real Name:    %s" % (display_value(details.phone), display_value(details.real_name)), msgid))
        msgs.extend(tld.encode_co_output("Last signon:    %-24s Last signoff: %s" % (display_value(signon), display_value(signoff)), msgid))
        msgs.extend(tld.encode_co_output("E-Mail:         %s" % display_value(details.email), msgid))
        msgs.extend(tld.encode_co_output("WWW:            %s" % display_value(details.www), msgid))

        if not details.address:
            msgs.extend(tld.encode_co_output("Street address: (None)", msgid))
        else:
            parts = [p.strip() for p in details.address.split("|")]

            msgs.extend(tld.encode_co_output("Street address: %s" % parts[0], msgid))

            for part in parts[1:]:
                msgs.extend(tld.encode_co_output("                %s" % part, msgid))

        if not details.text:
            msgs.extend(tld.encode_co_output("Text:           (None)", msgid))
        else:
            parts = wrap(details.text, 64)

            msgs.extend(tld.encode_co_output("Text:           %s" % parts[0], msgid))

            for part in parts[1:]:
                msgs.extend(tld.encode_co_output("                %s" % part, msgid))

        self.broker.deliver(session_id, msgs)

class MessageBox(Injected):
    def __init__(self):
        super().__init__()

    def send_message(self, session_id, receiver, text):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise TldErrorException("You must be registered to write a message.")

        if not validate.is_valid_nick(receiver):
            raise TldErrorException("'%s' is not a valid nick name." % receiver)

        if not validate.is_valid_message(text):
            raise TldErrorException("Message text not valid. Length has be between %d and %d characters." % (validate.MESSAGE_MIN, validate.MESSAGE_MAX))

        with self.db_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, receiver):
                raise TldErrorException("%s is not registered." % receiver)

            count = self.nickdb.count_messages(scope, receiver) + 1

            loggedin_session = self.session.find_nick(receiver)

            limit = config.MBOX_QUOTAS.get(receiver, config.MBOX_DEFAULT_LIMIT)

            if count > limit:
                if loggedin_session:
                    self.broker.deliver(loggedin_session, tld.encode_str("e", "User mailbox is full."))

                raise TldErrorException("User mailbox full")

            uuid = self.nickdb.add_message(scope, receiver, state.nick, text)

            self.broker.deliver(session_id, tld.encode_status_msg("Message", "Message '%s' saved." % uuid))

            if loggedin_session:
                self.broker.deliver(session_id, tld.encode_status_msg("Warning", "%s is logged in now." % receiver))
                self.broker.deliver(loggedin_session, tld.encode_status_msg("Message", "You have %d message%s." % (count, "" if count == 1 else "s")))

                if count == limit:
                    self.broker.deliver(loggedin_session, tld.encode_str("e", "User mailbox is full."))

            scope.complete()

    def read_messages(self, session_id, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise TldErrorException("You must be registered to read any messages.")

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.count_messages(scope, state.nick) == 0:
                raise TldErrorException("No messages")

            for msg in self.nickdb.get_messages(scope, state.nick):
                self.broker.deliver(session_id, tld.encode_co_output("Message left at %s" % msg.date, msgid))

                e = tld.Encoder("c")

                e.add_field_str(msg.sender, append_null=False)
                e.add_field_str(msg.text, append_null=True)

                self.broker.deliver(session_id, e.encode())

                self.nickdb.delete_message(scope, msg.uuid)

            scope.complete()

class Motd(Injected):
    def __init__(self):
        super().__init__()

    def receive(self, session_id, msgid=""):
        try:
            for line in motd.load():
                self.broker.deliver(session_id, tld.encode_co_output(line, msgid))

        except Exception as ex:
            log.warn(str(ex))
