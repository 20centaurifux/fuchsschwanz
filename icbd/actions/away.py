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
from actions import Injected
import tld
from exception import TldStatusException
from timer import Timer 

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
            raise TldStatusException("Away", "No away message set.")

        self.session.update(session_id, away=None, t_away=None)

        self.broker.deliver(session_id, tld.encode_status_msg("Away", "Away message unset."))
