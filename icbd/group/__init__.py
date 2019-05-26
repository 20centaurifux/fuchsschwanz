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
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

class Visibility(Enum):
    VISIBLE = 118
    SECRET = 115
    INVISIBLE = 105

    def __init__(self, _):
        super().__init__()

        self.__names = {118: "visible",
                        115: "secret",
                        105: "invisible"}

    def __str__(self):
        return self.__names[self.value]

class Control(Enum):
    def __init__(self, _):
        super().__init__()

        self.__names = {112: "public",
                        109: "moderated",
                        114: "restricted",
                        99: "controlled"}

    PUBLIC = 112
    MODERATED = 109
    RESTRICTED = 114
    CONTROLLED = 99

    def __str__(self):
        return self.__names[self.value]

class Volume(Enum):
    QUIET = 113
    NORMAL = 110
    LOUD = 108

    def __init__(self, _):
        super().__init__()

        self.__names = {113: "quiet",
                        110: "normal",
                        108: "loud"}

    def __str__(self):
        return self.__names[self.value]

@dataclass
class Invitation:
    display_name: str
    registered: bool

    def __init__(self, display_name="", registered=False):
        self.display_name = display_name
        self.registered = registered

    def __str__(self):
        return "%s%s" % (self.display_name, "(r)" if self.registered else "")

@dataclass
class GroupInfo:
    display_name: str = None
    visibility: Visibility = Visibility.VISIBLE
    control: Control = Control.PUBLIC
    volume: Volume = Volume.LOUD
    moderator: str = None
    topic: str = None

    __nicks_inv: Dict[str, Invitation] = field(default_factory=dict)
    __addrs_inv: Dict[str, Invitation] = field(default_factory=dict)
    __talker_nicks: Dict[str, Invitation] = field(default_factory=dict)
    __talker_addrs: Dict[str, Invitation] = field(default_factory=dict)

    def __str__(self):
        return self.display_name

    @property
    def key(self):
        return str(self).lower()

    @property
    def invited_nicks(self):
        return self.__invitations__(self.__nicks_inv)

    @property
    def invited_addresses(self):
        return self.__invitations__(self.__addrs_inv)

    @property
    def talker_nicks(self):
        return self.__invitations__(self.__talker_nicks)

    @property
    def talker_addresses(self):
        return self.__invitations__(self.__talker_addrs)

    def clear_invitations(self):
        self.__nicks_inv.clear()
        self.__addrs_inv.clear()

    def invite_nick(self, nick, registered):
        self.__invite__(self.__nicks_inv, nick, registered)

    def invite_address(self, addr, registered):
        self.__invite__(self.__addrs_inv, addr, registered)

    def nick_invited(self, nick, authenticated):
        return self.__is_invited__(self.__nicks_inv, nick, authenticated)

    def address_invited(self, loginid, ip, host, authenticated):
        return self.__address_is_invited__(self.__addrs_inv, loginid, ip, host, authenticated)

    def cancel_nick(self, nick):
        del self.__nicks_inv[nick.lower()]

    def cancel_address(self, address):
        del self.__addrs_inv[address.lower()]

    def clear_talkers(self):
        self.__talker_nicks.clear()
        self.__talker_addrs.clear()

    def unmute_nick(self, nick, registered):
        self.__invite__(self.__talker_nicks, nick, registered)

    def unmute_address(self, addr, registered):
        self.__invite__(self.__talker_addrs, addr, registered)

    def nick_can_talk(self, nick, authenticated):
        return self.__is_invited__(self.__talker_nicks, nick, authenticated)

    def address_can_talk(self, loginid, ip, host, authenticated):
        return self.__address_is_invited__(self.__talker_addrs, loginid, ip, host, authenticated)

    def mute_nick(self, nick):
        del self.__talker_nicks[nick.lower()]

    def mute_address(self, addr):
        del self.__talker_addrs[addr.lower()]

    @staticmethod
    def __invitations__(m):
        return sorted([str(inv) for inv in m.values()], key=lambda s: s.lower())

    @staticmethod
    def __invite__(m, name, registered):
        k = name.lower()

        added = not k in m

        if added:
            m[k] = Invitation(name, registered)

        return added

    @staticmethod
    def __is_invited__(m, name, authenticated):
        k = name.lower()

        return k in m and (not m[k].registered or authenticated)

    def __address_is_invited__(self, m, loginid, ip, host, authenticated):
        addrs = [ip, host, "%s@%s" % (loginid, ip), "%s@%s" % (loginid, host)]

        return next((True for addr in addrs if self.__is_invited__(m, addr, authenticated)), False)

class Store:
    def get(self, name):
        raise NotImplementedError

    def exists(self, name):
        raise NotImplementedError

    def update(self, info):
        raise NotImplementedError

    def get_groups(self):
        raise NotImplementedError

    def delete(self, id):
        raise NotImplementedError
