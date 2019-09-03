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
from string import Template
from actions import Injected
import validate
import confirmation
import passwordreset
import mail
import template
import ltd
from textutils import hide_chars
from exception import LtdResponseException, LtdErrorException, LtdStatusException

class Registration(Injected):
    def __init__(self):
        super().__init__()

        self.confirmation_connection = self.resolve(confirmation.Connection)
        self.confirmation = self.resolve(confirmation.Confirmation)

        self.password_reset_connection = self.resolve(passwordreset.Connection)
        self.password_reset = self.resolve(passwordreset.PasswordReset)

        self.mail_queue_connection = self.resolve(mail.Connection)
        self.mail_queue = self.resolve(mail.EmailQueue)

        self.template = self.resolve(template.Template)

    def register(self, session_id, password):
        self.log.debug("Starting user registration.")

        state = self.session.get(session_id)

        registered = False

        with self.nickdb_connection.enter_scope() as scope:
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
        with self.nickdb_connection.enter_scope() as scope:
            state = self.session.get(session_id)

            self.nickdb.set_lastlogin(scope, state.nick, state.loginid, state.host)

            now = datetime.utcnow()

            self.nickdb.set_signon(scope, state.nick, now)

            self.session.update(session_id, signon=now, authenticated=True)

            self.broker.deliver(session_id, ltd.encode_status_msg("Register", "Nick registered."))

            self.reputation.good(session_id)

            scope.complete()

    def notify_messagebox(self, session_id):
        with self.nickdb_connection.enter_scope() as scope:
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

        is_reset_code = False

        with self.password_reset_connection.enter_scope() as scope:
            is_reset_code = self.password_reset.has_pending_request(scope, state.nick, old_pwd, self.config.timeouts_password_reset_code)

        with self.nickdb_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, state.nick):
                raise LtdErrorException("Authorization failure.")

            if not is_reset_code:
                self.log.debug("Validating password.")

                if not state.authenticated:
                    self.reputation.critical(session_id)

                    raise LtdErrorException("You must be registered to change your password.")

                if not self.nickdb.check_password(scope, state.nick, old_pwd):
                    self.reputation.fatal(session_id)

                    raise LtdErrorException("Authorization failure.")
            else:
                self.log.debug("Password reset code found: %s", old_pwd)

            if not validate.is_valid_password(new_pwd):
                raise LtdStatusException("Pass",
                                         "Password format not valid. Password length must be between %d and %d characters."
                                         % (validate.PASSWORD_MIN, validate.PASSWORD_MAX))

            self.nickdb.set_password(scope, state.nick, new_pwd)

            self.broker.deliver(session_id, ltd.encode_status_msg("Pass", "Password changed."))

            scope.complete()

        if is_reset_code:
            with self.password_reset_connection.enter_scope() as scope:
                self.password_reset.delete_requests(scope, state.nick)

                scope.complete()

    def reset_password(self, session_id, email):
        self.log.debug("Resetting user password.")

        if not email:
            raise LtdErrorException("Usage: /newpasswd {confirmed email address}")

        if not validate.is_valid_email(email):
            raise LtdErrorException("Wrong email address.")

        state = self.session.get(session_id)
        details = None

        with self.nickdb_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, state.nick):
                self.reputation.warning(session_id)

                raise LtdErrorException("Nick not registered.")

            if not self.nickdb.is_email_confirmed(scope, state.nick):
                self.reputation.warning(session_id)

                raise LtdErrorException("Nick has no confirmed email address.")

            details = self.nickdb.lookup(scope, state.nick)

            if details.email.lower() != email.lower():
                self.reputation.critical(session_id)

                raise LtdErrorException("Wrong email address.")

        code = None

        with self.password_reset_connection.enter_scope() as scope:
            pending = self.password_reset.count_pending_requests(scope, state.nick, self.config.timeouts_password_reset_request)

            if pending > 0:
                self.reputation.critical(session_id)

                raise LtdStatusException("Pass", "Password reset pending, please check your inbox.")

            code = self.password_reset.create_request(scope, state.nick)

            scope.complete()

        self.log.debug("Reset code generated: %s", code)

        with self.mail_queue_connection.enter_scope() as scope:
            text = self.template.load("password_reset_email")
            tpl = Template(text)
            body = tpl.substitute(nick=state.nick, code=code)

            self.mail_queue.enqueue(scope, details.email, "Password reset", body)

            self.broker.deliver(session_id, ltd.encode_co_output("Email sent."))

            scope.complete()

    def set_security_mode(self, session_id, enabled, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise LtdErrorException("You must be registered to change your security.")

        with self.nickdb_connection.enter_scope() as scope:
            self.nickdb.set_secure(scope, state.nick, enabled)

            if enabled:
                self.broker.deliver(session_id, ltd.encode_co_output("Security set to password required.", msgid))
            else:
                self.broker.deliver(session_id, ltd.encode_co_output("Security set to automatic.", msgid))

            scope.complete()

    def set_protected(self, session_id, protected, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise LtdErrorException("You must be registered to change your protection level.")

        with self.nickdb_connection.enter_scope() as scope:
            self.nickdb.set_protected(scope, state.nick, protected)

            if protected:
                self.broker.deliver(session_id, ltd.encode_co_output("Protection enabled.", msgid))
            else:
                self.broker.deliver(session_id, ltd.encode_co_output("Protection disabled.", msgid))

            scope.complete()

    def change_field(self, session_id, field, text, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise LtdErrorException("You must be registered to change your security.")

        if not self.__validate_field__(field, text):
            raise LtdResponseException("Invalid attribute.",
                                       ltd.encode_co_output("'%s' format not valid." % self.__map_field__(field), msgid))

        with self.nickdb_connection.enter_scope() as scope:
            details = self.nickdb.lookup(scope, state.nick)

            old_val = getattr(details, field)

            if not old_val:
                old_val = ""

            setattr(details, field, text)

            self.nickdb.update(scope, state.nick, details)

            if text:
                self.broker.deliver(session_id, ltd.encode_co_output("%s set to '%s'." % (self.__map_field__(field), text), msgid))
            else:
                self.broker.deliver(session_id, ltd.encode_co_output("%s unset." % self.__map_field__(field), msgid))

            if field == "email" and old_val.lower() != text.lower() and self.nickdb.is_email_confirmed(scope, state.nick):
                self.broker.deliver(session_id, ltd.encode_co_output("Email confirmation revoked.", msgid))

                self.nickdb.set_email_confirmed(scope, state.nick, False)
                self.nickdb.enable_message_forwarding(scope, state.nick, False)

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

    def enable_forwarding(self, session_id, enabled, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise LtdErrorException("You must be registered to change forwarding.")

        with self.nickdb_connection.enter_scope() as scope:
            if not self.nickdb.is_email_confirmed(scope, state.nick):
                raise LtdErrorException("Please confirm your email address first.")

            self.nickdb.enable_message_forwarding(scope, state.nick, enabled)

            if enabled:
                self.broker.deliver(session_id, ltd.encode_co_output("Message forwarding enabled.", msgid))
            else:
                self.broker.deliver(session_id, ltd.encode_co_output("Message forwarding disabled.", msgid))

            scope.complete()

    def request_confirmation(self, session_id):
        self.log.debug("Requesting email confirmation.")

        nick, details = self.__load_details_if_confirmed__(session_id)
        code = None

        with self.confirmation_connection.enter_scope() as scope:
            pending = self.confirmation.count_pending_requests(scope, nick, details.email, self.config.timeouts_confirmation_request)

            if pending > 0:
                self.reputation.warning(session_id)

                raise LtdStatusException("Confirmation", "Confirmation request pending, please check your inbox.")

            code = self.confirmation.create_request(scope, nick, details.email)

            scope.complete()

        self.log.debug("Confirmation code generated: %s", code)

        with self.mail_queue_connection.enter_scope() as scope:
            text = self.template.load("confirm_email")
            tpl = Template(text)
            body = tpl.substitute(nick=nick, code=code)

            self.mail_queue.enqueue(scope, details.email, "Email confirmation", body)

            self.broker.deliver(session_id, ltd.encode_co_output("Confirmation mail sent."))

            scope.complete()

    def confirm(self, session_id, code):
        nick, details = self.__load_details_if_confirmed__(session_id)

        with self.confirmation_connection.enter_scope() as scope:
            if not self.confirmation.has_pending_request(scope, nick, code, details.email, self.config.timeouts_confirmation_code):
                self.reputation.fatal(session_id)

                raise LtdStatusException("Confirmation", "Confirmation failed.")

            self.confirmation.delete_requests(scope, nick)

            scope.complete()

        with self.nickdb_connection.enter_scope() as scope:
            self.nickdb.set_email_confirmed(scope, nick, True)

            scope.complete()

        self.broker.deliver(session_id, ltd.encode_status_msg("Confirmation", "Email address confirmed. Enable message forwarding with /forward."))

    def __load_details_if_confirmed__(self, session_id):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise LtdErrorException("You must be registered to confirm your email address.")

        with self.nickdb_connection.enter_scope() as scope:
            if self.nickdb.is_email_confirmed(scope, state.nick):
                raise LtdResponseException("Already already confirmed.",
                                           ltd.encode_co_output("Email address already confirmed."))

            details = self.nickdb.lookup(scope, state.nick)

            if not details.email:
                raise LtdStatusException("Confirmation", "No email address set.")

            return state.nick, details

    def delete(self, session_id, password, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise LtdErrorException("You must be registered to delete your entry.")

        if not password:
            raise LtdErrorException("Usage: /delete {password}")

        with self.nickdb_connection.enter_scope() as scope:
            if not self.nickdb.check_password(scope, state.nick, password):
                raise LtdErrorException("Password incorrect.")

            self.nickdb.delete(scope, state.nick)

            self.broker.deliver(session_id, ltd.encode_co_output("Record deleted.", msgid))

            self.session.update(session_id, authentication=False)

            scope.complete()

    def whois(self, session_id, nick, msgid=""):
        if not nick:
            raise LtdErrorException("Usage: /whois {nick}")

        state = self.session.get(session_id)

        signon = signoff = protected = details = None

        with self.nickdb_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, nick):
                raise LtdErrorException("%s not found." % nick)

            signon = self.nickdb.get_signon(scope, nick)
            signoff = self.nickdb.get_signoff(scope, nick)
            protected = self.nickdb.is_protected(scope, nick)
            details = self.nickdb.lookup(scope, nick)

        login = idle = away = None

        loggedin_session = self.session.find_nick(nick)

        if loggedin_session:
            loggedin_state = self.session.get(loggedin_session)

            login = loggedin_state.address
            idle = loggedin_state.t_recv.elapsed_str()

            if loggedin_state.away:
                away = "%s (since %s)" % (loggedin_state.away, loggedin_state.t_away.elapsed_str())

        email = None

        if details.email:
            if (session_id == loggedin_session and state.authenticated) or not protected:
                email = details.email
            else:
                email = hide_chars(details.email)

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

        msgs.extend(ltd.encode_co_output("E-Mail:         %s" % display_value(email), msgid))
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
