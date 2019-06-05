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
from datetime import datetime
import secrets
import re
from actions import Injected, ACTION
from actions.motd import Motd
from actions.registration import Registration
from actions.notification import Notify
from actions.group import Group
import core
import group
import validate
import ltd
from textutils import hide_password
from exception import LtdErrorException, LtdStatusException

class UserSession(Injected):
    def login(self, session_id, loginid, nick, password, group_name, status=""):
        self.log.debug("User login: loginid=%s, nick=%s, password=%s", loginid, nick, hide_password(password))

        if not validate.is_valid_loginid(loginid):
            raise LtdErrorException("loginid must consist of at least %d and at most %d alphabetic characters."
                                    % (validate.LOGINID_MIN, validate.LOGINID_MAX))

        if not validate.is_valid_nick(nick):
            raise LtdErrorException("Nickname must consist of at least %d and at most %d alphanumeric characters."
                                    % (validate.NICK_MIN, validate.NICK_MAX))

        self.broker.deliver(session_id, ltd.encode_empty_cmd("a"))

        if nick == core.NICKSERV:
            raise LtdStatusException("Register", "Nick already in use.")

        ACTION(Motd).receive(session_id)

        registered = self.config.server_unsecure_login and self.__try_login_unsecure__(session_id, loginid, nick)

        if not registered:
            if not password:
                self.__login_no_password__(session_id, loginid, nick)
            else:
                registered = self.__login_password__(session_id, loginid, nick, password)

        self.session.update(session_id, signon=datetime.utcnow())

        registration = ACTION(Registration)

        if registered:
            registration.mark_registered(session_id)

        self.__test_connection_limit__(session_id)

        registration.notify_messagebox(session_id)

        if not group_name:
            group_name = core.DEFAULT_GROUP

        self.join(session_id, group_name, status)

        ACTION(Notify).notify_signon(session_id)

        with self.statsdb_connection.enter_scope() as scope:
            self.statsdb.add_signon(scope)
            self.statsdb.set_max_logins(scope, self.session.count_logins())

            scope.complete()

    def __try_login_unsecure__(self, session_id, loginid, nick):
        self.log.debug("Testing unsecure authentication.")

        registered = False

        with self.nickdb_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                self.log.debug("Nick found, testing security level.")

                if not self.nickdb.is_secure(scope, nick):
                    self.log.debug("Nick allows auto-register.")

                    if not self.nickdb.is_admin(scope, nick):
                        lastlogin = self.nickdb.get_lastlogin(scope, nick)

                        if lastlogin:
                            self.log.debug("Last login: %s@%s", lastlogin[0], lastlogin[1])

                            state = self.session.get(session_id)
                            registered = (lastlogin[0] == loginid and lastlogin[1] == state.host)
                        else:
                            self.log.debug("First login, skipping auto-register.")
                    else:
                        self.log.debug("Cannot auto-register administrative users.")
                else:
                    self.log.debug("Nick doesn't allow auto-register.")

        if registered:
            loggedin_session = self.session.find_nick(nick)

            if loggedin_session:
                self.__auto_rename__(loggedin_session)

            self.session.update(session_id, loginid=loginid, nick=nick)

        return registered

    def __login_no_password__(self, session_id, loginid, nick):
        self.log.debug("No password given, skipping authentication.")

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session:
            self.log.debug("%s already logged in, aborting login.", nick)

            raise LtdStatusException("Register", "Nick already in use.")

        with self.nickdb_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                if self.nickdb.is_admin(scope, nick):
                    raise LtdErrorException("You need a password to login as administrator.")

                self.broker.deliver(session_id, ltd.encode_status_msg("Register",
                                                                      "Send password to authenticate your nickname."))
            else:
                self.broker.deliver(session_id, ltd.encode_status_msg("No-Pass",
                                                                      "Your nickname does not have a password."))

                self.broker.deliver(session_id, ltd.encode_status_msg("No-Pass",
                                                                      "For help type /m server ?"))

        self.session.update(session_id, loginid=loginid, nick=nick)

    def __login_password__(self, session_id, loginid, nick, password):
        self.log.debug("Password set, trying to authenticate %s.", nick)

        registered = False
        is_admin = False

        with self.nickdb_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                registered = self.nickdb.check_password(scope, nick, password)
                is_admin = self.nickdb.is_admin(scope, nick)

            if not registered:
                self.log.debug("Password is invalid.")

                self.reputation.critical(session_id)

                self.broker.deliver(session_id, ltd.encode_str("e", "Authorization failure."))
                self.broker.deliver(session_id, ltd.encode_status_msg("Register",
                                                                      "Send password to authenticate your nickname."))

                if is_admin:
                    raise LtdErrorException("You need a password to login as administrator.")

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session and not registered:
            self.log.debug("%s already logged in, aborting login.", nick)

            raise LtdStatusException("Register", "Nick already in use.")

        if loggedin_session:
            self.__auto_rename__(loggedin_session)

        self.session.update(session_id, loginid=loginid, nick=nick)

        return registered

    def __auto_rename__(self, session_id):
        state = self.session.get(session_id)

        self.log.debug("Renaming logged in user: %s", state.nick)

        prefix, _ = self.__split_name__(state.nick)
        new_nick = self.__guess_nick__(prefix, 1)

        if not new_nick:
            prefix, _ = self.__split_name__(state.loginid)
            new_nick = self.__guess_nick__(prefix, 1)

        while not new_nick:
            new_nick = secrets.token_hex(6)

            self.log.debug("Testing guessed nickname: %s" % new_nick)

            if self.session.find_nick(new_nick):
                new_nick = None

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

        self.log.debug("Testing guessed nickname: %s" % nick)

        if validate.is_valid_nick(nick):
            if not self.session.find_nick(nick):
                guessed = nick
            elif suffix != 10:
                guessed = self.__guess_nick__(name, suffix + 1)

        return guessed

    def __test_connection_limit__(self, session_id):
        if self.session.count_logins() > self.config.server_max_logins:
            self.log.warning("Connection limit (%d) reached.", self.config.server_max_logins)

            state = self.session.get(session_id)

            if state.authenticated:
                with self.nickdb_connection.enter_scope() as scope:
                    if not self.nickdb.is_admin(scope, state.nick):
                        raise LtdErrorException("Connection limit reached.")
            else:
                raise LtdErrorException("Connection limit reached.")

    def rename(self, session_id, nick):
        if not validate.is_valid_nick(nick):
            raise LtdErrorException("Nickname is invalid.")

        state = self.session.get(session_id)

        old_nick = state.nick
        was_authenticated = False

        if old_nick:
            self.log.debug("Renaming %s to %s.", old_nick, nick)

            was_authenticated = state.authenticated

            if self.session.find_nick(nick):
                self.reputation.warning(session_id)

                raise LtdErrorException("Nick already in use.")

            if state.group:
                self.log.debug("Renaming %s to %s in channel %s.", old_nick, nick, state.group)

                self.broker.to_channel(state.group,
                                       ltd.encode_status_msg("Name",
                                                             "%s changed nickname to %s." % (old_nick, nick)))

                if self.groups.get(state.group).moderator == session_id:
                    self.broker.to_channel(state.group,
                                           ltd.encode_status_msg("Pass",
                                                                 "%s is now mod." % nick))

            self.session.update(session_id, nick=nick, authenticated=False)

            registered = False
            is_admin = False

            with self.nickdb_connection.enter_scope() as scope:
                if was_authenticated and self.nickdb.exists(scope, old_nick):
                    self.nickdb.set_signoff(scope, old_nick)

                if self.nickdb.exists(scope, nick):
                    is_admin = self.nickdb.is_admin(scope, nick)

                    if self.nickdb.is_secure(scope, nick):
                        self.broker.deliver(session_id,
                                            ltd.encode_status_msg("Register",
                                                                  "Send password to authenticate your nickname."))
                    else:
                        self.log.debug("Nick not secure, trying to register automatically.")

                        lastlogin = self.nickdb.get_lastlogin(scope, nick)

                        if lastlogin:
                            self.log.debug("Last login: %s@%s", lastlogin[0], lastlogin[1])

                            registered = (lastlogin[0] == state.loginid and lastlogin[1] == state.host)
                else:
                    self.broker.deliver(session_id,
                                        ltd.encode_status_msg("No-Pass",
                                                              "To register your nickname type /m server p password."))

            registration = ACTION(Registration)

            if registered:
                registration.mark_registered(session_id)
            elif is_admin:
                self.broker.deliver(session_id,
                                    ltd.encode_str("e",
                                                   "Registration failed, administrative account requires a password."))

                self.reputation.fatal(session_id)

                self.__auto_rename__(session_id)
            else:
                registration.notify_messagebox(session_id)
                self.session.update(session_id, signon=datetime.utcnow())

    def sign_off(self, session_id):
        state = self.session.get(session_id)

        if state.nick:
            self.log.debug("Dropping session: %s", session_id)

            if state.authenticated:
                with self.nickdb_connection.enter_scope() as scope:
                    self.nickdb.set_signoff(scope, state.nick)

                    scope.complete()

            ACTION(Notify).notify_signoff(session_id)

            if state.group:
                self.log.debug("Removing %s from channel %s.", state.nick, state.group)

                if self.broker.part(session_id, state.group):
                    info = self.groups.get(state.group)

                    if info.volume != group.Volume.QUIET:
                        self.broker.to_channel_from(session_id,
                                                    state.group,
                                                    ltd.encode_status_msg("Sign-off",
                                                                          "%s (%s) has signed off." % (state.nick, state.address)))

                    self.drop_moderator(session_id, "Sign-off", "Your moderator signed off.")
                else:
                    self.groups.delete(state.group)

            self.log.debug("Removing nick %s from session %s.", state.nick, session_id)

            self.session.update(session_id, nick=None, authenticated=False)

    def idle_mod(self, session_id):
        self.broker.deliver(session_id, ltd.encode_status_msg("Idle-Mod", "You were booted."))

        self.join(session_id, core.BOOT_GROUP)
        self.drop_moderator(session_id, "Idle-Mod", "Your group moderator idled away.")

        with self.statsdb_connection.enter_scope() as scope:
            self.statsdb.add_idlemod(scope)

            scope.complete()

    def idle_boot(self, session_id):
        self.broker.deliver(session_id, ltd.encode_status_msg("Idle-Boot", "You were booted."))

        self.join(session_id, core.BOOT_GROUP)
        self.drop_moderator(session_id, "Idle-Boot", "Your group moderator idled away.")

        with self.statsdb_connection.enter_scope() as scope:
            self.statsdb.add_idleboot(scope)

            scope.complete()

    def drop_moderator(self, session_id, category, message):
        for info in self.groups.get_groups():
            if info.moderator == session_id:
                if info.volume != group.Volume.QUIET:
                    self.broker.to_channel_from(session_id, info.key, ltd.encode_status_msg(category, message))

                new_mod = None
                min_elapsed = -1

                for sub_id in self.broker.get_subscribers(info.key):
                    sub_state = self.session.get(sub_id)
                    elapsed = sub_state.t_recv.elapsed()

                    self.log.debug("Found subscriber: %s, elapsed milliseconds: %f", sub_state.nick, elapsed)

                    if not sub_state.away and (min_elapsed == -1 or elapsed < min_elapsed):
                        min_elapsed = elapsed
                        new_mod = [sub_id, sub_state.nick]

                if new_mod:
                    self.log.debug("New mod: %s", new_mod[1])

                    self.broker.to_channel(info.key, ltd.encode_status_msg("Pass", "%s is now mod." % new_mod[1]))

                    info.moderator = new_mod[0]
                else:
                    self.log.debug("No new moderator found.")

                    self.broker.to_channel(str(info), ltd.encode_status_msg("Change", "Group is now public."))

                    info.control = group.Control.PUBLIC
                    info.moderator = None
                    info.clear_talkers()
                    info.clear_invitations()

                self.groups.update(info)

    def join(self, session_id, group_name, status=""):
        state = self.session.get(session_id)

        self.log.debug("%s joins group %s.", state.nick, group_name)

        old_group = state.group
        new_status = None

        group_name = self.__resolve_user_group_name__(group_name)
        visibility, group_name = self.__extract_visibility_from_groupname__(group_name)

        if not validate.is_valid_group(group_name):
            raise LtdErrorException("Invalid group name.")

        if old_group == group_name:
            raise LtdErrorException("You are already in that group.")

        info = self.groups.get(group_name)

        if info.group_limit > 0 and len(self.broker.get_subscribers(str(info))) >= info.group_limit:
            with self.nickdb_connection.enter_scope() as scope:
                is_admin = self.nickdb.exists(scope, state.nick) and self.nickdb.is_admin(scope, state.nick)

                if info.moderator != session_id and not is_admin:
                    if info.volume == group.Volume.LOUD:
                        self.broker.to_channel(str(info),
                                               ltd.encode_status_msg("Probe", "%s tried to enter the group, but it's full." % state.nick))

                    raise LtdErrorException("Group is full.")

        if info.control == group.Control.RESTRICTED:
            if (info.moderator != session_id
                    and not (info.nick_invited(state.nick, state.authenticated)
                             or info.address_invited(state.loginid, state.ip, state.host, state.authenticated))):
                if info.volume == group.Volume.LOUD:
                    moderator_state = self.session.get(info.moderator)

                    hushed = moderator_state.hushlist.nick_private_hushed(state.nick)

                    if not hushed:
                        hushed = moderator_state.hushlist.site_private_hushed(state.address)

                    if not hushed:
                        self.broker.deliver(info.moderator,
                                            ltd.encode_status_msg("Probe",
                                                                  "%s tried to enter group %s." % (state.nick, group_name)))
                self.reputation.warning(session_id)

                raise LtdErrorException("%s is restricted." % group_name)

            self.broker.join(session_id, group_name)
        else:
            if self.broker.join(session_id, group_name):
                self.log.debug("Group %s created.", group_name)

                info.visibility = visibility

                if group_name == core.DEFAULT_GROUP:
                    info.control = group.Control.PUBLIC
                    info.topic = core.DEFAULT_TOPIC
                    info.idle_mod = 0
                elif group_name == core.IDLE_GROUP:
                    info.control = group.Control.PUBLIC
                    info.visibility = group.Visibility.VISIBLE
                    info.volume = group.Volume.QUIET
                    info.topic = core.IDLE_TOPIC
                    info.idle_mod = 0
                    info.idle_boot = 0
                elif group_name == core.BOOT_GROUP:
                    info.control = group.Control.PUBLIC
                    info.visibility = group.Visibility.VISIBLE
                    info.volume = group.Volume.LOUD
                    info.topic = core.BOOT_TOPIC
                    info.idle_mod = 0
                    info.idle_boot = 0
                else:
                    info.control = group.Control.MODERATED
                    info.moderator = session_id
                    info.idle_mod = self.config.timeouts_idle_mod
                    info.idle_boot = self.config.timeouts_idle_boot
                    new_status = status

                self.groups.update(info)

        msg = "You are now in group %s" % group_name

        if info.moderator == session_id:
            msg += " as moderator"

        msg += "."

        self.broker.deliver(session_id, ltd.encode_status_msg("Status", msg))

        if info.volume != group.Volume.QUIET:
            category = "Sign-on" if not old_group else "Arrive"
            self.broker.to_channel_from(session_id,
                                        group_name,
                                        ltd.encode_status_msg(category,
                                                              "%s (%s) entered group." % (state.nick, state.address)))

        self.session.update(session_id, group=info.key)

        if new_status:
            ACTION(Group).change_status(session_id, new_status)

        with self.statsdb_connection.enter_scope() as scope:
            self.statsdb.set_max_groups(scope, len(self.groups))

            scope.complete()

        if old_group:
            info = self.groups.get(old_group)

            self.log.debug("Removing %s from channel %s.", state.nick, old_group)

            if self.broker.part(session_id, old_group):
                if info.volume != group.Volume.QUIET:
                    self.broker.to_channel_from(session_id,
                                                old_group,
                                                ltd.encode_status_msg("Depart",
                                                                      "%s (%s) just left." % (state.nick, state.address)))
            else:
                self.groups.delete(old_group)

    def __resolve_user_group_name__(self, name):
        if name.startswith("@"):
            session_id = self.session.find_nick(name[1:])

            if not session_id:
                raise LtdErrorException("User not found.")

            state = self.session.get(session_id)

            if not state.group or self.groups.get(state.group).visibility != group.Visibility.VISIBLE:
                raise LtdErrorException("User not found.")

            name = state.group

        return name

    @staticmethod
    def __extract_visibility_from_groupname__(name):
        visibility = group.Visibility.VISIBLE

        if name.startswith(".."):
            visibility = group.Visibility.INVISIBLE
            name = name[2:]
        elif name.startswith("."):
            visibility = group.Visibility.SECRET
            name = name[1:]

        return visibility, name

    def whereis(self, session_id, nick, msgid=""):
        loggedin_session = self.session.find_nick(nick)

        if loggedin_session:
            state = self.session.get(loggedin_session)

            self.broker.deliver(session_id, ltd.encode_co_output("%-16s %s (%s)" % (nick, state.host, state.ip), msgid))
        else:
            self.broker.deliver(session_id, ltd.encode_co_output("User not found.", msgid))
