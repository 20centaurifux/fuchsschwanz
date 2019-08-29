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
import secrets
import string
import confirmation
from sqlite_schema import Schema
from textutils import tolower

class Confirmation(confirmation.Confirmation):
    def setup(self, scope):
        Schema().upgrade(scope)

    @tolower(argnames=["nick", "email"])
    def create_request(self, scope, nick, email):
        code = self.__generate_code__()
        now = self.__now__()

        cur = scope.get_handle()
        cur.execute("insert into ConfirmationRequest (Nick, Email, Code, Timestamp) values (?, ?, ?, ?)",
                    (nick, email, code, now))

        return code

    @tolower(argnames=["nick", "email"])
    def count_pending_requests(self, scope, nick, email, ttl):
        timestamp = self.__now__() - ttl

        cur = scope.get_handle()
        cur.execute("select count(*) from ConfirmationRequest where Nick=? and Email=? and Timestamp>=?",
                    (nick, email, timestamp))

        return int(cur.fetchone()[0])

    @tolower(argnames=["nick", "email"])
    def has_pending_request(self, scope, nick, code, email, ttl):
        timestamp = self.__now__() - ttl

        cur = scope.get_handle()
        cur.execute("select count(*) from ConfirmationRequest where Nick=? and Email=? and Code=? and Timestamp>=?",
                    (nick, email, code, timestamp))

        return bool(cur.fetchone()[0])

    @tolower(argname="nick")
    def delete_requests(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("delete from ConfirmationRequest where Nick=?", (nick,))

    @staticmethod
    def __generate_code__():
        return "".join([secrets.choice(string.ascii_letters + string.digits) for _ in range(8)])

    @staticmethod
    def __now__():
        return int(datetime.utcnow().timestamp())
