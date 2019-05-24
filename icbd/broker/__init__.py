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

class Broker:
    def add_session(self, session_id, handler):
        raise NotImplementedError

    def session_exists(self, session_id):
        raise NotImplementedError

    def remove_session(self, session_id):
        raise NotImplementedError

    def join(self, session_id, channel):
        raise NotImplementedError

    def part(self, session_id, channel):
        raise NotImplementedError

    def get_subscribers(self, channel):
        raise NotImplementedError

    def get_channels(self, session_id):
        raise NotImplementedError

    def deliver(self, receiver, message):
        raise NotImplementedError

    def to_channel(self, channel, message):
        raise NotImplementedError

    def to_channel_from(self, sender, channel, message):
        raise NotImplementedError

    def broadcast(self, message):
        raise NotImplementedError
