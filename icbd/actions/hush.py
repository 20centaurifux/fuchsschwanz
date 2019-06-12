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
from exception import LtdErrorException
import ltd

class Hush(Injected):
    def list(self, session_id):
        state = self.session.get(session_id)

        empty = True

        for nick in state.hushlist.nicks:
            empty = False

            if nick.private:
                self.broker.deliver(session_id, ltd.encode_status_msg("Personal-Nick-Hushed", nick.display_name))

            if nick.public:
                self.broker.deliver(session_id, ltd.encode_status_msg("Open-Nick-Hushed", nick.display_name))

        for site in state.hushlist.sites:
            empty = False

            if site.private:
                self.broker.deliver(session_id, ltd.encode_status_msg("Personal-Site-Hushed", site.display_name))

            if site.public:
                self.broker.deliver(session_id, ltd.encode_status_msg("Open-Site-Hushed", site.display_name))

        if empty:
            self.broker.deliver(session_id, ltd.encode_status_msg("Hush-List", "Empty List."))

    def toggle(self, session_id, target, mode="n", quiet=None, msg_type=""):
        quiet = bool(quiet)

        state = self.session.get(session_id)

        try:
            if mode == "n":
                if not msg_type or msg_type == "o":
                    if state.hushlist.hush_nick_public(target):
                        if not quiet:
                            self.broker.deliver(session_id, ltd.encode_status_msg("Hush", "%s added to nickname open hush list." % target))
                    elif not quiet:
                        self.broker.deliver(session_id, ltd.encode_status_msg("Hush", "%s removed from nickname open hush list." % target))

                if not msg_type or msg_type == "p":
                    if state.hushlist.hush_nick_private(target):
                        if not quiet:
                            self.broker.deliver(session_id, ltd.encode_status_msg("Hush", "%s added to nickname personal hush list." % target))
                    elif not quiet:
                        self.broker.deliver(session_id, ltd.encode_status_msg("Hush", "%s removed from nickname personal hush list." % target))
            else:
                if not msg_type or msg_type == "o":
                    if state.hushlist.hush_site_public(target):
                        if not quiet:
                            self.broker.deliver(session_id, ltd.encode_status_msg("Hush", "%s added to site open hush list." % target))
                    elif not quiet:
                        self.broker.deliver(session_id, ltd.encode_status_msg("Hush", "%s removed from site open hush list." % target))

                if not msg_type or msg_type == "p":
                    if state.hushlist.hush_site_private(target):
                        if not quiet:
                            self.broker.deliver(session_id, ltd.encode_status_msg("Hush", "%s added to site personal hush list." % target))
                    elif not quiet:
                        self.broker.deliver(session_id, ltd.encode_status_msg("Hush", "%s removed from site personal hush list." % target))
        except OverflowError:
            raise LtdErrorException("Hush list is full.")

        self.session.set(session_id, state)
