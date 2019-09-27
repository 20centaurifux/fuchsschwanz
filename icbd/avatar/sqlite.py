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
import avatar
from sqlite_schema import Schema
from textutils import tolower
import dateutils

class Writer(avatar.Writer):
    def __init__(self, refresh_timeout, retry_timeout, max_errors, error_timeout):
        self.__listeners = []
        self.__refresh_timeout = refresh_timeout
        self.__retry_timeout = retry_timeout
        self.__max_errors = max_errors
        self.__error_timeout = error_timeout

    def setup(self, scope):
        Schema().upgrade(scope)

    @tolower(argname="nick")
    def put(self, scope, nick, url):
        now = dateutils.now()

        cur = scope.get_handle()

        cur.execute("update Avatar set Active=0 where Nick=?", (nick,))

        cur.execute("select count(*) from Avatar where Nick=? and url=?", (nick, url))

        count = cur.fetchone()[0]

        if count:
            cur.execute("update Avatar set Active=1, DueDate=?, Errors=0 where Nick=? and Url=?", (now, nick, url))
        else:
            cur.execute("insert into Avatar (Nick, Active, DueDate, Url) values (?, 1, ?, ?)", (nick, now, url))

        for l in self.__listeners:
            l.put(nick, url)

    @tolower(argname="nick")
    def fetched(self, scope, nick, url, key):
        now = dateutils.now()
        due_date = now + self.__refresh_timeout

        cur = scope.get_handle()
        cur.execute("update Avatar set Hash=?, DueDate=?, Errors=0 where nick=? and Url=?", (key, due_date, nick, url))

    @tolower(argname="nick")
    def error(self, scope, nick, url):
        cur = scope.get_handle()

        cur.execute("select Errors from Avatar where Nick=? and Url=?", (nick, url))

        row = cur.fetchone()

        if row:
            errors = row[0]
            now = dateutils.now()

            if errors == self.__max_errors:
                due_date = now + self.__error_timeout
            else:
                due_date = now + self.__retry_timeout
                errors += 1

            cur.execute("update Avatar set Errors=?, DueDate=? where Nick=? and Url=?", (errors, due_date, nick, url))

    def remove_key(self, scope, key):
        cur = scope.get_handle()
        cur.execute("delete from Avatar where Hash=?", (key,))

    def cleanup(self, scope):
        cur = scope.get_handle()
        cur.execute("delete from Avatar where Active=0")

    @tolower(argname="nick")
    def clear(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("update Avatar set Active=0 where Nick=?", (nick,))

    def add_listener(self, listener):
        self.__listeners.append(listener)

    def remove_listener(self, listener):
        self.__listeners.remove(listener)

class Reader(avatar.Reader):
    def setup(self, scope):
        Schema().upgrade(scope)

    def head(self, scope):
        now = dateutils.now()

        cur = scope.get_handle()

        query = """select * from Avatar
                     where DueDate <= %d and Active = 1
                     order by Errors, DueDate asc limit 1""" % (now,)

        cur.execute(query)

        m = cur.fetchone()

        msg = None

        if m:
            msg = self.__to_request__(m)

        return msg

    @staticmethod
    def __to_request__(row):
        return avatar.Request(nick=row["Nick"], url=row["Url"])

    @tolower(argname="nick")
    def lookup_key(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select Hash from Avatar where Nick=? and Active=1 and Hash not null", (nick,))

        result = cur.fetchone()

        if result:
            result = result[0]

        return result

    def dangling_keys(self, scope):
        cur = scope.get_handle()
        cur.execute("""select Hash, SUM(Active) as InUse
                         from (select Hash, Active from Avatar where Hash is not null group by Hash, Active)
                         group by Hash
                         having InUse=0""")

        return [row[0] for row in cur]
