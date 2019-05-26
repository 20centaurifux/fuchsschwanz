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
from secrets import token_hex
import session

class Store(session.Store):
    def __init__(self):
        self.__m = {}

    def new(self, **kwargs):
        id = token_hex(20)

        self.__m[id] = session.State(**kwargs)

        return id

    def get(self, id):
        return self.__m[id]

    def get_nicks(self):
        return {k: v for k, v in self.__m.items() if v.nick}

    def update(self, id, **kwargs):
        for k, v in kwargs.items():
            setattr(self.__m[id], k, v)

    def set(self, id, state):
        self.__m[id] = state

    def delete(self, id):
        del self.__m[id]

    def find_nick(self, nick):
        session_id = None

        for k, v in self.__m.items():
            if v.nick and v.nick.lower() == nick.lower():
                session_id = k
                break

        return session_id

    def __len__(self):
        return len(self.__m)

    def __iter__(self):
        for k, v in self.__m.items():
            yield k, v
