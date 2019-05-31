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

class Notifylist:
    def __init__(self):
        self.__nicks = {}
        self.__sites = {}

    def watch_nick(self, nick):
        return self.__watch__(self.__nicks, nick)

    def watch_site(self, site):
        return self.__watch__(self.__sites, site)

    def __watch__(self, m, name):
        k = name.lower()

        added = not k in m

        if added:
            m[k] = name
        else:
            del m[k]

        return added

    def nick_watched(self, nick):
        return nick.lower() in self.__nicks

    def site_watched(self, site):
        return site.lower() in self.__sites

    def empty(self):
        return not (self.__nicks or self.__sites)

    @property
    def nicks(self):
        return sorted([n for n in self.__nicks.values()])

    @property
    def sites(self):
        return sorted([s for s in self.__sites.values()])
