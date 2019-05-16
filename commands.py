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
import re
import secrets
from textwrap import wrap
from datetime import datetime
import config
import di
import session
import broker
import groups
import validate
import database
import nickdb
import tld
import motd
from utils import Cache, Timer
from exception import TldResponseException, TldStatusException, TldErrorException
from logger import log

class Injected(di.Injected):
    def inject(self,
               session: session.Store,
               away_table: session.AwayTimeoutTable,
               broker: broker.Broker,
               groups: groups.Store,
               db_connection: database.Connection,
               nickdb: nickdb.NickDb):
        self.session = session
        self.away_table = away_table
        self.broker = broker
        self.groups = groups
        self.db_connection = db_connection
        self.nickdb = nickdb

INSTANCE = Cache()

class UserSession(Injected):
    def login(self, session_id, loginid, nick, password, group):
        log.debug("User login: loginid='%s', nick='%s', password='%s'", loginid, nick, password)

        if not validate.is_valid_loginid(loginid):
            raise TldErrorException("loginid is invalid. Length must be between %d and %d characters)."
                                    % (validate.LOGINID_MIN, validate.LOGINID_MAX))

        if not validate.is_valid_nick(nick):
            raise TldErrorException("Nickname is invalid. Length must be between %d and %d characters)."
                                    % (validate.NICK_MIN, validate.NICK_MAX))

        self.broker.deliver(session_id, tld.encode_empty_cmd("a"))

        if nick == config.NICKSERV:
            raise TldStatusException("Register", "Nick already in use.")

        INSTANCE(Motd).receive(session_id)

        registered = config.ENABLE_UNSECURE_LOGIN and self.__try_login_unsecure__(session_id, loginid, nick)

        if not registered:
            if not password:
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
            log.debug("'%s' already logged in, aborting login.", nick)

            raise TldStatusException("Register", "Nick already in use.")

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                if self.nickdb.is_admin(scope, nick):
                    raise TldErrorException("You need a password to login as administrator.")

                self.broker.deliver(session_id, tld.encode_status_msg("Register",
                                                                      "Send password to authenticate your nickname."))
            else:
                self.broker.deliver(session_id, tld.encode_status_msg("No-Pass",
                                                                      "Your nickname does not have a password."))

                self.broker.deliver(session_id, tld.encode_status_msg("No-Pass",
                                                                      "For help type /m server ?"))

        self.session.update(session_id, loginid=loginid, nick=nick)

    def __login_password__(self, session_id, loginid, nick, password):
        log.debug("Password set, trying to authenticate '%s'.", nick)

        registered = False
        is_admin = False

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                registered = self.nickdb.check_password(scope, nick, password)
                is_admin = self.nickdb.is_admin(scope, nick)

            if not registered:
                log.debug("Password is invalid.")

                self.broker.deliver(session_id, tld.encode_str("e", "Authorization failure"))
                self.broker.deliver(session_id, tld.encode_status_msg("Register",
                                                                      "Send password to authenticate your nickname."))

                if is_admin:
                    raise TldErrorException("You need a password to login as administrator.")

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session and not registered:
            log.debug("'%s' already logged in, aborting login.", nick)

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

    @staticmethod
    def __split_name__(name):
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
            log.info("Renaming '%s' to '%s'", old_nick, nick)

            was_authenticated = state.authenticated

            if self.session.find_nick(nick):
                raise TldErrorException("Nick already in use.")

            if state.group:
                log.debug("Renaming '%s' to '%s' in channel '%s'.", old_nick, nick, state.group)

                self.broker.to_channel(state.group,
                                       tld.encode_status_msg("Name",
                                                             "%s changed nickname to %s" % (old_nick, nick)))

                if self.groups.get(state.group).moderator == session_id:
                    self.broker.to_channel(state.group,
                                           tld.encode_status_msg("Pass",
                                                                 "%s is now mod." % nick))

            self.session.update(session_id, nick=nick, authenticated=False)

            registered = False
            is_admin = False

            with self.db_connection.enter_scope() as scope:
                if was_authenticated and self.nickdb.exists(scope, old_nick):
                    self.nickdb.set_signoff(scope, old_nick)

                if self.nickdb.exists(scope, nick):
                    is_admin = self.nickdb.is_admin(scope, nick)

                    if self.nickdb.is_secure(scope, nick):
                        self.broker.deliver(session_id,
                                            tld.encode_status_msg("Register",
                                                                  "Send password to authenticate your nickname."))
                    else:
                        log.debug("Nick not secure, trying to register automatically.")

                        lastlogin = self.nickdb.get_lastlogin(scope, nick)

                        if lastlogin:
                            log.debug("Last login: %s@%s", lastlogin[0], lastlogin[1])

                            registered = (lastlogin[0] == state.loginid and lastlogin[1] == state.host)
                else:
                    self.broker.deliver(session_id,
                                        tld.encode_status_msg("No-Pass",
                                                              "To register your nickname type /m server p password"))

            registration = INSTANCE(Registration)
            change_failed = False

            if registered:
                registration.mark_registered(session_id)
            else:
                change_failed = is_admin

            if change_failed:
                self.broker.deliver(session_id,
                                    tld.encode_str("e",
                                                   "Registration failed, please login to admin account with password."))

                self.__auto_rename__(session_id)
            else:
                registration.notify_messagebox(session_id)
                self.session.update(session_id, signon=datetime.utcnow())

    def sign_off(self, session_id):
        state = self.session.get(session_id)

        if state.nick:
            log.debug("Dropping session: '%s'", session_id)

            if state.authenticated:
                with self.db_connection.enter_scope() as scope:
                    self.nickdb.set_signoff(scope, state.nick)

                    scope.complete()

            if state.group:
                log.debug("Removing '%s' from channel '%s'.", state.nick, state.group)

                if self.broker.part(session_id, state.group):
                    info = self.groups.get(state.group)

                    if info.volume != groups.Volume.QUIET:
                        self.broker.to_channel_from(session_id,
                                                    state.group,
                                                    tld.encode_status_msg("Sign-off",
                                                                          "%s (%s) has signed off." % (state.nick, state.address)))

                    if info.moderator == session_id:
                        if info.volume != groups.Volume.QUIET:
                            self.broker.to_channel_from(session_id,
                                                        state.group,
                                                        tld.encode_status_msg("Sign-off",
                                                                              "Your group moderator signed off. (No timeout)"))

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

            log.debug("Removing nick '%s' from session '%s'.", state.nick, session_id)

            self.session.update(session_id, nick=None, authenticated=False)

    def join(self, session_id, group):
        state = self.session.get(session_id)

        log.info("'%s' joins group '%s'.", state.nick, group)

        old_group = state.group

        group = self.__resolve_user_group_name__(group)
        visibility, group = self.__extract_visibility_from_groupname__(group)

        if not validate.is_valid_group(group):
            raise TldErrorException("Invalid group name.")

        if old_group == group:
            raise TldErrorException("You are already in that group.")

        info = self.groups.get(group)

        if info.control == groups.Control.RESTRICTED:
            if (info.moderator != session_id
                    and not (info.nick_invited(state.nick, state.authenticated)
                             or info.address_invited(state.loginid, state.ip, state.host, state.authenticated))):
                if info.volume == groups.Volume.LOUD:
                    self.broker.deliver(info.moderator,
                                        tld.encode_status_msg("Probe",
                                                              "%s tried to enter group %s." % (state.nick, group)))

                raise TldErrorException("%s is restricted." % group)

            self.broker.join(session_id, group)
        else:
            if self.broker.join(session_id, group):
                log.info("Group '%s' created.", group)

                info.visibility = visibility

                if group == config.DEFAULT_GROUP:
                    info.control = groups.Control.PUBLIC
                    info.topic = config.DEFAULT_TOPIC
                elif group == config.IDLE_GROUP:
                    info.control = groups.Control.PUBLIC
                    info.visibility = groups.Visibility.VISIBLE
                    info.volume = groups.Volume.QUIET
                    info.topic = config.IDLE_TOPIC
                elif group == config.BOOT_GROUP:
                    info.control = groups.Control.PUBLIC
                    info.visibility = groups.Visibility.VISIBLE
                    info.volume = groups.Volume.LOUD
                    info.topic = config.BOOT_TOPIC
                else:
                    info.control = groups.Control.MODERATED
                    info.moderator = session_id

                self.groups.update(info)

        msg = "You are now in group %s" % group

        if info.moderator == session_id:
            msg += " as moderator"

        self.broker.deliver(session_id, tld.encode_status_msg("Status", msg))

        if info.volume != groups.Volume.QUIET:
            category = "Sign-on" if not old_group else "Arrive"
            self.broker.to_channel_from(session_id,
                                        group,
                                        tld.encode_status_msg(category,
                                                              "%s (%s) entered group" % (state.nick, state.address)))

        self.session.update(session_id, group=info.key)

        if old_group:
            info = self.groups.get(old_group)

            log.debug("Removing '%s' from channel '%s'.", state.nick, old_group)

            if self.broker.part(session_id, old_group):
                if info.volume != groups.Volume.QUIET:
                    self.broker.to_channel_from(session_id,
                                                old_group,
                                                tld.encode_status_msg("Depart",
                                                                      "%s (%s) just left" % (state.nick, state.address)))
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
            visibility = groups.Visibility.INVISIBLE
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

    def list_and_quit(self, session_id, msgid=""):
        self.list(session_id, msgid)

        self.broker.deliver(session_id, tld.encode_empty_cmd("g"))

    def list(self, session_id, msgid=""):
        log.debug("Sending session list.")

        logins = self.session.get_nicks()

        is_admin = False

        state = self.session.get(session_id)

        if state.authenticated:
            with self.db_connection.enter_scope() as scope:
                is_admin = self.nickdb.is_admin(scope, state.nick)

        available_groups = self.groups.get_groups()

        for info in available_groups:
            show_group = True
            display_name = str(info)

            if info.visibility != groups.Visibility.VISIBLE:
                if is_admin or state.group == info.key:
                    display_name = "*%s*" % str(info)
                else:
                    display_name = "-SECRET-"
                    show_group = info.visibility != groups.Visibility.INVISIBLE

            if show_group:
                moderator = logins[info.moderator].nick if info.moderator else "(None)"

                self.broker.deliver(session_id,
                                    tld.encode_co_output("Group: %-27s Mod: %-16s" % (display_name, moderator), msgid))

                self.broker.deliver(session_id,
                                    tld.encode_co_output("Topic: %s" % (info.topic if info.topic else "(None)"), msgid))

                self.broker.deliver(session_id,
                                    tld.encode_co_output("Nickname           Idle            Signon (UTC)      Account", msgid))

                subscribers = sorted([[sub_id, logins[sub_id]] for sub_id in self.broker.get_subscribers(info.key)],
                                     key=lambda arg: arg[1].nick.lower())

                for sub_id, sub_state in subscribers:
                    admin_flag = "*" if info.moderator == sub_id else " "

                    self.broker.deliver(session_id,
                                        tld.encode_co_output("%s  %-16s%-16s%-18s%s" % (admin_flag,
                                                                                        sub_state.nick,
                                                                                        sub_state.t_recv.elapsed_str(),
                                                                                        sub_state.signon.strftime("%Y/%m/%d %H:%M"),
                                                                                        sub_state.address),
                                                             msgid))

                self.broker.deliver(session_id, tld.encode_co_output("", msgid))

        logins_n = len(logins) - 1
        logins_suffix = "" if logins_n == 1 else "s"

        groups_n = len(available_groups)
        groups_suffix = "" if groups_n == 1 else "s"

        self.broker.deliver(session_id,
                            tld.encode_co_output("Total: %d user%s in %d group%s" % (logins_n, logins_suffix, groups_n, groups_suffix),
                                                 msgid))

