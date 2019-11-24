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
import confirmation
from sqlite_schema import Schema
from textutils import tolower, make_password
import dateutils

class Confirmation(confirmation.Confirmation):
    def setup(self, scope):
        Schema().upgrade(scope)

    @tolower(argnames=["nick", "email"])
    def create_request(self, scope, nick, email):
        code = make_password(8)
        now = dateutils.timestamp()

        cur = scope.get_handle()
        cur.execute("insert into ConfirmationRequest (Nick, Email, Code, Timestamp) values (?, ?, ?, ?)",
                    (nick, email, code, now))

        return code

    @tolower(argnames=["nick", "email"])
    def count_pending_requests(self, scope, nick, email, ttl):
        timestamp = dateutils.timestamp() - ttl

        cur = scope.get_handle()
        cur.execute("select count(*) from ConfirmationRequest where Nick=? and Email=? and Timestamp>=?",
                    (nick, email, timestamp))

        return int(cur.fetchone()[0])

    @tolower(argnames=["nick", "email"])
    def has_pending_request(self, scope, nick, code, email, ttl):
        timestamp = dateutils.timestamp() - ttl

        cur = scope.get_handle()
        cur.execute("select count(*) from ConfirmationRequest where Nick=? and Email=? and Code=? and Timestamp>=?",
                    (nick, email, code, timestamp))

        return bool(cur.fetchone()[0])

    @tolower(argname="nick")
    def delete_requests(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("delete from ConfirmationRequest where Nick=?", (nick,))

    def cleanup(self, scope, ttl):
        timestamp = dateutils.timestamp() - ttl

        cur = scope.get_handle()
        cur.execute("delete from ConfirmationRequest where Timestamp<?", (timestamp,))
