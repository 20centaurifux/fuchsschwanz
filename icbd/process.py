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
from subprocess import Popen, DEVNULL, PIPE, TimeoutExpired
import logging
import os
import di
import config
from log.asyncio import LogProtocol

class Process:
    def __init__(self, name):
        self.__name = name
        self.__process = None
        self.__log = di.default_container.resolve(logging.Logger)
        self.__config = di.default_container.resolve(config.Config)

    async def spawn(self, argv):
        args = self.__build_args__(argv)

        self.__log.info("Spawning '%s' process: %s", self.__name, " ".join(args))

        if os.name == "posix":
            self.__process = Popen(args, stdout=DEVNULL, stderr=PIPE)

            loop = asyncio.get_event_loop()

            await loop.connect_read_pipe(lambda: LogProtocol(self.__name, self.__config.logging_verbosity), self.__process.stderr)
        else:
            self.__process = Popen(args, stdout=DEVNULL, stderr=DEVNULL)

            self.__log.warning("Messages of '%s' process will be hidden.", self.__name)

        self.__log.info("Child process started with pid %d.", self.__process.pid)

    def __build_args__(self, argv):
        raise NotImplementedError()

    def signal(self, sig):
        self.__log.debug("Sending %s to child process with pid %d.", sig, self.__process.pid)

        loop = asyncio.get_running_loop()

        loop.call_soon(self.__process.send_signal, sig)

    def kill(self):
        if self.__process:
            self.__log.info("Terminating '%s' process with pid %d.", self.__name, self.__process.pid)

            self.__process.terminate()

            self.__log.info("Waiting for '%s' process.", self.__name)

            try:
                self.__process.communicate(timeout=15)
            except TimeoutExpired:
                self.__log.info("Timeout expired, killing '%s' process.", self.__name)

                self.__process.kill()
                self.__process.communicate()

            self.__log.info("Process %d stopped with exit status %d.", self.__process.pid, self.__process.returncode)