class OpenMessage(Injected):
    def send(self, session_id, message):
        state = self.session.get(session_id)

        if state.group:
            info = self.groups.get(state.group)

            if info.volume == groups.Volume.QUIET:
                raise TldErrorException("Open messages are not permitted in quiet groups.")

            if info.control == groups.Control.CONTROLLED:
                if (not info.nick_can_talk(state.nick, state.authenticated)
                        and not info.address_can_talk(state.loginid, state.ip, state.host, state.authenticated)):
                    raise TldErrorException("You do not have permission to talk in this group.")

            e = tld.Encoder("b")

            e.add_field_str(state.nick, append_null=False)
            e.add_field_str(message, append_null=True)

            if self.broker.to_channel_from(session_id, state.group, e.encode()) == 0:
                raise TldErrorException("No one else in group!")
        else:
            log.warning("Cannot send open message, session '%s' not logged in.", session_id)

            raise TldErrorException("Login required.")

class PrivateMessage(Injected):
    def send(self, session_id, receiver, message):
        loggedin_session = self.session.find_nick(receiver)

        if loggedin_session:
            state = self.session.get(session_id)

            e = tld.Encoder("c")

            e.add_field_str(state.nick, append_null=False)
            e.add_field_str(message, append_null=True)

            self.broker.deliver(loggedin_session, e.encode())

            loggedin_state = self.session.get(loggedin_session)

            if loggedin_state.away:
                if not self.away_table.is_alive(session_id, receiver):
                    self.broker.deliver(session_id, tld.encode_status_msg("Away",
                                                                          "%s (since %s)" % (loggedin_state.away,
                                                                                             loggedin_state.t_away.elapsed_str())))
                    self.away_table.set_alive(session_id, receiver, config.AWAY_MSG_TIMEOUT)
        else:
            raise TldErrorException("%s is not signed on." % receiver)

