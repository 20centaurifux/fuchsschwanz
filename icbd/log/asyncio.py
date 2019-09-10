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
import asyncio
from io import StringIO
import logging
import core
import log
import di

class LogProtocol(asyncio.Protocol, di.Injected):
    def __init__(self, name, verbosity=core.Verbosity.DEBUG, level=logging.DEBUG):
        self.__buffer = StringIO()
        self.__verbosity = verbosity
        self.__level = level
        self.__log = log.new_logger(name, verbosity, log.PROTOCOL_FORMAT)

        asyncio.Protocol.__init__(self)
        di.Injected.__init__(self)

    def inject(self, registry: log.Registry):
        registry.register(self.__log)

    def data_received(self, data):
        for c in data.decode("utf-8"):
            if c == "\n":
                msg = self.__buffer.getvalue().strip()

                self.__log.log(self.__level, msg)

                self.__buffer.truncate(0)
                self.__buffer.seek(0)
            else:
                self.__buffer.write(c)
