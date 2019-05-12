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

class Visibility(Enum):
    VISIBLE = 118
    SECRET = 115
    INVISIBLE = 105

    def __init__(self, val):
        super().__init__()

        self.__names = {118: "Visible",
                        115: "Secret",
                        105: "Invisible"}
    def __str__(self):
        return self.__names[self.value]

class Control(Enum):
    def __init__(self, val):
        super().__init__()

        self.__names = {112: "Public",
                        155: "Moderated",
                        114: "Restricted",
                        99: "Controlled"}

    PUBLIC = 112
    MODERATED = 155
    RESTRICTED = 114
    CONTROLLED = 99

    def __str__(self):
        return self.__names[self.value]

class Volume(Enum):
    QUIET = 113
    NORMAL = 110
    LOUD = 108

    def __init__(self, val):
        super().__init__()

        self.__names = {113: "Quiet",
                        110: "Normal",
                        108: "Loud"}

    def __str__(self):
        return self.__names[self.value]

@dataclass
class GroupInfo:
    visibility: Visibility = Visibility.VISIBLE
    control: Control = Control.PUBLIC
    volume: Volume = Volume.LOUD
    moderator: str = None
    topic: str = None

class Store:
    def get(self, name):
        raise NotImplementedError

    def set(self, name, info):
        raise NotImplementedError

    def get_groups(self):
        raise NotImplementedError

    def delete(self, id):
        raise NotImplementedError

class MemoryStore(Store):
    def __init__(self):
        self.__m = {}

    def get(self, name):
        return self.__m.get(name, GroupInfo())

    def get_groups(self):
        return self.__m.keys()

    def set(self, name, info):
        self.__m[name] = info

    def delete(self, id):
        del self.__m[id]
