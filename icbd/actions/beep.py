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
import session
import ltd
from exception import LtdStatusException, LtdErrorException

class Beep(Injected):
    def __init__(self):
        super().__init__()

        self.away_table = self.resolve(session.AwayTimeoutTable)

    def beep(self, session_id, receiver):
        loggedin_session = self.session.find_nick(receiver)

        if not loggedin_session:
            raise LtdErrorException("%s is not signed on." % receiver)

        loggedin_state = self.session.get(loggedin_session)

        state = self.session.get(session_id)

        if state.echo == session.EchoMode.VERBOSE:
            self.broker.deliver(session_id, ltd.encode_co_output("<*to: %s*> [=Beep=]" % receiver))

        if loggedin_state.beep != session.BeepMode.ON:
            if loggedin_state.beep == session.BeepMode.VERBOSE:
                self.broker.deliver(loggedin_session,
                                    ltd.encode_status_msg("No-Beep", "%s attempted (and failed) to beep you." % state.nick))

            raise LtdStatusException("Beep", "User has nobeep enabled.")

        self.broker.deliver(loggedin_session, ltd.encode_str("k", state.nick))

        if loggedin_state.away:
            if not self.away_table.is_alive(session_id, receiver):
                self.broker.deliver(session_id,
                                    ltd.encode_status_msg("Away",
                                                          "%s (since %s)." % (loggedin_state.away, loggedin_state.t_away.elapsed_str())))

                self.away_table.set_alive(session_id, receiver, self.config.timeouts_away_message)

    def set_mode(self, session_id, mode):
        if not mode in ["on", "off", "verbose"]:
            raise LtdErrorException("Usage: /nobeep on/off/verbose")

        real_mode = session.BeepMode.ON

        if mode == "on":
            real_mode = session.BeepMode.OFF
        elif mode == "verbose":
            real_mode = session.BeepMode.VERBOSE

        self.session.update(session_id, beep=real_mode)

        self.broker.deliver(session_id, ltd.encode_status_msg("No-Beep", "No-Beep is now %s." % mode))
