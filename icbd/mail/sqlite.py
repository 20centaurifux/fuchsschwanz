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
import uuid
import mail
from sqlite_schema import Schema

class Sink(mail.Sink):
    def __init__(self):
        self.__listeners = []

    def setup(self, scope):
        Schema().upgrade(scope)

    def put(self, scope, receiver, subject, body):
        msgid = uuid.uuid4().hex
        now = int(datetime.utcnow().timestamp())

        cur = scope.get_handle()
        cur.execute("insert into Mail (UUID, Receiver, Subject, Body, Timestamp, DueDate) values (?, ?, ?, ?, ?, ?)",
                    (msgid, receiver, subject, body, now, now))

        for l in self.__listeners:
            l.put(receiver, subject, body)

    def add_listener(self, listener):
        self.__listeners.append(listener)

    def remove_listener(self, listener):
        self.__listeners.remove(listener)

class Queue(mail.Queue):
    def __init__(self, ttl, max_errors, retry_timeout):
        self.__ttl = ttl
        self.__max_errors = max_errors
        self.__retry_timeout = retry_timeout

    def setup(self, scope):
        Schema().upgrade(scope)

    def head(self, scope):
        now = int(datetime.utcnow().timestamp())

        query = """select * from Mail
                     where Sent=0 and %d - Timestamp <= %d and MTAErrors < %d and DueDate <= %d
                     order by MTAErrors, Timestamp asc limit 1""" % (now, self.__ttl, self.__max_errors, now)

        cur = scope.get_handle()
        cur.execute(query)

        m = cur.fetchone()

        msg = None

        if m:
            msg = self.__to_email__(m)

        return msg

    @staticmethod
    def __to_email__(row):
        return mail.Email(msgid=uuid.UUID(row["UUID"]),
                          receiver=row["Receiver"],
                          subject=row["Subject"],
                          body=row["Body"])

    def delivered(self, scope, msgid):
        cur = scope.get_handle()
        cur.execute("update Mail set Sent=1 where UUID=?", (msgid.hex,))

    def mta_error(self, scope, msgid):
        now = int(datetime.utcnow().timestamp())
        due_date = now + self.__retry_timeout

        cur = scope.get_handle()
        cur.execute("update Mail set MTAErrors=MTAErrors + 1, DueDate = ? where UUID=?", (due_date, msgid.hex,))

    def cleanup(self, scope):
        now = int(datetime.utcnow().timestamp())

        cur = scope.get_handle()
        cur.execute("delete from Mail where %d - Timestamp > %d" % (now, self.__ttl))
