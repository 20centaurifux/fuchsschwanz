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
    def add_session(self, session_id):
        raise NotImplementedError

    def session_exists(self, session_id):
        raise NotImplementedError

    def remove_session(self, session_id):
        raise NotImplementedError

    def assign_nick(self, session_id, nick):
        raise NotImplementedError

    def unassign_nick(self, nick):
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

    def to_nick(self, receiver, message):
        raise NotImplementedError

    def to_channel(self, channel, message):
        raise NotImplementedError

    def to_channel_from(self, sender, channel, message):
        raise NotImplementedError

    def broadcast(self, message):
        raise NotImplementedError

    def pop(self, session_id):
        raise NotImplementedError

class Memory(Broker):
    def __init__(self):
        self.__sessions = {}
        self.__nicks = {}
        self.__channels = {}

    def add_session(self, session_id):
        added = session_id not in self.__sessions

        if added:
            self.__sessions[session_id] = []

        return added

    def session_exists(self, session_id):
        return session_id in self.__sessions

    def remove_session(self, session_id):
        del self.__sessions[session_id]

        for _, c in self.__channels.items():
            try:
                c.remove(session_id)
            except KeyError:
                pass

        self.__channels = {k: v for k, v in self.__channels.items() if len(v) > 0}

        for k, v in self.__nicks.items():
            if v == session_id:
                del self.__nicks[k]
                break

    def assign_nick(self, session_id, nick):
        if not session_id in self.__sessions:
            raise KeyError

        self.__nicks[nick] = session_id

    def unassign_nick(self, nick):
        del self.__nicks[nick]

    def join(self, session_id, channel):
        members = self.__channels.get(channel, set())
        members.add(session_id)

        self.__channels[channel] = members

        return len(members) == 1

    def part(self, session_id, channel):
        members = self.__channels.get(channel)
        members.remove(session_id)

        if len(members) == 0:
            del self.__channels[channel]

        return len(members) > 0

    def get_subscribers(self, channel):
        return self.__channels[channel]

    def get_channels(self, session_id):
        return [k for k, v in self.__channels.items() if session_id in v]

    def deliver(self, receiver, message):
        self.__sessions[receiver].append(message)

    def to_nick(self, nick, message):
        session_id = self.__nicks[nick]
        self.deliver(session_id, message)

    def to_channel_from(self, sender, channel, message):
        count = 0

        for session_id in self.__channels[channel]:
            if session_id != sender:
                self.deliver(session_id, message)
                count += 1

        return count

    def to_channel(self, channel, message):
        for session_id in self.__channels[channel]:
            self.deliver(session_id, message)

        return len(self.__channels[channel])

    def broadcast(self, message):
        for session_id in self.__sessions:
            self.deliver(session_id, message)

    def pop(self, session_id):
        if len(self.__sessions[session_id]) > 0:
            return self.__sessions[session_id].pop(0)
