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
from typing import NewType
import re
import ipaddress
import database
import dateutils

class Filter:
    def __init__(self, expr):
        self.__expr = expr

    def matches(self, login):
        raise NotImplementedError

    @property
    def expression(self):
        return self.__expr.lower()

class Factory:
    @staticmethod
    class Network(Filter):
        def __init__(self, expr):
            Filter.__init__(self, expr)

            loginid, address = Factory.__split_expression__(expr)

            self.__loginid = loginid
            self.__network = ipaddress.ip_network(address)

        def matches(self, login):
            loginid, address = Factory.__split_expression__(login)

            return Factory.__loginid_equals__(self.__loginid, loginid) and ipaddress.ip_address(address) in self.__network

    class Address(Filter):
        def __init__(self, expr):
            Filter.__init__(self, expr)

            loginid, address = Factory.__split_expression__(expr)

            self.__loginid = loginid
            self.__ip = ipaddress.ip_address(address)

        def matches(self, login):
            loginid, address = Factory.__split_expression__(login)

            return Factory.__loginid_equals__(self.__loginid, loginid) and ipaddress.ip_address(address) == self.__ip

    @staticmethod
    def create(expr):
        parts = expr.split("@", 1)
        address = parts[0] if len(parts) == 1 else parts[1]

        f = None

        if re.match(r".+/\d+", address):
            f = Factory.Network(expr)
        else:
            f = Factory.Address(expr)

        return f

    @staticmethod
    def __loginid_equals__(a, b):
        success = True

        if a:
            success = (a.lower() == (b.lower() if b else ""))

        return success

    @staticmethod
    def __split_expression__(expr):
        parts = expr.split("@", 1)

        if len(parts) == 1:
            parts = [None, parts[0]]
        else:
            parts[0] = parts[0].lower()

        return parts

Connection = NewType("Connection", database.Connection)

class Storage:
    def setup(self, scope):
        raise NotImplementedError

    def load_deny_filters(self, scope):
        raise NotImplementedError

    def deny(self, scope, expr, ttl):
        timestamp = -1

        if ttl != -1:
            timestamp = dateutils.timestamp() + ttl

        self.deny_until(scope, expr, timestamp)

    def deny_until(self, scope, filter, timestamp):
        raise NotImplementedError

    def deny_filter_exists(self, scope, expr):
        raise NotImplementedError

    def remove(self, scope, expr):
        raise NotImplementedError

    def flush(self, scope):
        raise NotImplementedError

    def cleanup(self, scope):
        raise NotImplementedError
