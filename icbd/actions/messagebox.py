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
import validate
from exception import TldErrorException

class MessageBox(Injected):
    def send_message(self, session_id, receiver, text):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise TldErrorException("You must be registered to write a message.")

        if not validate.is_valid_nick(receiver):
            raise TldErrorException("%s is not a valid nick name." % receiver)

        if not validate.is_valid_message(text):
            raise TldErrorException("Message text not valid. Length has to be between %d and %d characters."
                                    % (validate.MESSAGE_MIN, validate.MESSAGE_MAX))

        with self.db_connection.enter_scope() as scope:
            if not self.nickdb.exists(scope, receiver):
                raise TldErrorException("%s is not registered." % receiver)

            count = self.nickdb.count_messages(scope, receiver) + 1
            limit = self.nickdb.get_mbox_limit(scope, receiver)

            loggedin_session = self.session.find_nick(receiver)

            if count > limit:
                if loggedin_session and not self.notification_table.is_alive(loggedin_session, "mbox_full"):
                    self.broker.deliver(loggedin_session, tld.encode_str("e", "User mailbox is full."))
                    self.notification_table.set_alive(loggedin_session, "mbox_full", self.config.timeouts_mbox_full_message)

                raise TldErrorException("User mailbox full.")

            uuid = self.nickdb.add_message(scope, receiver, state.nick, text)

            self.broker.deliver(session_id, tld.encode_status_msg("Message", "Message '%s' saved." % uuid))

            if loggedin_session:
                self.broker.deliver(session_id, tld.encode_status_msg("Warning", "%s is logged in now." % receiver))
                self.broker.deliver(loggedin_session,
                                    tld.encode_status_msg("Message", "You have %d message%s." % (count, "" if count == 1 else "s")))

                if count == limit and not self.notification_table.is_alive(loggedin_session, "mbox_full"):
                    self.broker.deliver(loggedin_session, tld.encode_str("e", "User mailbox is full."))
                    self.notification_table.set_alive(loggedin_session, "mbox_full", self.config.timeouts_mbox_full_message)

            scope.complete()

    def read_messages(self, session_id, msgid=""):
        state = self.session.get(session_id)

        if not state.authenticated:
            raise TldErrorException("You must be registered to read any messages.")

        with self.db_connection.enter_scope() as scope:
            if self.nickdb.count_messages(scope, state.nick) == 0:
                raise TldErrorException("No messages.")

            for msg in self.nickdb.get_messages(scope, state.nick):
                self.broker.deliver(session_id, tld.encode_co_output("Message left at %s (UTC)." % msg.date, msgid))

                e = tld.Encoder("c")

                e.add_field_str(msg.sender, append_null=False)
                e.add_field_str(msg.text, append_null=True)

                self.broker.deliver(session_id, e.encode())

                self.nickdb.delete_message(scope, msg.uuid)

            scope.complete()

            self.notification_table.remove_entry(session_id, "mbox_full")
