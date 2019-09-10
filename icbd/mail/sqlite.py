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

class EmailQueue(mail.EmailQueue):
    def __init__(self):
        self.__listeners = []

    def setup(self, scope):
        Schema().upgrade(scope)

    def enqueue(self, scope, receiver, subject, body):
        msgid = uuid.uuid4().hex
        now = self.__now__()

        cur = scope.get_handle()
        cur.execute("insert into Mail (UUID, Receiver, Subject, Body, Timestamp) values (?, ?, ?, ?, ?)",
                    (msgid, receiver, subject, body, now))

        for l in self.__listeners:
            l.enqueued(receiver, subject, body)

    def next_mail(self, scope):
        cur = scope.get_handle()
        cur.execute("select * from Mail where Sent=0 order by Timestamp asc limit 1")

        m = cur.fetchone()

        msg = None

        if m:
            msg = self.__to_email__(m)

        return msg

    def next_batch(self, scope, max_size=None):
        cur = scope.get_handle()

        query = "select * from Mail where Sent=0 order by MTAErrors, Timestamp asc"

        if max_size:
            query += " limit %d" % max_size

        cur.execute(query)

        return [self.__to_email__(m) for m in cur.fetchall()]

    @staticmethod
    def __to_email__(row):
        return mail.Email(msgid=uuid.UUID(row["uuid"]),
                          created_at=datetime.fromtimestamp(row["Timestamp"]),
                          receiver=row["Receiver"],
                          subject=row["Subject"],
                          body=row["Body"],
                          mta_errors=row["MTAErrors"])

    def mark_delivered(self, scope, msgid):
        cur = scope.get_handle()
        cur.execute("update Mail set Sent=1 where uuid=?", (msgid.hex,))

        for l in self.__listeners:
            l.delivered(msgid)

    def mta_error(self, scope, msgid):
        cur = scope.get_handle()
        cur.execute("update Mail set MTAErrors=MTAErrors + 1 where uuid=?", (msgid.hex,))

        for l in self.__listeners:
            l.mta_error(msgid)

    def delete(self, scope, msgid):
        cur = scope.get_handle()
        cur.execute("delete from Mail where uuid=?", (msgid.hex,))

        for l in self.__listeners:
            l.deleted(msgid)

    def add_listener(self, listener):
        self.__listeners.append(listener)

    def remove_listener(self, listener):
        self.__listeners.remove(listener)

    @staticmethod
    def __now__():
        return int(datetime.utcnow().timestamp())
