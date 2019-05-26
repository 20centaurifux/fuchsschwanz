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
from textwrap import wrap
from actions import Injected, ACTION
import actions.usersession
import core
import tld
import validate
import group
from exception import TldErrorException

class Group(Injected):
    def set_topic(self, session_id, topic):
        info = self.__get_group_if_can_moderate__(session_id)

        if not validate.is_valid_topic(topic):
            raise TldErrorException("Topic must consist of at least %d and at most %d characters."
                                    % (validate.TOP_MIN, validate.TOPIC_MAX))

        info.topic = topic

        self.groups.update(info)

        if info.volume != group.Volume.QUIET:
            self.broker.to_channel(str(info), tld.encode_status_msg("Topic",
                                                                    "%s changed the topic to \"%s\"" % (self.session.get(session_id).nick,
                                                                                                        topic)))

    def topic(self, session_id, msgid):
        info = self.__get_group__(session_id)

        if info.topic:
            self.broker.deliver(session_id, tld.encode_co_output("The topic is: '%s'." % info.topic, msgid))
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
            visibility = group.Visibility(ord(flag))

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
            volume = group.Volume(ord(flag))


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
            control = group.Control(ord(flag))

            if info.control == control:
                self.broker.deliver(session_id, tld.encode_str("e", "Group is already %s." % str(control)))
            else:
                info.control = control

                if control == group.Control.PUBLIC:
                    self.broker.to_channel(str(info), tld.encode_status_msg("Change", "%s made group public." % moderator))
                else:
                    self.broker.to_channel(str(info), tld.encode_status_msg("Change", "%s is now %s." % (str(info), str(control))))

                info.clear_talkers()

                if control == group.Control.RESTRICTED:
                    self.__make_restricted__(session_id, info)
                else:
                    info.clear_invitations()
        except ValueError:
            found = False

        return found

    def __make_restricted__(self, session_id, info):
        for sub_id in self.broker.get_subscribers(str(info)):
            sub_state = self.session.get(sub_id)

            self.broker.deliver(session_id, tld.encode_status_msg("FYI", "%s invited." % sub_state.nick))
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

        if not info.control == group.Control.RESTRICTED:
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
                                tld.encode_status_msg("FYI", "%s invited%s." % (invitee, " (registered only)" if registered else "")))

        self.groups.update(info)

    def cancel(self, session_id, invitee, mode="n", quiet=None):
        quiet = bool(quiet)

        info = self.__get_group_if_can_moderate__(session_id)

        if not info.control == group.Control.RESTRICTED:
            raise TldErrorException("The group isn't restricted.")

        try:
            if mode == "n":
                info.cancel_nick(invitee)

                loggedin_session = self.session.find_nick(invitee)

                if loggedin_session:
                    loggedin_state = self.session.get(loggedin_session)
                    state = self.session.get(session_id)

                    self.broker.deliver(loggedin_session,
                                        tld.encode_status_msg("FYI", "Invitation to group %s cancelled by %s." % (state.group, state.nick)))
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

        if not info.control == group.Control.CONTROLLED:
            raise TldErrorException("The group isn't controlled.")

        if delete:
            try:
                if mode == "n":
                    info.mute_nick(talker)

                    loggedin_session = self.session.find_nick(talker)

                    if loggedin_session:
                        state = self.session.get(session_id)

                        self.broker.deliver(loggedin_session,
                                            tld.encode_status_msg("FYI", "You cannot talk in group %s anymore." % state.group))
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
            raise TldErrorException("%s is not signed on." % nick)

        state = self.session.get(session_id)
        loggedin_state = self.session.get(loggedin_session)

        if loggedin_state.group.lower() != state.group.lower():
            raise TldErrorException("%s is not in your group." % nick)

        if loggedin_state.authenticated:
            with self.db_connection.enter_scope() as scope:
                if self.nickdb.is_admin(scope, nick):
                    self.broker.deliver(loggedin_session, tld.encode_status_msg("Boot", "%s tried to boot you." % state.nick))

                    self.reputation.fatal(session_id)

                    raise TldErrorException("You cannot boot an admin.")

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

        ACTION(actions.usersession.UserSession).join(loggedin_session, core.BOOT_GROUP)

    def pass_over(self, session_id, nick):
        info = self.__get_group_if_can_moderate__(session_id)

        loggedin_session = self.session.find_nick(nick)

        if not loggedin_session:
            raise TldErrorException("%s is not signed on." % nick)

        if info.moderator == loggedin_session:
            raise TldErrorException("You are already moderator.")

        loggedin_state = self.session.get(loggedin_session)

        if loggedin_state.nick.lower() == core.NICKSERV.lower():
            raise TldErrorException("Cannot pass to %s." % core.NICKSERV)

        info.moderator = loggedin_session

        self.groups.update(info)

        state = self.session.get(session_id)

        self.broker.deliver(loggedin_session, tld.encode_status_msg("Pass", "%s just passed moderation of group %s." % (state.nick, info.display_name)))

        if info.volume != group.Volume.QUIET:
            self.broker.to_channel(info.key, tld.encode_status_msg("Pass", "%s has passed moderation to %s." % (state.nick, loggedin_state.nick)))

    def relinquish(self, session_id):
        info = self.__get_group_if_can_moderate__(session_id)

        info.moderator = None

        state = self.session.get(session_id)

        if info.volume != group.Volume.QUIET:
            self.broker.to_channel(info.key, tld.encode_status_msg("Change", "%s just relinquished moderation." % state.nick))

        if info.control != group.Control.PUBLIC:
            info.control = group.Control.PUBLIC
            info.clear_talkers()
            info.clear_invitations()

            if info.volume != group.Volume.QUIET:
                self.broker.to_channel(info.key, tld.encode_status_msg("Change", "Group is now public."))

        self.groups.update(info)

    def __get_group__(self, session_id):
        state = self.session.get(session_id)

        return self.groups.get(state.group)

    def __get_group_if_can_moderate__(self, session_id):
        info = self.__get_group__(session_id)

        if self.__is_protected_group__(info.key):
            self.reputation.critical(session_id)

            raise TldErrorException("You aren't the moderator.")

        if info.control != group.Control.PUBLIC:
            self.log.debug("Group's moderator: %s", info.moderator)

            if info.moderator != session_id:
                self.log.debug("User isn't moderator, testing administrative privileges.")

                with self.db_connection.enter_scope() as scope:
                    state = self.session.get(session_id)

                    if not self.nickdb.exists(scope, state.nick) or not self.nickdb.is_admin(scope, state.nick):
                        self.reputation.critical(session_id)

                        raise TldErrorException("You aren't the moderator.")

        return info

    @staticmethod
    def __is_protected_group__(name):
        return name.lower() in [p.lower() for p in [core.DEFAULT_GROUP, core.IDLE_GROUP, core.BOOT_GROUP]]
