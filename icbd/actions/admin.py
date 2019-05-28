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
import ltd
from exception import LtdErrorException

class Admin(Injected):
    def get_reputation(self, session_id, nick, msgid=""):
        is_admin = False

        state = self.session.get(session_id)

        if state.authenticated:
            with self.db_connection.enter_scope() as scope:
                is_admin = self.nickdb.is_admin(scope, state.nick)

        if not is_admin:
            self.reputation.critical(session_id)

            raise LtdErrorException("You don't have administrative privileges.")

        loggedin_session = self.session.find_nick(nick)

        if not loggedin_session:
            raise LtdErrorException("%s is not signed on." % nick)

        loggedin_state = self.session.get(loggedin_session)
        reputation = self.reputation.get(loggedin_session)

        self.broker.deliver(session_id,
                            ltd.encode_co_output("%s (%s): %.2f"
                                                 % (nick, loggedin_state.address, reputation), msgid))
