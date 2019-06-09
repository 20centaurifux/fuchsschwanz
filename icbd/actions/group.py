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
import ltd
import validate
import group
from exception import LtdErrorException

class Group(Injected):
    def set_topic(self, session_id, topic):
        info = self.__get_group_if_can_moderate__(session_id, allow_public=True)

        if not validate.is_valid_topic(topic):
            raise LtdErrorException("Topic must consist of at least %d and at most %d characters."
                                    % (validate.TOPIC_MIN, validate.TOPIC_MAX))

        info.topic = topic

        self.groups.update(info)

        if info.volume != group.Volume.QUIET:
            self.broker.to_channel(str(info), ltd.encode_status_msg("Topic",
                                                                    "%s changed the topic to \"%s\"" % (self.session.get(session_id).nick,
                                                                                                        topic)))

    def topic(self, session_id, msgid):
        info = self.__get_group__(session_id)

        if info.topic:
            self.broker.deliver(session_id, ltd.encode_co_output("The topic is: %s" % info.topic, msgid))
        else:
            self.broker.deliver(session_id, ltd.encode_co_output("The topic is not set.", msgid))

    def change_status(self, session_id, opts):
        state = self.session.get(session_id)
        info = self.__get_group_if_can_moderate__(session_id)

        opt = None
        arg_required = False

        for word in [f.strip() for f in opts.split(" ")]:
            if arg_required:
                arg = word

                if opt == "b":
                    if arg.isdigit():
                        minutes = int(arg)

                        if minutes == 0 or (minutes >= core.MIN_IDLE_BOOT and minutes <= core.MAX_IDLE_BOOT):
                            self.__change_idle_boot__(state.nick, info, minutes)
                        else:
                            self.broker.deliver(session_id,
                                                ltd.encode_str("e",
                                                               "Idle-Boot must be between %d and %d minutes."
                                                               % (core.MIN_IDLE_BOOT, core.MAX_IDLE_BOOT)))
                    else:
                        self.broker.deliver(session_id, ltd.encode_str("e", "Idle-Boot must be a number."))
                elif opt == "im":
                    if arg.isdigit():
                        minutes = int(arg)

                        if minutes == 0 or (minutes >= core.MIN_IDLE_MOD and minutes <= core.MAX_IDLE_MOD):
                            self.__change_idle_mod__(state.nick, info, minutes)
                        else:
                            self.broker.deliver(session_id,
                                                ltd.encode_str("e",
                                                               "Idle-Mod must be between %d and %d minutes."
                                                               % (core.MIN_IDLE_MOD, core.MAX_IDLE_MOD)))
                    else:
                        self.broker.deliver(session_id, ltd.encode_str("e", "Idle-Mod must be a number."))
                elif opt == "#":
                    if arg.isdigit():
                        limit = int(arg)

                        if limit >= 0 and limit <= self.config.server_max_logins:
                            self.__change_group_limit__(state.nick, info, limit)
                        else:
                            self.broker.deliver(session_id,
                                                ltd.encode_str("e",
                                                               "Group limit must be between 0 and %d."
                                                               % self.config.server_max_logins))
                    else:
                        self.broker.deliver(session_id, ltd.encode_str("e", "Group limit must be a number."))

                arg_required = False
            else:
                opt = word

                if opt in ["b", "im", "#"]:
                    arg_required = True
                elif opt in ["r", "m", "p", "i", "s", "v", "q", "n", "l"]:
                    arg_required = False

                    if (not (self.__try_change_visibility__(session_id, state.nick, info, opt)
                             or self.__try_change_volume__(session_id, state.nick, info, opt)
                             or self.__try_change_control__(session_id, state.nick, info, opt))):
                        self.broker.deliver(session_id, ltd.encode_str("e", "Option %s is unknown." % opt))
                else:
                    self.broker.deliver(session_id, ltd.encode_str("e", "Option \"%s\" is unknown." % opt))

        if arg_required:
            self.broker.deliver(session_id, ltd.encode_str("e", "Option \"%s\" requires an argument." % opt))

        self.groups.update(info)

    def __try_change_visibility__(self, session_id, nick, info, flag):
        found = True

        try:
            visibility = group.Visibility(ord(flag))

            if info.visibility == visibility:
                self.broker.deliver(session_id, ltd.encode_str("e", "Group is already %s." % str(visibility)))
            else:
                info.visibility = visibility

                self.broker.to_channel(str(info), ltd.encode_status_msg("Change", "%s made group %s." % (nick, str(visibility))))
        except ValueError:
            found = False

        return found

    def __try_change_volume__(self, session_id, nick, info, flag):
        found = True

        try:
            volume = group.Volume(ord(flag))


            if info.volume == volume:
                self.broker.deliver(session_id, ltd.encode_str("e", "Group is already %s." % str(volume)))
            else:
                info.volume = volume

                self.broker.to_channel(str(info), ltd.encode_status_msg("Change", "%s made group %s." % (nick, str(volume))))
        except ValueError:
            found = False

        return found

    def __try_change_control__(self, session_id, moderator, info, flag):
        found = True

        try:
            control = group.Control(ord(flag))

            if info.control == control:
                self.broker.deliver(session_id, ltd.encode_str("e", "Group is already %s." % str(control)))
            else:
                info.control = control

                if control == group.Control.PUBLIC:
                    self.broker.to_channel(str(info), ltd.encode_status_msg("Change", "%s made group public." % moderator))
                else:
                    self.broker.to_channel(str(info), ltd.encode_status_msg("Change", "%s is now %s." % (str(info), str(control))))

                info.clear_talkers()

                if control == group.Control.MODERATED:
                    info.moderator = session_id

                    self.broker.to_channel(info.key, ltd.encode_status_msg("Pass", "%s is now mod." % moderator))

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

            self.broker.deliver(session_id, ltd.encode_status_msg("FYI", "%s invited." % sub_state.nick))
            self.broker.deliver(sub_id, ltd.encode_status_msg("FYI", "You are invited to group %s by default." % sub_state.nick))

            info.invite_nick(sub_state.nick, sub_state.authenticated)

    def __change_idle_boot__(self, moderator, info, minutes):
        old_val = info.idle_boot
        info.idle_boot = minutes

        self.broker.to_channel(info.key, ltd.encode_status_msg("Change", "%s changed idle-boot to %s." % (moderator, info.idle_boot_str)))

        if old_val > minutes and minutes > 0:
            boot_ids = []

            for sub_id in self.broker.get_subscribers(str(info)):
                sub_state = self.session.get(sub_id)

                if (not info.moderator or sub_id != info.moderator):
                    if sub_state.t_recv.elapsed() > (info.idle_boot * 60):
                        boot_ids.append(sub_id)

            for sub_id in boot_ids:
                ACTION(actions.usersession.UserSession).idle_boot(sub_id)

    def __change_idle_mod__(self, moderator, info, minutes):
        old_val = info.idle_mod
        info.idle_mod = minutes

        self.broker.to_channel(info.key, ltd.encode_status_msg("Change", "%s changed idle-mod to %s." % (moderator, info.idle_mod_str)))

        if old_val > minutes and minutes > 0 and info.moderator:
            mod_state = self.session.get(info.moderator)

            if mod_state.t_recv.elapsed() > (minutes * 60):
                ACTION(actions.usersession.UserSession).idle_mod(info.moderator)

    def __change_group_limit__(self, moderator, info, limit):
        info.group_limit = limit

        self.broker.to_channel(info.key, ltd.encode_status_msg("Change", "%s changed limit to %s." % (moderator, info.group_limit_str)))

    def status(self, session_id, msgid):
        info = self.__get_group__(session_id)
        logins = self.session.get_nicks()

        self.broker.deliver(session_id,
                            ltd.encode_co_output("Name: %s Mod: %s (%s / %s / %s)"
                                                 % (str(info),
                                                    logins[info.moderator].nick if info.moderator else "(None)",
                                                    info.visibility,
                                                    info.control,
                                                    info.volume),
                                                 msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("Size: %s" % info.group_limit_str, msgid))
        self.broker.deliver(session_id, ltd.encode_co_output("Idle-Boot: %s" % info.idle_boot_str, msgid))
        self.broker.deliver(session_id, ltd.encode_co_output("Idle-Mod: %s" % info.idle_mod_str, msgid))

        self.__send__wrapped__(session_id, "Nicks invited: ", info.invited_nicks, msgid)
        self.__send__wrapped__(session_id, "Addresses invited: ", info.invited_addresses, msgid)
        self.__send__wrapped__(session_id, "Talkers: ", info.talker_nicks, msgid)
        self.__send__wrapped__(session_id, "Talkers (addresses) ", info.talker_addresses, msgid)

    def __send__wrapped__(self, session_id, prefix, seq, msgid):
        line = ", ".join(seq)

        if line:
            parts = wrap(line, 64)

            self.broker.deliver(session_id, ltd.encode_co_output("%s%s" % (prefix, parts[0]), msgid))

            for part in parts[1:]:
                self.broker.deliver(session_id, ltd.encode_co_output("%s%s" % (" " * len(prefix), part), msgid))

    def invite(self, session_id, invitee, mode="n", quiet=None, registered=None):
        quiet = bool(quiet)
        registered = bool(registered)

        info = self.__get_group_if_can_moderate__(session_id)

        if not info.control == group.Control.RESTRICTED:
            raise LtdErrorException("The group isn't restricted.")

        state = self.session.get(session_id)
        loggedin_session = None

        if mode == "n":
            if registered:
                with self.nickdb_connection.enter_scope() as scope:
                    if not self.nickdb.exists(scope, invitee):
                        raise LtdErrorException("User not found.")

            loggedin_session = self.session.find_nick(invitee)

            if loggedin_session:
                self.broker.deliver(loggedin_session,
                                    ltd.encode_status_msg("RSVP", "You are invited to group %s by %s." % (str(info), state.nick)))

                if registered:
                    loggedin_state = self.session.get(loggedin_session)

                    if not loggedin_state.authenticated:
                        self.broker.deliver(loggedin_session,
                                            ltd.encode_status_msg("RSVP", "You need to be registered to enter group %s." % str(info)))
            elif not registered:
                raise LtdErrorException("%s is not signed on." % invitee)

            info.invite_nick(invitee, registered)
        else:
            info.invite_address(invitee, registered)

        if not quiet:
            self.broker.deliver(session_id,
                                ltd.encode_status_msg("FYI", "%s invited%s." % (invitee, " (registered only)" if registered else "")))

        self.groups.update(info)

    def cancel(self, session_id, invitee, mode="n", quiet=None):
        quiet = bool(quiet)

        info = self.__get_group_if_can_moderate__(session_id)

        if not info.control == group.Control.RESTRICTED:
            raise LtdErrorException("The group isn't restricted.")

        try:
            if mode == "n":
                info.cancel_nick(invitee)

                loggedin_session = self.session.find_nick(invitee)

                if loggedin_session:
                    state = self.session.get(session_id)

                    self.broker.deliver(loggedin_session,
                                        ltd.encode_status_msg("FYI", "Invitation to group %s cancelled by %s." % (state.group, state.nick)))
            else:
                info.cancel_address(invitee)
        except KeyError:
            raise LtdErrorException("%s isn't invited." % invitee)

        if not quiet:
            self.broker.deliver(session_id, ltd.encode_status_msg("FYI", "%s cancelled." % invitee))

        self.groups.update(info)

    def talk(self, session_id, talker, mode="n", delete=None, quiet=None, registered=None):
        quiet = bool(quiet)
        delete = bool(delete)
        registered = bool(registered)

        info = self.__get_group_if_can_moderate__(session_id)

        if not info.control == group.Control.CONTROLLED:
            raise LtdErrorException("The group isn't controlled.")

        if delete:
            try:
                if mode == "n":
                    info.mute_nick(talker)

                    loggedin_session = self.session.find_nick(talker)

                    if loggedin_session:
                        state = self.session.get(session_id)

                        self.broker.deliver(loggedin_session,
                                            ltd.encode_status_msg("FYI", "You cannot talk in group %s anymore." % state.group))
                else:
                    info.mute_address(talker)
            except KeyError:
                raise LtdErrorException("%s isn't allowed to talk." % talker)

            if not quiet:
                self.broker.deliver(session_id, ltd.encode_status_msg("FYI", "%s removed from talker list." % talker))
        else:
            loggedin_session = None

            if mode == "n":
                if registered:
                    with self.nickdb_connection.enter_scope() as scope:
                        if not self.nickdb.exists(scope, talker):
                            raise LtdErrorException("User not found.")

                loggedin_session = self.session.find_nick(talker)

                if loggedin_session:
                    self.broker.deliver(loggedin_session, ltd.encode_status_msg("RSVP", "You can now talk in group %s." % str(info)))

                    if registered:
                        loggedin_state = self.session.get(loggedin_session)

                        if not loggedin_state.authenticated:
                            self.broker.deliver(loggedin_session,
                                                ltd.encode_status_msg("RSVP",
                                                                      "You need to be registered to talk in group %s." % str(info)))
                elif not registered:
                    raise LtdErrorException("%s is not signed on." % talker)

                info.unmute_nick(talker, registered)
            else:
                info.unmute_address(talker, registered)

            if not quiet:
                self.broker.deliver(session_id,
                                    ltd.encode_status_msg("FYI",
                                                          "%s%s can now talk." % (talker, " (registered only)" if registered else "")))

        self.groups.update(info)

    def boot(self, session_id, nick):
        info = self.__get_group_if_can_moderate__(session_id)

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session == session_id:
            raise LtdErrorException("You cannot boot yourself.")

        if not loggedin_session:
            raise LtdErrorException("%s is not signed on." % nick)

        state = self.session.get(session_id)
        loggedin_state = self.session.get(loggedin_session)

        if loggedin_state.group.lower() != state.group.lower():
            raise LtdErrorException("%s is not in your group." % nick)

        if loggedin_state.authenticated:
            with self.nickdb_connection.enter_scope() as scope:
                if self.nickdb.is_admin(scope, state.nick):
                    self.broker.deliver(loggedin_session, ltd.encode_status_msg("Boot", "%s tried to boot you." % state.nick))

                    self.reputation.fatal(session_id)

                    raise LtdErrorException("You cannot boot an admin.")

        try:
            info.cancel_nick(loggedin_state.nick)

            self.broker.deliver(session_id, ltd.encode_status_msg("FYI", "%s cancelled." % nick))
        except KeyError: pass

        try:
            info.mute_nick(loggedin_state.nick)

            self.broker.deliver(session_id, ltd.encode_status_msg("FYI", "%s removed from talker list." % nick))
        except KeyError: pass

        self.broker.to_channel(info.key, ltd.encode_status_msg("Boot", "%s was booted." % nick))
        self.broker.deliver(loggedin_session, ltd.encode_status_msg("Boot", "%s booted you." % state.nick))

        ACTION(actions.usersession.UserSession).join(loggedin_session, core.BOOT_GROUP)

        with self.statsdb_connection.enter_scope() as scope:
            self.statsdb.add_boot(scope)

            scope.complete()

    def pass_over(self, session_id, nick):
        info = self.__get_group_if_can_moderate__(session_id)

        loggedin_session = self.session.find_nick(nick)

        if not loggedin_session:
            raise LtdErrorException("%s is not signed on." % nick)

        if info.moderator == loggedin_session:
            raise LtdErrorException("You are already moderator.")

        loggedin_state = self.session.get(loggedin_session)

        if loggedin_state.nick.lower() == core.NICKSERV.lower():
            raise LtdErrorException("Cannot pass to %s." % core.NICKSERV)

        info.moderator = loggedin_session

        self.groups.update(info)

        state = self.session.get(session_id)

        self.broker.deliver(loggedin_session, ltd.encode_status_msg("Pass",
                                                                    "%s just passed moderation of group %s."
                                                                    % (state.nick, info.display_name)))

        if info.volume != group.Volume.QUIET:
            self.broker.to_channel(info.key, ltd.encode_status_msg("Pass",
                                                                   "%s has passed moderation to %s."
                                                                   % (state.nick, loggedin_state.nick)))

    def relinquish(self, session_id):
        info = self.__get_group_if_can_moderate__(session_id)

        info.moderator = None

        state = self.session.get(session_id)

        if info.volume != group.Volume.QUIET:
            self.broker.to_channel(info.key, ltd.encode_status_msg("Change", "%s just relinquished moderation." % state.nick))

        if info.control != group.Control.PUBLIC:
            info.control = group.Control.PUBLIC
            info.clear_talkers()
            info.clear_invitations()

            if info.volume != group.Volume.QUIET:
                self.broker.to_channel(info.key, ltd.encode_status_msg("Change", "Group is now public."))

        self.groups.update(info)

    def __get_group__(self, session_id):
        state = self.session.get(session_id)

        return self.groups.get(state.group)

    def __get_group_if_can_moderate__(self, session_id, allow_public=False):
        info = self.__get_group__(session_id)

        if self.__is_protected_group__(info.key):
            self.reputation.critical(session_id)

            raise LtdErrorException("You aren't the moderator.")

        if not (allow_public and info.control == group.Control.PUBLIC):
            if info.moderator:
                self.log.debug("Group's moderator: %s", info.moderator)

                if info.moderator != session_id:
                    self.log.debug("User isn't moderator, testing administrative privileges.")

                    with self.nickdb_connection.enter_scope() as scope:
                        state = self.session.get(session_id)

                        if not self.nickdb.exists(scope, state.nick) or not self.nickdb.is_admin(scope, state.nick):
                            self.reputation.critical(session_id)

                            raise LtdErrorException("You aren't the moderator.")

        return info

    @staticmethod
    def __is_protected_group__(name):
        return name.lower() in [p.lower() for p in [core.DEFAULT_GROUP, core.IDLE_GROUP, core.BOOT_GROUP]]
