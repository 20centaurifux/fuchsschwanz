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
import database, nickdb, tld, validate
import re, sys, secrets
from exception import TldStatusException, TldErrorException
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

class UserSession(Injected):
    def __init__(self):
        super().__init__()

    def login(self, session_id, loginid, nick, password, group):
        log.debug("User login: loginid='%s', nick='%s', password='%s'" % (loginid, nick, password))

        if not validate.is_valid_loginid(loginid):
            raise TldErrorException("loginid is invalid.")

        if not validate.is_valid_nick(nick):
            raise TldErrorException("nick is invalid.")

        if not self.__try_login_unsecure__(session_id, loginid, nick):
            if len(password) == 0:
                self.__login_no_password__(session_id, loginid, nick)
            else:
                self.__login_password__(session_id, loginid, nick, password)

            self.__set_lastlogin__(session_id)

        if group == "":
            group = config.DEFAULT_GROUP

        self.join(session_id, group)

    def __try_login_unsecure__(self, session_id, loginid, nick):
        log.debug("Testing unsecure authentication.")

        authenticated = False

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                log.debug("Nick found, testing security level.")

                if not self.nickdb.is_secure(scope, nick):
                    log.debug("Nick allows auto-register.")

                    lastlogin = self.nickdb.get_lastlogin(scope, nick)

                    if not lastlogin is None:
                        log.debug("Last login: %s@%s" % (lastlogin[0], lastlogin[1]))

                        state = self.session.get(session_id)

                        authenticated = (lastlogin[0] == loginid and lastlogin[1] == state.host)
                    else:
                       log.debug("First login, skipping auto-register.")
                else:
                    log.debug("Nick doesn't allow auto-register.")
        
        if authenticated:
            self.broker.deliver(session_id, tld.encode_status_msg("Register", "Nick registered"))

            existing_session = self.session.find_nick(nick)

            if not existing_session is None:
                self.auto_rename(existing_session)

            self.session.update(session_id, loginid=loginid, nick=nick, authenticated=True)

            self.broker.deliver(session_id, tld.encode_empty_cmd("a"))
            self.broker.assign_nick(session_id, nick)

        return authenticated

    def __login_no_password__(self, session_id, loginid, nick):
        log.debug("No password given, skipping authentication.")

        existing_session = self.session.find_nick(nick)

        if not existing_session is None:
            log.debug("'%s' already logged in, aborting login." % nick)

            raise TldStatusException("Register", "Nick already in use.")

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                if self.nickdb.is_admin(scope, nick):
                    raise TldErrorException("Nickname already in use.")
                else:
                    self.broker.deliver(session_id, tld.encode_status_msg("Register", "Send password to authenticate your nickname."))
            else:
                self.broker.deliver(session_id, tld.encode_status_msg("No-Pass", "Your nickname does not have a password."))
                self.broker.deliver(session_id, tld.encode_status_msg("No-Pass", "For help type /m server ?"))

        self.broker.deliver(session_id, tld.encode_empty_cmd("a"))
        self.broker.assign_nick(session_id, nick)

        self.session.update(session_id, loginid=loginid, nick=nick, authenticated=False)

    def __login_password__(self, session_id, loginid, nick, password):
        log.debug("Password set, trying to authenticate '%s'." % nick)

        authenticated = False
        is_admin = False

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, nick):
                authenticated = self.nickdb.check_password(scope, nick, password)
                is_admin = self.nickdb.is_admin(scope, nick)

        if authenticated:
            log.debug("Password verified.")

            self.broker.deliver(session_id, tld.encode_status_msg("Register", "Nick registered"))
        else:
            log.debug("Password is invalid.")

            self.broker.deliver(session_id, tld.encode_str("e", "Authorization failure"))

            if is_admin:
                raise TldErrorException("Nickname already in use.")

        existing_session = self.session.find_nick(nick)

        if not existing_session is None and not authenticated:
            log.debug("'%s' already logged in, aborting login." % nick)

            raise TldStatusException("Register", "Nick already in use.")

        if not existing_session is None:
            self.auto_rename(existing_session)

        self.session.update(session_id, loginid=loginid, nick=nick, authenticated=authenticated)

        self.broker.deliver(session_id, tld.encode_empty_cmd("a"))
        self.broker.assign_nick(session_id, nick)

    def __set_lastlogin__(self, session_id):
        state = self.session.get(session_id)

        if state.authenticated:
            with self.db_connection.enter_scope() as scope:
                if self.nickdb.exists(scope, state.nick):
                    self.nickdb.set_lastlogin(scope, state.nick, state.loginid, state.host)

                    scope.complete()

    def auto_rename(self, session_id):
        state = self.session.get(session_id)

        prefix, _ = self.__split_name__(state.nick)
        new_nick = self.__guess_nick__(prefix, 1)

        if new_nick is None:
            prefix, _ = self.__split_name__(state.loginid)
            new_nick = self.__guess_nick__(prefix, 1)

        while new_nick is None:
            new_nick = self.__guess_nick__(secrets.token_hex(8), 1)

        self.rename(session_id, new_nick)

    def __split_name__(self, name):
        prefix = name
        suffix = 1

        m = re.match("(.*)-([0-9]+)$", name)

        if not m is None:
            prefix = m.group(1)
            suffix = int(m.group(2))

        return prefix, suffix

    def __guess_nick__(self, name, suffix):
        nick = "%s-%d" % (name, suffix)
        guessed = None

        if validate.is_valid_nick(nick):
            if self.session.find_nick(nick) is None:
                guessed = nick
            elif suffix != sys.maxsize:
                guessed = self.__guess_nick__(name, suffix + 1)

        return guessed

    def rename(self, session_id, nick):
        if not validate.is_valid_nick(nick):
            raise TldErrorException("Nick is invalid.")

        state = self.session.get(session_id)

        if not state.nick is None:
            log.info("Renaming '%s' to '%s'" % (state.nick, nick))

            if self.session.find_nick(nick):
                raise TldErrorException("Nick already in use.")

            if not state.group is None:
                log.debug("Renaming '%s' to '%s' in channel '%s'." % (state.nick, nick, state.group))

                self.broker.to_channel(state.group, tld.encode_status_msg("Name", "%s changed nickname to %s" % (state.nick, nick)))

                if self.groups.get(state.group).moderator == session_id:
                    self.broker.to_channel(state.group, tld.encode_status_msg("Pass", "%s is now mod." % nick))

            self.broker.unassign_nick(state.nick)
            self.broker.assign_nick(session_id, nick)

            self.session.update(session_id, nick=nick, authenticated=False)

            with self.db_connection.enter_scope() as scope:
                if self.nickdb.exists(scope, nick):
                    self.broker.deliver(session_id, tld.encode_status_msg("Register", "Send password to authenticate your nickname."))
                else:
                    self.broker.deliver(session_id, tld.encode_status_msg("No-Pass", "To register your nickname type /m server p password"))

    def sign_off(self, session_id):
        state = self.session.get(session_id)

        if not state.nick is None:
            log.debug("Dropping session: '%s'" % session_id)

            if not state.group is None:
                log.debug("Removing '%s' from channel '%s'." % (state.nick, state.group))

                if self.broker.part(session_id, state.group):
                    info = self.groups.get(state.group)

                    if info.volume != groups.Volume.QUIET:
                        self.broker.to_channel_from(session_id,
                                                    state.group,
                                                    tld.encode_status_msg("Sign-off", "%s (%s@%s) has signed off." % (state.nick, state.loginid, state.host)))

                        if info.moderator == session_id:
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
            self.broker.unassign_nick(state.nick)

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
            category = "Sign-on" if old_group is None else "Arrive"
            self.broker.to_channel_from(session_id,
                                        group,
                                        tld.encode_status_msg(category, "%s (%s@%s) entered group" % (state.nick, state.loginid, state.host)))

        self.session.update(session_id, group=group)

        if not old_group is None:
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

            if session_id is None:
                raise TldErrorException("User not found.")

            state = self.session.get(session_id)

            if state.group is None or self.groups.get(state.group).visibility != groups.Visibility.VISIBLE:
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

