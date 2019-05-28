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

@dataclass
class Entry:
    display_name: str
    public: bool = False
    private: bool = False

    def __str__(self):
        return self.display_name

class Hushlist:
    def __init__(self):
        self.__nicks = {}
        self.__sites = {}

    def hush_nick_public(self, nick):
        return self.__hush__(self.__nicks, nick, public=True)

    def hush_nick_private(self, nick):
        return self.__hush__(self.__nicks, nick, public=False)

    def hush_site_public(self, site):
        return self.__hush__(self.__sites, site, public=True)

    def hush_site_private(self, site):
        return self.__hush__(self.__sites, site, public=False)

    def __hush__(self, m, name, public):
        k = name.lower()
        entry = m.get(k, Entry(display_name=name))

        attr = "public" if public else "private"
        new_val = not getattr(entry, attr)

        setattr(entry, attr, new_val)

        if entry.public or entry.private:
            m[k] = entry
        else:
            del m[k]

        return new_val

    def nick_public_hushed(self, nick):
        return self.__hushed__(self.__nicks, nick, public=True)

    def nick_private_hushed(self, nick):
        return self.__hushed__(self.__nicks, nick, public=False)

    def empty(self):
        return not (self.__nicks or self.__sites)

    def site_public_hushed(self, name):
        return self.__hushed__(self.__sites, name, public=True)

    def site_private_hushed(self, name):
        return self.__hushed__(self.__sites, name, public=False)

    def __hushed__(self, m, name, public):
        entry = m.get(name.lower(), Entry(display_name=name))

        return getattr(entry, "public" if public else "private")

    @property
    def nicks(self):
        return sorted(self.__nicks.values(), key=lambda e: e.display_name.lower())

    @property
    def sites(self):
        return sorted(self.__sites.values(), key=lambda e: e.display_name.lower())
