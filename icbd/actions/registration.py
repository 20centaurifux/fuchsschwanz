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
from datetime import datetime
from textwrap import wrap
from actions import Injected
import validate
import ltd
from exception import LtdResponseException, LtdErrorException, LtdStatusException

class Registration(Injected):
    def __init__(self):
        super().__init__()

    def register(self, session_id, password):
        self.log.debug("Starting user registration.")

        state = self.session.get(session_id)

        registered = False

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.exists(scope, state.nick):
                self.log.debug("Nick found, validating password.")

                if not self.nickdb.check_password(scope, state.nick, password):
                    self.reputation.fatal(session_id)

                    raise LtdErrorException("Authorization failure.")

                registered = True
            else:
                self.log.debug("Creating new user profile for %s.", state.nick)

                if not validate.is_valid_password(password):
                    raise LtdStatusException("Register",
                                             "Password format not valid. Password length must be between %d and %d characters."
                                             % (validate.PASSWORD_MIN, validate.PASSWORD_MAX))

                self.nickdb.create(scope, state.nick)
                self.nickdb.set_secure(scope, state.nick, True)
                self.nickdb.set_admin(scope, state.nick, False)
                self.nickdb.set_password(scope, state.nick, password)
                self.nickdb.set_mbox_limit(scope, state.nick, self.config.mbox_limit)

                registered = True

                scope.complete()

        if registered:
            self.mark_registered(session_id)
            self.notify_messagebox(session_id)

    def mark_registered(self, session_id):
        with self.db_connection.enter_scope() as scope:
            state = self.session.get(session_id)

            self.nickdb.set_lastlogin(scope, state.nick, state.loginid, state.host)

            now = datetime.utcnow()

            self.nickdb.set_signon(scope, state.nick, now)

            self.session.update(session_id, signon=now, authenticated=True)

            self.broker.deliver(session_id, ltd.encode_status_msg("Register", "Nick registered."))

            self.reputation.good(session_id)

            scope.complete()

    def notify_messagebox(self, session_id):
        with self.db_connection.enter_scope() as scope:
            state = self.session.get(session_id)

            if self.nickdb.exists(scope, state.nick):
                count = self.nickdb.count_messages(scope, state.nick)
                limit = self.nickdb.get_mbox_limit(scope, state.nick)

                if count > 0:
                    self.broker.deliver(session_id,
                                        ltd.encode_status_msg("Message", "You have %d message%s." % (count, "" if count == 1 else "s")))

                if count >= limit:
                    self.broker.deliver(session_id, ltd.encode_status_msg("Message", "User mailbox is full."))

    def change_password(self, session_id, old_pwd, new_pwd):
        self.log.debug("Changing user password.")

        state = self.session.get(session_id)

        with self.db_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, state.nick):
                raise LtdErrorException("Authorization failure.")

            self.log.debug("Nick found, validating password.")

            if not self.nickdb.check_password(scope, state.nick, old_pwd):
                self.reputation.fatal(session_id)

                raise LtdErrorException("Authorization failure.")

            self.nickdb.set_password(scope, state.nick, new_pwd)

            self.broker.deliver(session_id, ltd.encode_status_msg("Pass", "Password changed."))

            scope.complete()

    def set_security_mode(self, session_id, enabled, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise LtdErrorException("You must be registered to change your security.")

        with self.db_connection.enter_scope() as scope:
            self.nickdb.set_secure(scope, state.nick, enabled)

            if enabled:
                self.broker.deliver(session_id, ltd.encode_co_output("Security set to password required.", msgid))
            else:
                self.broker.deliver(session_id, ltd.encode_co_output("Security set to automatic.", msgid))

            scope.complete()

    def change_field(self, session_id, field, text, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise LtdErrorException("You must be registered to change your security.")

        if not self.__validate_field__(field, text):
            raise LtdResponseException("Invalid attribute.",
                                       ltd.encode_co_output("'%s' format not valid." % self.__map_field__(field), msgid))

        with self.db_connection.enter_scope() as scope:
            details = self.nickdb.lookup(scope, state.nick)

            setattr(details, field, text)

            self.nickdb.update(scope, state.nick, details)

            if text:
                self.broker.deliver(session_id, ltd.encode_co_output("%s set to '%s'." % (self.__map_field__(field), text), msgid))
            else:
                self.broker.deliver(session_id, ltd.encode_co_output("%s unset." % self.__map_field__(field), msgid))

            scope.complete()

    @staticmethod
    def __map_field__(field):
        name = None

        if field == "real_name":
            name = "Real name"
        elif field == "address":
            name = "Address"
        elif field == "phone":
            name = "Phone number"
        elif field == "email":
            name = "E-Mail"
        elif field == "text":
            name = "Message text"
        elif field == "www":
            name = "Website"
        else:
            raise ValueError

        return name

    @staticmethod
    def __validate_field__(field, text):
        valid = False

        if field == "real_name":
            valid = validate.is_valid_realname(text)
        elif field == "address":
            valid = validate.is_valid_address(text)
        elif field == "phone":
            valid = validate.is_valid_phone(text)
        elif field == "email":
            valid = validate.is_valid_email(text)
        elif field == "text":
            valid = validate.is_valid_text(text)
        elif field == "www":
            valid = validate.is_valid_www(text)
        else:
            raise ValueError

        return valid

    def delete(self, session_id, password, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise LtdErrorException("You must be registered to delete your entry.")

        if not password:
            raise LtdErrorException("Usage: /delete password")

        with self.db_connection.enter_scope() as scope:
            if not self.nickdb.check_password(scope, state.nick, password):
                raise LtdErrorException("Password incorrect.")

            self.nickdb.delete(scope, state.nick)

            self.broker.deliver(session_id, ltd.encode_co_output("Record deleted.", msgid))

            self.session.update(session_id, authentication=False)

            scope.complete()

    def whois(self, session_id, nick, msgid=""):
        if not nick:
            raise LtdErrorException("Usage: /whois nickname")

        with self.db_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, nick):
                raise LtdErrorException("%s not found." % nick)

            signon = self.nickdb.get_signon(scope, nick)
            signoff = self.nickdb.get_signoff(scope, nick)

            details = self.nickdb.lookup(scope, nick)

        login = idle = away = None

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session:
            loggedin_state = self.session.get(loggedin_session)

            login = loggedin_state.address
            idle = loggedin_state.t_recv.elapsed_str()

            if loggedin_state.away:
                away = "%s (since %s)" % (loggedin_state.away, loggedin_state.t_away.elapsed_str())

        msgs = bytearray()

        def display_value(text):
            if not text:
                text = "(None)"

            return text

        msgs.extend(ltd.encode_co_output("Nickname:       %-24s Address:      %s"
                                         % (nick, display_value(login)),
                                         msgid))

        msgs.extend(ltd.encode_co_output("Phone Number:   %-24s Real Name:    %s"
                                         % (display_value(details.phone), display_value(details.real_name)),
                                         msgid))

        msgs.extend(ltd.encode_co_output("Last signon:    %-24s Last signoff: %s"
                                         % (display_value(signon), display_value(signoff)),
                                         msgid))

        if idle:
            msgs.extend(ltd.encode_co_output("Idle:           %s" % idle, msgid))

        if away:
            msgs.extend(ltd.encode_co_output("Away:           %s" % away, msgid))

        msgs.extend(ltd.encode_co_output("E-Mail:         %s" % display_value(details.email), msgid))
        msgs.extend(ltd.encode_co_output("WWW:            %s" % display_value(details.www), msgid))

        if not details.address:
            msgs.extend(ltd.encode_co_output("Street address: (None)", msgid))
        else:
            parts = [p.strip() for p in details.address.split("|")]

            msgs.extend(ltd.encode_co_output("Street address: %s" % parts[0], msgid))

            for part in parts[1:]:
                msgs.extend(ltd.encode_co_output("                %s" % part, msgid))

        if not details.text:
            msgs.extend(ltd.encode_co_output("Text:           (None)", msgid))
        else:
            parts = wrap(details.text, 64)

            msgs.extend(ltd.encode_co_output("Text:           %s" % parts[0], msgid))

            for part in parts[1:]:
                msgs.extend(ltd.encode_co_output("                %s" % part, msgid))

        self.broker.deliver(session_id, msgs)
