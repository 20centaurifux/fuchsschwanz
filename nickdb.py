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

@dataclass
class UserDetails:
    real_name: str = None
    phone: str = None
    address: str = None
    email: str = None
    text: str = None
    www: str = None

class NickDb:
    def setup(self, scope):
        raise NotImplementedError

    def create(self, scope, nick):
        raise NotImplementedError

    def exists(self, scope, nick):
        raise NotImplementedError

    def lookup(self, scope, nick):
        raise NotImplementedError

    def update(self, scope, nick, details):
        raise NotImplementedError

    def set_password(self, scope, nick, password):
        raise NotImplementedError

    def check_password(self, scope, nick, password):
        raise NotImplementedError

    def is_secure(self, scope, nick):
        raise NotImplementedError

    def set_secure(self, scope, nick, secure):
        raise NotImplementedError

    def is_admin(self, scope, nick):
        raise NotImplementedError

    def set_admin(self, scope, nick, is_admin):
        raise NotImplementedError

    def delete(self, scope, nick):
        raise NotImplementedError
