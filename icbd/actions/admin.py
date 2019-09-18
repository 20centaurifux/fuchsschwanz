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
from core import Verbosity
import validate
import log
from exception import LtdErrorException, LtdStatusException

class Admin(Injected):
    def __init__(self):
        super().__init__()

        self.__registry = self.resolve(log.Registry)

    def get_reputation(self, session_id, nick, msgid=""):
        self.__test_admin__(session_id)

        loggedin_session = self.session.find_nick(nick)

        if not loggedin_session:
            raise LtdErrorException("%s is not signed on." % nick)

        loggedin_state = self.session.get(loggedin_session)
        reputation = self.reputation.get(loggedin_session)

        self.broker.deliver(session_id,
                            ltd.encode_co_output("%s (%s): %.2f"
                                                 % (nick, loggedin_state.address, reputation), msgid))

    def wall(self, session_id, message):
        self.__test_admin__(session_id)

        e = ltd.Encoder("f")

        e.add_field_str("WALL", append_null=False)
        e.add_field_str(message, append_null=True)

        self.broker.broadcast(e.encode())

    def set_log_level(self, session_id, level, msgid):
        self.__test_admin__(session_id)

        try:
            verbosity = Verbosity(level)
        except ValueError:
            raise LtdErrorException("Unsupported log level: %d" % level)

        self.log.info("Verbosity set to %s.", verbosity)

        for l in self.__registry.loggers:
            l.setLevel(log.LOG_LEVELS[verbosity])

        self.broker.deliver(session_id, ltd.encode_co_output("The log level is %d." % level, msgid))

    def log_level(self, session_id, msgid):
        self.__test_admin__(session_id)

        verbosity = next(k for k, v in log.LOG_LEVELS.items() if v == self.log.level)

        self.broker.deliver(session_id, ltd.encode_co_output("The log level is %d." % verbosity.value, msgid))

    def drop(self, session_id, nicks):
        self.__test_admin__(session_id)

        state = self.session.get(session_id)

        with self.statsdb_connection.enter_scope() as scope:
            for nick in nicks:
                victim_id = self.session.find_nick(nick)

                if victim_id:
                    self.broker.deliver(session_id, ltd.encode_status_msg("Drop", "You have dropped %s." % nick))
                    self.broker.deliver(victim_id, ltd.encode_status_msg("Drop", "You have been disconnected by %s." % state.nick))
                    self.broker.deliver(victim_id, ltd.encode_empty_cmd("g"))

                    self.statsdb.add_drop(scope)
                else:
                    self.broker.deliver(session_id, ltd.encode_str("e", "%s not found." % nick))

                scope.complete()

    def change_password(self, session_id, nick, password):
        state = self.session.get(session_id)

        if state.nick.lower() == nick.lower():
            if not state.authenticated:
                raise LtdErrorException("You must be registered to change your password.")
        else:
            self.__test_admin__(session_id)

        self.log.debug("Changing password of user %s." % nick)

        with self.nickdb_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, nick):
                raise LtdErrorException("%s not found." % nick)

            self.log.debug("Nick found, changing password.")

            if not validate.is_valid_password(password):
                raise LtdStatusException("Password",
                                         "Password format not valid. Password length must be between %d and %d characters."
                                         % (validate.PASSWORD_MIN, validate.PASSWORD_MAX))

            self.nickdb.set_password(scope, nick, password)

            self.broker.deliver(session_id, ltd.encode_status_msg("Pass", "Password changed."))

            scope.complete()

    def __test_admin__(self, session_id):
        is_admin = False

        state = self.session.get(session_id)

        if state.authenticated:
            with self.nickdb_connection.enter_scope() as scope:
                is_admin = self.nickdb.is_admin(scope, state.nick)

        if not is_admin:
            self.reputation.critical(session_id)

            raise LtdErrorException("You don't have administrative privileges.")
