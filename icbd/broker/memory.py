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
from logging import Logger
import broker
import di
from textutils import tolower

class Broker(broker.Broker, di.Injected):
    def __init__(self):
        super(Broker, self).__init__()

        self.__sessions = {}
        self.__channels = {}

    def inject(self, log: Logger):
        self.log = log

    def add_session(self, session_id, handler):
        added = session_id not in self.__sessions

        if added:
            self.__sessions[session_id] = handler

        return added

    def session_exists(self, session_id):
        return session_id in self.__sessions

    def remove_session(self, session_id):
        del self.__sessions[session_id]

        for _, channel in self.__channels.items():
            try:
                channel.remove(session_id)
            except KeyError:
                pass

        self.__channels = {k: v for k, v in self.__channels.items() if len(v) > 0}

    @tolower(argname="channel")
    def join(self, session_id, channel):
        members = self.__channels.get(channel, set())
        members.add(session_id)

        self.__channels[channel] = members

        return len(members) == 1

    @tolower(argname="channel")
    def part(self, session_id, channel):
        members = self.__channels.get(channel)
        members.remove(session_id)

        if not members:
            del self.__channels[channel]

        return len(members) > 0

    @tolower(argname="channel")
    def get_subscribers(self, channel):
        return self.__channels[channel]

    def get_channels(self, session_id):
        return [k for k, v in self.__channels.items() if session_id in v]

    def deliver(self, receiver, message):
        if receiver in self.__sessions:
            self.__sessions[receiver](message)
        else:
            self.log.warning("Couldn't deliver message, session not registered.")

    @tolower(argname="channel")
    def to_channel_from(self, sender, channel, message):
        count = 0

        for session_id in self.__channels[channel]:
            if session_id != sender:
                self.deliver(session_id, message)
                count += 1

        return count

    @tolower(argname="channel")
    def to_channel(self, channel, message):
        for session_id in self.__channels[channel]:
            self.deliver(session_id, message)

        return len(self.__channels[channel])

    def broadcast(self, message):
        for session_id in self.__sessions:
            self.deliver(session_id, message)

    def pop(self, session_id):
        msg = None

        if self.__sessions[session_id]:
            msg = self.__sessions[session_id].pop(0)

        return msg
