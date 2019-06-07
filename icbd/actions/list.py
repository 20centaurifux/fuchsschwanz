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
from actions import Injected
import group
import ltd
from exception import LtdErrorException

class List(Injected):
    def list_and_quit(self, session_id, msgid=""):
        self.list(session_id, msgid)

        self.broker.deliver(session_id, ltd.encode_empty_cmd("g"))

    def list(self, session_id, msgid=""):
        is_admin = False

        state = self.session.get(session_id)

        if state.authenticated:
            with self.nickdb_connection.enter_scope() as scope:
                is_admin = self.nickdb.is_admin(scope, state.nick)

        logins = self.session.get_nicks()

        available_groups = self.groups.get_groups()

        if available_groups:
            for info in available_groups[:-1]:
                if self.__show_group__(session_id, state, info, logins, is_admin, False, msgid):
                    self.broker.deliver(session_id, ltd.encode_co_output("", msgid))

            self.__show_group__(session_id, state, available_groups[-1], logins, is_admin, False, msgid)

        self.__show_summary__(session_id, logins, available_groups, msgid)

    def list_group(self, session_id, group_name, msgid=""):
        is_admin = False

        state = self.session.get(session_id)

        if group_name == ".":
            group_name = state.group

        if not self.groups.exists(group_name):
            raise LtdErrorException("Group %s not found." % group_name)

        if state.authenticated:
            with self.nickdb_connection.enter_scope() as scope:
                is_admin = self.nickdb.is_admin(scope, state.nick)

        info = self.groups.get(group_name)

        logins = self.session.get_nicks()

        self.__show_group__(session_id, state, info, logins, is_admin, True, msgid)

    def __show_group__(self, session_id, state, info, logins, is_admin, ignore_visibility, msgid):
        show_group = True
        display_name = str(info)

        if not ignore_visibility and info.visibility != group.Visibility.VISIBLE:
            if is_admin or state.group == info.key:
                display_name = "*%s*" % str(info)
            else:
                display_name = "-SECRET-"
                show_group = info.visibility != group.Visibility.INVISIBLE

        if show_group:
            moderator = logins[info.moderator].nick if info.moderator else "(None)"
            flags = "%s%s%s" % (chr(info.control.value), chr(info.visibility.value), chr(info.volume.value))
            topic = info.topic if info.topic else "(None)"

            self.broker.deliver(session_id,
                                ltd.encode_co_output("Group: %-8s (%s) Mod: %-13s Topic: %s" % (display_name, flags, moderator, topic),
                                                     msgid))

            self.broker.deliver(session_id,
                                ltd.encode_co_output("   Nickname         Idle Sign-On  Account", msgid))

            subscribers = sorted([[sub_id, logins[sub_id]] for sub_id in self.broker.get_subscribers(info.key)],
                                 key=lambda arg: arg[1].nick.lower())

            for sub_id, sub_state in subscribers:
                admin_flag = "*" if info.moderator == sub_id else " "

                e = ltd.Encoder("i")

                idle = int(sub_state.t_recv.elapsed()) if sub_state.t_recv else 0
                signon = int(sub_state.signon.timestamp())

                e.add_field_str("wl", append_null=False)
                e.add_field_str(admin_flag, append_null=False)
                e.add_field_str(sub_state.nick, append_null=False)
                e.add_field_str(str(idle), append_null=False)
                e.add_field_str("0", append_null=False)
                e.add_field_str(str(signon), append_null=False)
                e.add_field_str(sub_state.loginid, append_null=False)
                e.add_field_str(sub_state.address, append_null=False)
                e.add_field_str(sub_state.status, append_null=True)

                self.broker.deliver(session_id, e.encode())

        return show_group

    def __show_summary__(self, session_id, logins, groups, msgid):
        logins_n = len(logins) - 1
        logins_suffix = "" if logins_n == 1 else "s"

        groups_n = len(groups)
        groups_suffix = "" if groups_n == 1 else "s"

        self.broker.deliver(session_id,
                            ltd.encode_co_output("Total: %d user%s in %d group%s." % (logins_n, logins_suffix, groups_n, groups_suffix),
                                                 msgid))

    def shortlist(self, session_id, with_members=False, msgid=""):
        is_admin = False

        state = self.session.get(session_id)

        if state.authenticated:
            with self.nickdb_connection.enter_scope() as scope:
                is_admin = self.nickdb.is_admin(scope, state.nick)

        logins = self.session.get_nicks()

        available_groups = self.groups.get_groups()

        if available_groups:
            for info in available_groups[:-1]:
                if self.__show_short_group__(session_id, state, info, logins, is_admin, with_members, msgid):
                    self.broker.deliver(session_id, ltd.encode_co_output("", msgid))

            self.__show_short_group__(session_id, state, available_groups[-1], logins, is_admin, with_members, msgid)

        self.__show_summary__(session_id, logins, available_groups, msgid)

    def __show_short_group__(self, session_id, state, info, logins, is_admin, with_members, msgid):
        show_group = True
        display_name = str(info)

        if info.visibility != group.Visibility.VISIBLE:
            if is_admin or state.group == info.key:
                display_name = "*%s*" % str(info)
            else:
                display_name = "-SECRET-"
                show_group = info.visibility != group.Visibility.INVISIBLE

        if show_group:
            moderator = logins[info.moderator].nick if info.moderator else "(None)"
            flags = "%s%s%s" % (chr(info.control.value), chr(info.visibility.value), chr(info.volume.value))
            topic = info.topic if info.topic else "(None)"

            self.broker.deliver(session_id,
                                ltd.encode_co_output("Group: %-12s (%s) Mod: %-12s Topic: %s"
                                                     % (display_name, flags, moderator, topic), msgid))

            if with_members:
                subscribers = ", ".join(sorted([logins[sub_id].nick for sub_id in self.broker.get_subscribers(info.key)],
                                               key=lambda n: n.lower()))
                lines = wrap(subscribers, 64)

                if lines:
                    self.broker.deliver(session_id, ltd.encode_co_output("    Members: %s" % lines[0], msgid))

                    for line in lines[1:]:
                        self.broker.deliver(session_id, ltd.encode_co_output("             %s" % line, msgid))

        return show_group