class Ping(Injected):
    def ping(self, session_id, message_id=""):
        state = self.session.get(session_id)

        if state.group:
            self.broker.deliver(session_id, tld.encode_str("m", message_id))

class Group(Injected):
    def set_topic(self, session_id, topic):
        info = self.__get_group_if_can_moderate__(session_id)

        if not validate.is_valid_topic(topic):
            raise TldErrorException("Topic is invalid.")

        info.topic = topic

        self.groups.update(info)

        if info.volume != groups.Volume.QUIET:
            self.broker.to_channel(str(info), tld.encode_status_msg("Topic",
                                                                    "%s changed the topic to \"%s\"" % (self.session.get(session_id).nick,
                                                                                                        topic)))

    def topic(self, session_id, msgid):
        info = self.__get_group__(session_id)

        if info.topic:
            self.broker.deliver(session_id, tld.encode_co_output("The topic is: %s" % info.topic, msgid))
        else:
            self.broker.deliver(session_id, tld.encode_co_output("The topic is not set.", msgid))

    def change_status(self, session_id, flags):
        state = self.session.get(session_id)
        info = self.__get_group_if_can_moderate__(session_id)

        for flag in [f.strip() for f in flags.split(" ")]:
            if len(flag) == 1:
                if (self.__try_change_visibility__(session_id, state.nick, info, flag)
                        or self.__try_change_volume__(session_id, state.nick, info, flag)
                        or self.__try_change_control__(session_id, state.nick, info, flag)):
                    self.groups.update(info)
                else:
                    self.broker.deliver(session_id, tld.encode_str("e", "Option %s is unknown." % flag))
            else:
                self.broker.deliver(session_id, tld.encode_str("e", "Option %s is unknown." % flag))

    def __try_change_visibility__(self, session_id, nick, info, flag):
        found = True

        try:
            visibility = groups.Visibility(ord(flag))

            if info.visibility == visibility:
                self.broker.deliver(session_id, tld.encode_str("e", "Group is already %s." % str(visibility)))
            else:
                info.visibility = visibility

                self.broker.to_channel(str(info), tld.encode_status_msg("Change", "%s made group %s." % (nick, str(visibility))))
        except ValueError:
            found = False

        return found

    def __try_change_volume__(self, session_id, nick, info, flag):
        found = True

        try:
            volume = groups.Volume(ord(flag))


            if info.volume == volume:
                self.broker.deliver(session_id, tld.encode_str("e", "Group is already %s." % str(volume)))
            else:
                info.volume = volume

                self.broker.to_channel(str(info), tld.encode_status_msg("Change", "%s made group %s." % (nick, str(volume))))
        except ValueError:
            found = False

        return found

    def __try_change_control__(self, session_id, moderator, info, flag):
        found = True

        try:
            control = groups.Control(ord(flag))

            if info.control == control:
                self.broker.deliver(session_id, tld.encode_str("e", "Group is already %s." % str(control)))
            else:
                info.control = control

                if control == groups.Control.PUBLIC:
                    self.broker.to_channel(str(info), tld.encode_status_msg("Change", "%s made group public." % moderator))
                else:
                    self.broker.to_channel(str(info), tld.encode_status_msg("Change", "%s is now %s." % (str(info), str(control))))

                info.clear_talkers()

                if control == groups.Control.RESTRICTED:
                    self.__make_restricted__(session_id, info)
                else:
                    info.clear_invitations()
        except ValueError:
            found = False

        return found

    def __make_restricted__(self, session_id, info):
        for sub_id in self.broker.get_subscribers(str(info)):
            sub_state = self.session.get(sub_id)

            self.broker.deliver(session_id, tld.encode_status_msg("FYI", "%s invited" % sub_state.nick))
            self.broker.deliver(sub_id, tld.encode_status_msg("FYI", "You are invited to group %s by default." % sub_state.nick))

            info.invite_nick(sub_state.nick, sub_state.authenticated)

    def status(self, session_id, msgid):
        info = self.__get_group__(session_id)
        logins = self.session.get_nicks()

        self.broker.deliver(session_id,
                            tld.encode_co_output("Name: %s Mod: %s (%s / %s / %s)"
                                                 % (str(info),
                                                    logins[info.moderator].nick if info.moderator else "(None)",
                                                    info.visibility,
                                                    info.control,
                                                    info.volume),
                                                 msgid))

        self.__send__wrapped__(session_id, "Nicks invited: ", info.invited_nicks, msgid)
        self.__send__wrapped__(session_id, "Addresses invited: ", info.invited_addresses, msgid)
        self.__send__wrapped__(session_id, "Talkers: ", info.talker_nicks, msgid)
        self.__send__wrapped__(session_id, "Talkers (addresses) ", info.talker_addresses, msgid)

    def __send__wrapped__(self, session_id, prefix, seq, msgid):
        line = ", ".join(seq)

        if line:
            parts = wrap(line, 64)

            self.broker.deliver(session_id, tld.encode_co_output("%s%s" % (prefix, parts[0]), msgid))

            for part in parts[1:]:
                self.broker.deliver(session_id, tld.encode_co_output("%s%s" % (" " * len(prefix), part), msgid))

    def invite(self, session_id, invitee, mode="n", quiet=None, registered=None):
        quiet = bool(quiet)
        registered = bool(registered)

        info = self.__get_group_if_can_moderate__(session_id)

        if not info.control == groups.Control.RESTRICTED:
            raise TldErrorException("The group isn't restricted.")

        state = self.session.get(session_id)
        loggedin_session = None

        if mode == "n":
            if registered:
                with self.db_connection.enter_scope() as scope:
                    if not self.nickdb.exists(scope, invitee):
                        raise TldErrorException("User not found.")

            loggedin_session = self.session.find_nick(invitee)

            if loggedin_session:
                self.broker.deliver(loggedin_session,
                                    tld.encode_status_msg("RSVP", "You are invited to group %s by %s." % (str(info), state.nick)))

                if registered:
                    loggedin_state = self.session.get(loggedin_session)

                    if not loggedin_state.authenticated:
                        self.broker.deliver(loggedin_session,
                                            tld.encode_status_msg("RSVP", "You need to be registered to enter group %s." % str(info)))
            elif not registered:
                raise TldErrorException("%s is not signed on." % invitee)

            info.invite_nick(invitee, registered)
        else:
            info.invite_address(invitee, registered)

        if not quiet:
            self.broker.deliver(session_id,
                                tld.encode_status_msg("FYI", "%s invited%s" % (invitee, " (registered only)" if registered else "")))

        self.groups.update(info)

    def cancel(self, session_id, invitee, mode="n", quiet=None):
        quiet = bool(quiet)

        info = self.__get_group_if_can_moderate__(session_id)

        if not info.control == groups.Control.RESTRICTED:
            raise TldErrorException("The group isn't restricted.")

        try:
            if mode == "n":
                info.cancel_nick(invitee)
            else:
                info.cancel_address(invitee)
        except KeyError:
            raise TldErrorException("%s isn't invited." % invitee)

        if not quiet:
            self.broker.deliver(session_id, tld.encode_status_msg("FYI", "%s cancelled." % invitee))

        self.groups.update(info)

    def talk(self, session_id, talker, mode="n", delete=None, quiet=None, registered=None):
        quiet = bool(quiet)
        delete = bool(delete)
        registered = bool(registered)

        info = self.__get_group_if_can_moderate__(session_id)

        if not info.control == groups.Control.CONTROLLED:
            raise TldErrorException("The group isn't controlled.")

        if delete:
            try:
                if mode == "n":
                    info.mute_nick(talker)
                else:
                    info.mute_address(talker)
            except KeyError:
                raise TldErrorException("%s isn't allowed to talk." % talker)

            if not quiet:
                self.broker.deliver(session_id, tld.encode_status_msg("FYI", "%s removed from talker list." % talker))
        else:
            loggedin_session = None

            if mode == "n":
                if registered:
                    with self.db_connection.enter_scope() as scope:
                        if not self.nickdb.exists(scope, talker):
                            raise TldErrorException("User not found.")

                loggedin_session = self.session.find_nick(talker)

                if loggedin_session:
                    self.broker.deliver(loggedin_session, tld.encode_status_msg("RSVP", "You can now talk in group %s." % str(info)))

                    if registered:
                        loggedin_state = self.session.get(loggedin_session)

                        if not loggedin_state.authenticated:
                            self.broker.deliver(loggedin_session,
                                                tld.encode_status_msg("RSVP",
                                                                      "You need to be registered to talk in group %s." % str(info)))
                elif not registered:
                    raise TldErrorException("%s is not signed on." % talker)

                info.unmute_nick(talker, registered)
            else:
                info.unmute_address(talker, registered)

            if not quiet:
                self.broker.deliver(session_id,
                                    tld.encode_status_msg("FYI",
                                                          "%s%s can now talk." % (talker, " (registered only)" if registered else "")))

        self.groups.update(info)

    def boot(self, session_id, nick):
        info = self.__get_group_if_can_moderate__(session_id)

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session == session_id:
            raise TldErrorException("You cannot boot yourself.")

        if not loggedin_session:
            raise TldErrorException("%s is not in your group." % nick)

        state = self.session.get(session_id)
        loggedin_state = self.session.get(loggedin_session)

        if loggedin_state.authenticated:
            with self.db_connection.enter_scope() as scope:
                if self.nickdb.is_admin(scope, nick):
                    self.broker.deliver(loggedin_session, tld.encode_status_msg("Boot", "%s tried to boot you." % state.nick))

                    raise TldErrorException("You cannot boot an admin!")

        try:
            info.cancel_nick(loggedin_state.nick)

            self.broker.deliver(session_id, tld.encode_status_msg("FYI", "%s cancelled." % nick))
        except KeyError: pass

        try:
            info.mute_nick(loggedin_state.nick)

            self.broker.deliver(session_id, tld.encode_status_msg("FYI", "%s removed from talker list." % nick))
        except KeyError: pass

        self.broker.to_channel(info.key, tld.encode_status_msg("Boot", "%s was booted." % nick))
        self.broker.deliver(loggedin_session, tld.encode_status_msg("Boot", "%s booted you." % state.nick))

        INSTANCE(UserSession).join(loggedin_session, config.BOOT_GROUP)

    def __get_group__(self, session_id):
        state = self.session.get(session_id)

        if not state.group:
            raise TldErrorException("Login required.")

        return self.groups.get(state.group)

    def __get_group_if_can_moderate__(self, session_id):
        info = self.__get_group__(session_id)

        if self.__is_protected_group__(info.key):
            raise TldErrorException("You aren't the moderator.")

        if info.control != groups.Control.PUBLIC:
            log.debug("Group's moderator: %s", info.moderator)

            if info.moderator != session_id:
                log.debug("User isn't moderator, testing administrative privileges.")

                with self.db_connection.enter_scope() as scope:
                    state = self.session.get(session_id)

                    if not self.nickdb.exists(scope, state.nick) or not self.nickdb.is_admin(scope, state.nick):
                        raise TldErrorException("You aren't the moderator.")

        return info

    @staticmethod
    def __is_protected_group__(name):
        return name.lower() in [p.lower() for p in [config.DEFAULT_GROUP, config.IDLE_GROUP, config.BOOT_GROUP]]

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
                log.info("Creating new user profile for '%s'.", state.nick)

                if not validate.is_valid_password(password):
                    raise TldStatusException("Register",
                                             "Password format not valid. Passwords length must be between %d and %d characters."
                                             % (validate.PASSWORD_MIN, validate.PASSWORD_MAX))

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
                    self.broker.deliver(session_id,
                                        tld.encode_status_msg("Message", "You have %d message%s." % (count, "" if count == 1 else "s")))

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
        state = self.session.get(session_id)

        if not state.authenticated:
            raise TldErrorException("You must be registered to change your security.")

        if not self.__validate_field__(field, text):
            raise TldResponseException("Invalid attribute.",
                                       tld.encode_co_output("'%s' format not valid." % self.__map_field__(field), msgid))

        with self.db_connection.enter_scope() as scope:
            details = self.nickdb.lookup(scope, state.nick)

            setattr(details, field, text)

            self.nickdb.update(scope, state.nick, details)

            self.broker.deliver(session_id, tld.encode_co_output("%s set to '%s'" % (self.__map_field__(field), text), msgid))

            scope.complete()

    @staticmethod
    def __map_field__(field):
        name = None

        if field == "real_name":
            name = "Real Name"
        elif field == "address":
            name = "Address"
        elif field == "phone":
            name = "Phone Number"
        elif field == "email":
            name = "E-Mail"
        elif field == "text":
            name = "Message text"
        elif field == "www":
            name = "WWW"
        else:
            raise ValueError

        return name

    @staticmethod
    def __validate_field__(field, text):
        valid = False

        if field == "real_name":
            valid = validate.is_valid_realname(text)
        elif field == "address":
            valid = validate.is_valid_address(text)
        elif field == "phone":
            valid = validate.is_valid_phone(text)
        elif field == "email":
            valid = validate.is_valid_email(text)
        elif field == "text":
            valid = validate.is_valid_text(text)
        elif field == "www":
            valid = validate.is_valid_www(text)
        else:
            raise ValueError

        return valid

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
        if not nick:
            raise TldErrorException("Nickname to lookup not specified.")

        with self.db_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, nick):
                raise TldErrorException("%s is not in the database." % nick)

            signon = self.nickdb.get_signon(scope, nick)
            signoff = self.nickdb.get_signoff(scope, nick)

            details = self.nickdb.lookup(scope, nick)

        login = idle = away = None

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session:
            loggedin_state = self.session.get(loggedin_session)

            login = loggedin_state.address
            idle = loggedin_state.t_recv.elapsed_str()

            if loggedin_state.away:
                away = "%s (since %s)" % (loggedin_state.away, loggedin_state.t_away.elapsed_str())

        msgs = bytearray()

        def display_value(text):
            if not text:
                text = "(None)"

            return text

        msgs.extend(tld.encode_co_output("Nickname:       %-24s Address:      %s"
                                         % (nick, display_value(login)),
                                         msgid))

        msgs.extend(tld.encode_co_output("Phone Number:   %-24s Real Name:    %s"
                                         % (display_value(details.phone), display_value(details.real_name)),
                                         msgid))

        msgs.extend(tld.encode_co_output("Last signon:    %-24s Last signoff: %s"
                                         % (display_value(signon), display_value(signoff)),
                                         msgid))

        if idle:
            msgs.extend(tld.encode_co_output("Idle:           %s" % idle, msgid))

        if away:
            msgs.extend(tld.encode_co_output("Away:           %s" % away, msgid))

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
            raise TldErrorException("Message text not valid. Length has be between %d and %d characters."
                                    % (validate.MESSAGE_MIN, validate.MESSAGE_MAX))

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
                self.broker.deliver(loggedin_session,
                                    tld.encode_status_msg("Message", "You have %d message%s." % (count, "" if count == 1 else "s")))

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
                self.broker.deliver(session_id, tld.encode_co_output("Message left at %s (UTC)" % msg.date, msgid))

                e = tld.Encoder("c")

                e.add_field_str(msg.sender, append_null=False)
                e.add_field_str(msg.text, append_null=True)

                self.broker.deliver(session_id, e.encode())

                self.nickdb.delete_message(scope, msg.uuid)

            scope.complete()

