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
from actions import Injected
import core
import group
import ltd
from exception import LtdErrorException

class Notify(Injected):
    def list(self, session_id):
        state = self.session.get(session_id)

        empty = True

        for nick in state.notifylist.nicks:
            empty = False

            self.broker.deliver(session_id, ltd.encode_status_msg("Notify-Nickname", nick))

        for site in state.notifylist.sites:
            empty = False

            self.broker.deliver(session_id, ltd.encode_status_msg("Notify-Site", site))

        if empty:
            self.broker.deliver(session_id, ltd.encode_status_msg("Notify-List", "Empty List."))

    def toggle(self, session_id, target, mode="n", quiet=None):
        quiet = bool(quiet)

        state = self.session.get(session_id)

        msg = None

        if mode == "n":
            if state.notifylist.watch_nick(target):
                msg = "%s added to nickname notify list." % target
            else:
                msg = "%s removed from nickname notify list." % target
        else:
            if state.notifylist.watch_site(target):
                msg = "%s added to site notify list." % target
            else:
                msg = "%s removed from site notify list." % target

        if not quiet:
            self.broker.deliver(session_id, ltd.encode_status_msg("Notify", msg))

        self.session.set(session_id, state)

    def notify_signon(self, session_id):
        self.__notify__(session_id, signed_on=True)

    def notify_signoff(self, session_id):
        self.__notify__(session_id, signed_on=False)

    def __notify__(self, session_id, signed_on):
        state = self.session.get(session_id)

        info = None

        if state.group:
            info = self.groups.get(state.group)

        status_name = "Notify-%s" % ("On" if signed_on else "Off")

        for k, v in self.session:
            if k != session_id and v.nick != core.NICKSERV and not v.notifylist.empty():
                hidden = not info or info.visibility == group.Visibility.INVISIBLE
                same_group= v.group and v.group.lower() == info.key

                if not hidden or same_group:
                    if v.notifylist.nick_watched(state.nick) and not same_group:
                        self.broker.deliver(k, ltd.encode_status_msg(status_name, state.nick))

                    if v.notifylist.site_watched(state.address) and not same_group:
                        self.broker.deliver(k, ltd.encode_status_msg(status_name, state.address))
