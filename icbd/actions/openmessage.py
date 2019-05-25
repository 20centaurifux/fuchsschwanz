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
from textwrap import wrap
from actions import Injected
import group
import tld
import validate
from exception import TldErrorException

class OpenMessage(Injected):
    def send(self, session_id, message):
        state = self.session.get(session_id)

        info = self.groups.get(state.group)

        if info.volume == group.Volume.QUIET:
            raise TldErrorException("Open messages are not permitted in quiet groups.")

        if info.control == group.Control.CONTROLLED:
            if (not info.nick_can_talk(state.nick, state.authenticated)
                    and not info.address_can_talk(state.loginid, state.ip, state.host, state.authenticated)):
                self.reputation.warning(session_id)

                raise TldErrorException("You do not have permission to talk in this group.")

        max_len = 254 - validate.NICK_MAX - 2

        for part in wrap(message, max_len):
            e = tld.Encoder("b")

            e.add_field_str(state.nick, append_null=False)
            e.add_field_str(part, append_null=True)

            if self.broker.to_channel_from(session_id, state.group, e.encode()) == 0:
                raise TldErrorException("No one else in group.")
