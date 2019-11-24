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
import ipfilter
import dateutils
from textutils import tolower

class Storage(ipfilter.Storage):
    def __init__(self, storage):
        self.__storage = storage
        self.__deny = {}

    def setup(self, scope):
        self.__storage.setup(scope)

        self.__reload__(scope)

    def load_deny_filters(self, scope):
        return [t for t in self.__deny.values() if t[1] == -1 or t[1] >= dateutils.timestamp()]

    def deny_until(self, scope, filter, timestamp):
        self.__storage.deny_until(scope, filter, timestamp)

        if filter.expression in self.__deny:
            self.__deny[filter.expression][1] = timestamp
        else:
            self.__deny[filter.expression] = [filter, timestamp]

    @tolower(argname="expr")
    def deny_filter_exists(self, scope, expr):
        exists = False

        try:
            lifetime = self.__deny[expr][1]

            exists = lifetime == -1 or lifetime >= dateutils.timestamp()
        except KeyError:
            pass

        return exists

    @tolower(argname="expr")
    def remove(self, scope, expr):
        try:
            del self.__deny[expr]
        except KeyError:
            pass

        self.__storage.remove(scope, expr)

    def flush(self, scope):
        self.__storage.flush(scope)

        self.__deny = {}

    def cleanup(self, scope):
        self.__reload__(scope)

    def __reload__(self, scope):
        self.__storage.cleanup(scope)

        self.__deny = {f.expression: [f, l] for f, l in self.__storage.load_deny_filters(scope)}
