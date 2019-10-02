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
import shutdown
import ipfilter
import dateutils
from exception import LtdErrorException, LtdStatusException

def isadmin(fn):
    def wrapper(*args, **kwds):
        args[0].__test_admin__(args[1])

        return fn(*args, **kwds)

    return wrapper

class Admin(Injected):
    def __init__(self):
        super().__init__()

        self.__registry = self.resolve(log.Registry)
        self.__shutdown = self.resolve(shutdown.Shutdown)
        self.__ipfilter_connection = self.resolve(ipfilter.Connection)
        self.__ipfilters = self.resolve(ipfilter.Storage)

    @isadmin
    def get_reputation(self, session_id, nick, msgid=""):
        loggedin_session = self.session.find_nick(nick)

        if not loggedin_session:
            raise LtdErrorException("%s is not signed on." % nick)

        loggedin_state = self.session.get(loggedin_session)
        reputation = self.reputation.get(loggedin_session)

        self.broker.deliver(session_id,
                            ltd.encode_co_output("%s (%s): %.2f"
                                                 % (nick, loggedin_state.address, reputation), msgid))

    @isadmin
    def wall(self, session_id, message):
        e = ltd.Encoder("f")

        e.add_field_str("WALL", append_null=False)
        e.add_field_str(message, append_null=True)

        self.broker.broadcast(e.encode())

    @isadmin
    def set_log_level(self, session_id, level, msgid):
        try:
            verbosity = Verbosity(level)
        except ValueError:
            raise LtdErrorException("Unsupported log level: %d" % level)

        self.log.info("Verbosity set to %s.", verbosity)

        for l in self.__registry.loggers:
            l.setLevel(log.LOG_LEVELS[verbosity])

        self.broker.deliver(session_id, ltd.encode_co_output("The log level is %d." % level, msgid))

    @isadmin
    def log_level(self, session_id, msgid):
        verbosity = next(k for k, v in log.LOG_LEVELS.items() if v == self.log.level)

        self.broker.deliver(session_id, ltd.encode_co_output("The log level is %d." % verbosity.value, msgid))

    @isadmin
    def drop(self, session_id, nicks):
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

    @isadmin
    def shutdown(self, session_id, delay, restart):
        self.__test_admin__(session_id)

        msg = "Server %s in %s." % ("restarting" if restart else "shutting down", dateutils.elapsed_time(delay))

        if restart:
            self.__shutdown.restart(delay)
        else:
            self.__shutdown.halt(delay)

        e = ltd.Encoder("f")

        e.add_field_str("WALL", append_null=False)
        e.add_field_str(msg, append_null=True)

        self.broker.broadcast(e.encode())

    @isadmin
    def cancel_shutdown(self, session_id):
        self.__test_admin__(session_id)

        self.__shutdown.cancel()

        e = ltd.Encoder("f")

        e.add_field_str("WALL", append_null=False)
        e.add_field_str("Server shutdown cancelled.", append_null=True)

        self.broker.broadcast(e.encode())

    @isadmin
    def ipfilter(self, session_id, fields):
        action, argv = fields[0], fields[1:]

        fn = None

        if action == "deny":
            fn = self.__deny_login__
        elif action == "drop":
            fn = self.__drop_ip_filter__
        elif action == "flush":
            fn = self.__flush_ip_filters__
        elif action == "show":
            fn = self.__show_ip_filters__
        elif not action:
            raise LtdErrorException("Usage: ipfilter {action} {arguments}")
        else:
            raise LtdErrorException("Unsupported action.")

        fn(session_id, argv)

    def __deny_login__(self, session_id, argv):
        usage = "Usage: ipfilter deny {filter} {seconds}"

        if not argv or len(argv) > 2:
            raise LtdErrorException(usage)

        filter = None

        try:
            filter = ipfilter.Factory.create(argv[0])
        except:
            raise LtdErrorException("Filter is malformed.")

        ttl = -1

        try:
            if len(argv) == 2:
                ttl = int(argv[1])

                if ttl < 0:
                    raise ValueError
        except:
            raise LtdErrorException(usage)

        with self.__ipfilter_connection.enter_scope() as scope:
            self.__ipfilters.deny(scope, filter, ttl)

            lifetime = "forever"

            if ttl > -1:
                lifetime = dateutils.elapsed_time(ttl)

            self.broker.deliver(session_id, ltd.encode_status_msg("IP-Filter", "%s denied (%s)." % (argv[0], lifetime)))

            scope.complete()

    def __drop_ip_filter__(self, session_id, argv):
        if len(argv) != 1:
            raise LtdErrorException("Usage: ipfilter drop {filter}")

        filter = None

        try:
            filter = ipfilter.Factory.create(argv[0])
        except:
            raise LtdErrorException("Filter is malformed.")

        with self.__ipfilter_connection.enter_scope() as scope:
            if not self.__ipfilters.deny_filter_exists(scope, filter.expression):
                raise LtdErrorException("Filter not found.")

            self.__ipfilters.remove(scope, filter.expression)

            self.broker.deliver(session_id, ltd.encode_status_msg("IP-Filter", "%s dropped." % (argv[0],)))

            scope.complete()

    def __flush_ip_filters__(self, session_id, argv):
        if argv:
            raise LtdErrorException("Usage: ipfilter flush")

        with self.__ipfilter_connection.enter_scope() as scope:
            self.__ipfilters.flush(scope)

            scope.complete()

        self.broker.deliver(session_id, ltd.encode_status_msg("IP-Filter", "Flushed."))

    def __show_ip_filters__(self, session_id, argv):
        if argv:
            raise LtdErrorException("Usage: ipfilter show")

        filters = []

        with self.__ipfilter_connection.enter_scope() as scope:
            for f, l in self.__ipfilters.load_deny_filters(scope):
                lifetime = "forever"

                if l > -1:
                    time_left = max(1, l - dateutils.now())
                    lifetime = dateutils.elapsed_time(time_left)

                filters.append((f.expression, lifetime))

        if filters:
            for entry in sorted(filters, key=lambda e: "@".join(reversed(e[0].split("@", 1))).lower()):
                self.broker.deliver(session_id, ltd.encode_status_msg("IP-Filter", "%s denied (%s)" % entry))
        else:
            self.broker.deliver(session_id, ltd.encode_status_msg("IP-Filter", "List is empty."))

    def __test_admin__(self, session_id):
        is_admin = False

        state = self.session.get(session_id)

        if state.authenticated:
            with self.nickdb_connection.enter_scope() as scope:
                is_admin = self.nickdb.is_admin(scope, state.nick)

        if not is_admin:
            self.reputation.critical(session_id)

            raise LtdErrorException("You don't have administrative privileges.")
