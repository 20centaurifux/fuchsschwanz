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

import logging
import di

class Reputation(di.Injected):
    def __init__(self):
        super().__init__()

        self.__m = {}

    def inject(self, log: logging.Logger):
        self.log = log

    def add_session(self, session_id):
        self.__m[session_id] = 1.0

    def remove_session(self, session_id):
        del self.__m[session_id]

    def ok(self, session_id):
        self.__add__(session_id, 0.05)

    def good(self, session_id):
        self.__add__(session_id, 0.1)

    def warning(self, session_id):
        self.__add__(session_id, -0.1)

    def critical(self, session_id):
        self.__add__(session_id, -0.2)

    def fatal(self, session_id):
        self.__add__(session_id, -0.4)

    def get(self, session_id):
        return self.__m[session_id]

    def __add__(self, session_id, value):
        old_value = self.__m[session_id]
        new_value = round(max(min(1.0, old_value + value), 0.0), 2)

        if old_value != new_value:
            self.log.debug("Reputation of session '%s' changed from %.2f to %.2f.", session_id, old_value, new_value)

            self.__m[session_id] = new_value
