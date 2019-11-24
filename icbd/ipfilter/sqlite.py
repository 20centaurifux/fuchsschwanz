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
from sqlite_schema import Schema
import ipfilter
import dateutils
from textutils import tolower

class Storage(ipfilter.Storage):
    def setup(self, scope):
        Schema().upgrade(scope)

    def load_deny_filters(self, scope):
        now = dateutils.timestamp()

        cur = scope.get_handle()
        cur.execute("select Expression, Lifetime from IPFilter where Action=1 and (Lifetime=-1 or Lifetime>=?)", (now,))

        return [(ipfilter.Factory.create(row["Expression"]), row["Lifetime"]) for row in cur]

    def deny_until(self, scope, filter, timestamp):
        cur = scope.get_handle()
        cur.execute("replace into IPFilter (Expression, Action, Lifetime) values (?, 1, ?)", (filter.expression, timestamp))

    @tolower(argname="expr")
    def deny_filter_exists(self, scope, expr):
        now = dateutils.timestamp()

        cur = scope.get_handle()
        cur.execute("select count(*) from IPFilter where Expression=? and Action=1 and (Lifetime=-1 or Lifetime>=?)", (expr, now))

        return bool(cur.fetchone()[0])

    @tolower(argname="expr")
    def remove(self, scope, expr):
        cur = scope.get_handle()
        cur.execute("delete from IPFilter where Expression=?", (expr,))

    def flush(self, scope):
        cur = scope.get_handle()
        cur.execute("delete from IPFilter")

    def cleanup(self, scope):
        now = dateutils.timestamp()

        cur = scope.get_handle()
        cur.execute("delete from IPFilter where Lifetime>-1 and Lifetime<?", (now,))
