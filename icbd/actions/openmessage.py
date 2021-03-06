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
import session
import group
import ltd
import validate
from exception import LtdErrorException, LtdStatusException

class OpenMessage(Injected):
    def send(self, session_id, message, exclude=None):
        state = self.session.get(session_id)

        info = self.groups.get(state.group)

        if info.volume == group.Volume.QUIET:
            raise LtdErrorException("Open messages are not permitted in quiet groups.")

        if info.control == group.Control.CONTROLLED and info.moderator != session_id:
            if (not info.nick_can_talk(state.nick, state.authenticated)
                    and not info.address_can_talk(state.loginid, state.ip, state.host, state.authenticated)):
                self.reputation.warning(session_id)

                raise LtdErrorException("You do not have permission to talk in this group.")

        if len(self.broker.get_subscribers(state.group)) == 1:
            raise LtdErrorException("No one else in group.")

        max_len = 254 - validate.NICK_MAX - 2

        for part in wrap(message, max_len):
            e = ltd.Encoder("b")

            e.add_field_str(state.nick, append_null=False)
            e.add_field_str(part, append_null=True)

            if exclude:
                excluded_sessions = set()

                excluded_id = self.session.find_nick(exclude)

                if not excluded_id:
                    raise LtdStatusException("Exclude", "Nick not found.")

                subscribers = self.broker.get_subscribers(info.key)

                if not excluded_id in subscribers:
                    raise LtdStatusException("Exclude", "Nick is not here.")

                excluded_sessions.add(excluded_id)

                if state.echo == session.EchoMode.OFF:
                    excluded_sessions.add(session_id)

                msg = e.encode()

                for sub_id in [s for s in subscribers if not s in excluded_sessions]:
                    self.broker.deliver(sub_id, msg)
            else:
                if state.echo == session.EchoMode.OFF:
                    self.broker.to_channel_from(session_id, state.group, e.encode())
                else:
                    self.broker.to_channel(state.group, e.encode())
