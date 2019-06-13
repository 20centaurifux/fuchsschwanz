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
from enum import Enum
from datetime import datetime
from typing import NewType
from timer import Timer, TimeoutTable
from hush import Hushlist
from notify import Notifylist

class BeepMode(Enum):
    OFF = 0
    ON = 1
    VERBOSE = 2

class EchoMode(Enum):
    OFF = 0
    ON = 1
    VERBOSE = 2

@dataclass
class State:
    loginid: str = None
    ip: str = None
    host: str = None
    tls: bool = False
    nick: str = None
    group: str = None
    authenticated: bool = False
    signon: datetime = datetime.utcnow()
    t_recv: Timer = None
    t_alive: Timer = None
    t_ping: Timer = None
    beep: BeepMode = BeepMode.ON
    echo: EchoMode = EchoMode.OFF
    away: str = None
    t_away: Timer = None
    hushlist: Hushlist = None
    notifylist: Notifylist = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def loggedin(self):
        return self.nick and self.group

    @property
    def address(self):
        return "%s@%s" % (self.loginid, self.host)

AwayTimeoutTable = NewType("AwayTimeoutTable", TimeoutTable)
NotificationTimeoutTable = NewType("NotificationTimeoutTable", TimeoutTable)

class Store:
    def new(self, **kwargs):
        raise NotImplementedError

    def get(self, id):
        raise NotImplementedError

    def get_nicks(self):
        raise NotImplementedError

    def count_logins(self):
        raise NotImplementedError

    def update(self, id, **kwargs):
        raise NotImplementedError

    def set(self, id, state):
        raise NotImplementedError

    def delete(self, id):
        raise NotImplementedError

    def find_nick(self, nick):
        raise NotImplementedError