class OpenMessage(Injected):
    def __init__(self):
        super().__init__()

    def send(self, session_id, message):
        state = self.session.get(session_id)
        
        if not state.group is None:
            info = self.groups.get(state.group)

            if info.volume == groups.Volume.QUIET:
                raise TldErrorException("Open messages are not permitted in quiet groups.")

            e = tld.Encoder("b")

            e.add_field_str(state.nick, append_null=True)
            e.add_field_str(message, append_null=True)

            if self.broker.to_channel_from(session_id, state.group, e.encode()) == 0:
                raise TldErrorException("No one else in group!")
        else:
            log.warning("Cannot send open message, session '%s' not logged in." % session_id)

            raise TldErrorException("Login required.")

class Ping(Injected):
    def __init__(self):
        super().__init__()

    def ping(self, session_id, message_id=""):
        state = self.session.get(session_id)
        
        if not state.group is None:
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

        if not info.moderator is None and info.moderator != session_id:
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

        if state.nick is None:
            raise TldErrorException("Login required.")

        with self.db_connection.enter_scope() as scope:
            authenticated = False

            if self.nickdb.exists(scope, state.nick):
                log.debug("Nick found, validating password.")

                if not self.nickdb.check_password(scope, state.nick, password):
                    raise TldErrorException("Authorization failure")
                
                authenticated = True
            else:
                log.info("Creating new user profile for '%s'." % state.nick)

                if not validate.is_valid_password(password):
                    raise TldStatusException("Register", "Password format not valid.")

                self.nickdb.create(scope, state.nick)
                self.nickdb.set_secure(scope, state.nick, True)
                self.nickdb.set_admin(scope, state.nick, False)
                self.nickdb.set_password(scope, state.nick, password)

                authenticated = True

            if authenticated:
                log.debug("Authentication succeeded.")

                self.nickdb.set_lastlogin(scope, state.nick, state.loginid, state.host)

                self.session.update(session_id, authenticated=True)

                self.broker.deliver(session_id, tld.encode_status_msg("Register", "Nick registered"))

                scope.complete()
