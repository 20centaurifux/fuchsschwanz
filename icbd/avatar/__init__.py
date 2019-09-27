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
from dataclasses import dataclass
import database

def is_available():
    success = True

    try:
        import PIL.Image
        import aalib
    except ImportError:
        success = False

    return success

@dataclass
class Request:
    nick: str
    url: str

    def __str__(self):
        return "%s (%s)" % (self.url, self.nick)

Connection = NewType("Connection", database.Connection)

class WriterListener:
    def put(self, nick, url):
        pass

class Writer:
    def setup(self, scope):
        raise NotImplementedError

    def put(self, scope, nick, url):
        raise NotImplementedError

    def clear(self, scope, nick):
        raise NotImplementedError

    def fetched(self, scope, nick, url, key):
        raise NotImplementedError

    def error(self, scope, nick, url):
        raise NotImplementedError

    def remove_key(self, scope, key):
        raise NotImplementedError

    def cleanup(self, scope):
        raise NotImplementedError

    def add_listener(self, listener):
        raise NotImplementedError

    def remove_listener(self, listener):
        raise NotImplementedError

class Reader:
    def setup(self, scope):
        raise NotImplementedError

    def head(self, scope):
        raise NotImplementedError

    def lookup_key(self, scope, nick):
        raise NotImplementedError

    def dangling_keys(self, scope):
        raise NotImplementedError

class Storage:
    def setup(self):
        raise NotImplementedError

    def store(self, image):
        raise NotImplementedError

    def load(self, key):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError
