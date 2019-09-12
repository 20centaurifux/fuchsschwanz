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
from datetime import datetime
from uuid import UUID
import database

@dataclass
class Email:
    msgid: UUID
    receiver: str
    subject: str
    body: str

    def __str__(self):
        return "msgid=%s, receiver=%s, subject=%s" % (self.msgid,
                                                      self.receiver,
                                                      self.subject)

Connection = NewType("Connection", database.Connection)

class SinkListener:
    def put(self, receiver, subject, body): pass

class Sink:
    def setup(self, scope):
        raise NotImplementedError

    def put(self, scope, receiver, subject, body):
        raise NotImplementedError

    def add_listener(self, listener):
        raise NotImplementedError

    def remove_listener(self, listener):
        raise NotImplementedError

class Queue:
    def setup(self, scope):
        raise NotImplementedError

    def head(self, scope):
        raise NotImplementedError

    def delivered(self, scope, msgid):
        raise NotImplementedError

    def mta_error(self, scope, msgid):
        raise NotImplementedError

    def cleanup(self, scope):
        raise NotImplementedError

class MTA:
    def start_session(self):
        raise NotImplementedError

    def send(self, receiver, subject, body):
        raise NotImplementedError

    def end_session(self):
        raise NotImplementedError
