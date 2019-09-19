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
from enum import Enum
import timer

class PendingRequest(Enum):
    NONE = 1
    RESTART = 2
    HALT = 3

class ShutdownListener:
    def shutdown(self, delay, restart):
        raise NotImplementedError

    def cancel_shutdown(self):
        raise NotImplementedError

class Shutdown:
    def __init__(self):
        self.__listeners= []
        self.__pending = PendingRequest.NONE
        self.__timer = None
        self.__delay = 0

    def halt(self, delay):
        self.__pending = PendingRequest.HALT
        self.__timer = timer.Timer()
        self.__delay = delay

        for l in self.__listeners:
            l.shutdown(delay, restart=False)

    def restart(self, delay):
        self.__pending = PendingRequest.RESTART
        self.__timer = timer.Timer()
        self.__delay = delay

        for l in self.__listeners:
            l.shutdown(delay, restart=True)

    def cancel(self):
        self.__pending = PendingRequest.NONE
        self.__timer = None
        self.__delay = 0

        for l in self.__listeners:
            l.cancel_shutdown()

    @property
    def pending_request(self):
        return self.__pending

    @property
    def time_left(self):
        left = None

        if self.__timer:
            left = max(0, self.__delay - self.__timer.elapsed())

        return left

    @property
    def time_left_str(self):
        left_str = None
        left = self.time_left

        if left:
            left_str = timer.Timer.display_str(left)

        return left_str

    def add_listener(self, listener):
        self.__listeners.append(listener)

    def remove_listener(self, listener):
        self.__listeners.remove(listener)
