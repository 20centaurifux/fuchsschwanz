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
import ltd
import validate
from exception import LtdErrorException

class PrivateMessage(Injected):
    def __init__(self):
        super().__init__()

        self.__away_table = self.resolve(session.AwayTimeoutTable)

    def send(self, session_id, receiver, message):
        loggedin_session = self.session.find_nick(receiver)

        if loggedin_session:
            state = self.session.get(session_id)

            max_len = 254 - validate.NICK_MAX - 5

            for part in wrap(message, max_len):
                e = ltd.Encoder("c")

                e.add_field_str(state.nick, append_null=False)
                e.add_field_str(part, append_null=True)

                self.broker.deliver(loggedin_session, e.encode())

                if state.echo == session.EchoMode.VERBOSE:
                    self.broker.deliver(session_id, ltd.encode_co_output("<*to: %s*> %s" % (receiver, part)))

            loggedin_state = self.session.get(loggedin_session)

            if loggedin_state.away:
                if not self.__away_table.is_alive(session_id, receiver):
                    self.broker.deliver(session_id, ltd.encode_status_msg("Away",
                                                                          "%s (since %s)." % (loggedin_state.away,
                                                                                              loggedin_state.t_away.elapsed_str())))
                    self.__away_table.set_alive(session_id, receiver, self.config.timeouts_away_message)
        else:
            raise LtdErrorException("%s is not signed on." % receiver)
