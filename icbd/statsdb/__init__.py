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
from dataclasses import dataclass
from typing import NewType, Tuple
import database

@dataclass
class Stats:
    signons: int = 0
    boots: int = 0
    drops: int = 0
    idleboots: int = 0
    idlemods: int = 0
    max_logins: int = 0
    max_groups: int = 0
    max_idle: Tuple[str, float] = None

Connection = NewType("Connection", database.Connection)

class StatsDb:
    def setup(self, scope):
        raise NotImplementedError

    def add_signon(self, scope):
        raise NotImplementedError

    def add_boot(self, scope):
        raise NotImplementedError

    def add_drop(self, scope):
        raise NotImplementedError

    def add_idleboot(self, scope):
        raise NotImplementedError

    def add_idlemod(self, scope):
        raise NotImplementedError

    def set_max_logins(self, scope, max_logins):
        raise NotImplementedError

    def set_max_groups(self, scope, max_groups):
        raise NotImplementedError

    def set_max_idle(self, scope, idle_time, idle_nick):
        raise NotImplementedError

    def start(self, scope):
        raise NotImplementedError

    def today(self, scope):
        raise NotImplementedError

    def month(self, scope):
        raise NotImplementedError

    def year(self, scope):
        raise NotImplementedError

    def all(self, scope):
        raise NotImplementedError
