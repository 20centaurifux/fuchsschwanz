"""
    project............: Fuchsschwanz
    description........: icbd server implementation
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
from secrets import token_hex
from utils import Timer, TimeoutTable
from datetime import datetime
from typing import NewType

class BeepMode(Enum):
    OFF = 0
    ON = 1
    VERBOSE = 2

@dataclass
class State:
    loginid: str = None
    ip: str = None
    host: str = None
    nick: str = None
    group: str = None
    authenticated: bool = False
    signon: datetime = datetime.utcnow()
    t_recv: Timer = None
    beep: BeepMode = BeepMode.ON
    away: str = None
    t_away: Timer = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

AwayTimeoutTable = NewType("AwayTimeoutTable", TimeoutTable)

class Store:
    def new(self, *kwargs):
        raise NotImplementedError

    def get(self, id):
        raise NotImplementedError

    def get_logins(self):
        raise NotImplementedError

    def update(self, id, **kwargs):
        raise NotImplementedError

    def set(self, id, state):
        raise NotImplementedError

    def delete(self, id):
        raise NotImplementedError

    def find_nick(self, nick):
        raise NotImplementedError

class MemoryStore(Store):
    def __init__(self):
        self.__m = {}

    def new(self, **kwargs):
        id = token_hex(20)

        self.__m[id] = State(**kwargs)

        return id

    def get(self, id):
        return self.__m[id]

    def get_logins(self):
        return {k: v for k, v in self.__m.items() if v.nick}

    def update(self, id, **kwargs):
        for k, v in kwargs.items():
            setattr(self.__m[id], k, v)

    def set(self, id, state):
        self.__m[id] = state

    def delete(self, id):
        del self.__m[id]

    def find_nick(self, nick):
        for k, v in self.__m.items():
            if v.nick == nick:
                return k