class Beep(Injected):
    def __init__(self):
        super().__init__()

    def beep(self, session_id, receiver):
        loggedin_session = self.session.find_nick(receiver)

        if not loggedin_session:
            raise TldErrorException("%s not signed on." % receiver)

        loggedin_state = self.session.get(loggedin_session)

        state = self.session.get(session_id)

        if loggedin_state.beep != session.BeepMode.ON:
            if loggedin_state.beep == session.BeepMode.VERBOSE:
                self.broker.deliver(loggedin_session,
                                    tld.encode_status_msg("No-Beep", "%s attempted (and failed) to beep you" % state.nick))

            raise TldStatusException("Beep", "User has nobeep enabled.")

        self.broker.deliver(loggedin_session, tld.encode_str("k", state.nick))

        if loggedin_state.away:
            if not self.away_table.is_alive(session_id, receiver):
                self.broker.deliver(session_id,
                                    tld.encode_status_msg("Away",
                                                          "%s (since %s)" % (loggedin_state.away, loggedin_state.t_away.elapsed_str())))

                self.away_table.set_alive(session_id, receiver, config.AWAY_MSG_TIMEOUT)

    def set_mode(self, session_id, mode):
        if not mode in ["on", "off", "verbose"]:
            raise TldErrorException("Usage: /nobeep on/off/verbose")

        real_mode = session.BeepMode.ON

        if mode == "on":
            real_mode = session.BeepMode.OFF
        elif mode == "verbose":
            real_mode = session.BeepMode.VERBOSE

        self.session.update(session_id, beep=real_mode)

        self.broker.deliver(session_id, tld.encode_status_msg("No-Beep", "No-Beep %s" % mode))

class Away(Injected):
    def __init__(self):
        super().__init__()

    def away(self, session_id, text):
        state = self.session.get(session_id)

        if text:
            if len(text) > 64:
                text = "%s..." % text[:61]

            self.session.update(session_id, away=text, t_away=Timer())

            self.broker.deliver(session_id, tld.encode_status_msg("Away", "Away message set to \"%s\"." % text))
        elif state.away:
            self.broker.deliver(session_id,
                                tld.encode_status_msg("Away",
                                                      "Away message is set to \"%s\" (since %s)."
                                                      % (state.away, state.t_away.elapsed_str())))
        else:
            self.broker.deliver(session_id, tld.encode_status_msg("Away", "Away message is not set."))

    def noaway(self, session_id):
        state = self.session.get(session_id)

        if not state.away:
            raise TldStatusException("Away", "No away message set!")

        self.session.update(session_id, away=None, t_away=None)

        self.broker.deliver(session_id, tld.encode_status_msg("Away", "Away message unset."))

class Motd(Injected):
    def __init__(self):
        super().__init__()

    def receive(self, session_id, msgid=""):
        try:
            for line in motd.load():
                self.broker.deliver(session_id, tld.encode_co_output(line, msgid))

        except Exception as ex:
            log.warn(str(ex))
