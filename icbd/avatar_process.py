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
import getopt
import sys
import os
import asyncio
import signal
import urllib.request
import tempfile
import shutil
import traceback
import logging
import PIL.Image
import io
import config
import config.json
import log
import sqlite
import avatar
import avatar.sqlite
import avatar.fs
import di

class Download(di.Injected):
    def inject(self,
               config: config.Config,
               log: logging.Logger,
               connection: avatar.Connection,
               reader: avatar.Reader,
               writer: avatar.Writer,
               storage: avatar.Storage):
        self.__config = config
        self.__log = log
        self.__connection = connection
        self.__reader = reader
        self.__writer = writer
        self.__storage = storage

        self.__prepare_db__()

    def fetch(self):
        self.__log.debug("Processing queue.")

        read_next = True

        while read_next:
            with self.__connection.enter_scope() as scope:
                request = self.__reader.head(scope)

            if request:
                self.__import__(request)
            else:
                read_next = False

    def __import__(self, request):
        key = None

        try:
            self.__log.info("Downloading avatar %s", request.url)

            f = self.__download__(request.url)

            self.__log.debug("Testing image.")

            png = self.__to_thumbnail__(f)

            self.__log.debug("Storing image.")

            key = self.__storage.store(png)

            self.__log.debug("Image stored successfully, key=%s.", key)
        except:
            self.__log.warning(traceback.format_exc())

        with self.__connection.enter_scope() as scope:
            if key:
                self.__log.debug("Avatar imported successfully.")

                self.__writer.fetched(scope, request.nick, request.url, key)
            else:
                self.__log.debug("Incrementing import error counter.")

                self.__writer.error(scope, request.nick, request.url)

            scope.complete()

    def __download__(self, url):
        with urllib.request.urlopen(url) as req:
            f = io.BytesIO()

            block = req.read(4096)
            total = 0

            while block:
                total += len(block)

                if total > self.__config.avatar_max_file_size:
                    raise OverflowError("Image exceeds maximum file size.")

                f.write(block)

                block = req.read(4096)

            f.seek(0, io.SEEK_SET)

            return f

    def __to_thumbnail__(self, f):
        image = PIL.Image.open(f)

        width, height = image.size

        self.__log.debug("Image read successfully, format=%s, size=%dx%d.", image.format, width, height)

        if width > self.__config.avatar_max_width or height > self.__config.avatar_max_height:
            raise OverflowError("Image exceeds maximum size.")

        image.thumbnail((self.__config.avatar_thumbnail_width, self.__config.avatar_thumbnail_height))

        png = io.BytesIO()

        image.save(png, "PNG")

        png.seek(0, io.SEEK_SET)

        return png

    def __prepare_db__(self):
        with self.__connection.enter_scope() as scope:
            self.__reader.setup(scope)
            self.__writer.setup(scope)

            scope.complete()

def get_opts(argv):
    options, _ = getopt.getopt(argv, 'c:d:', ['config=', 'data-dir='])
    m = {}

    for opt, arg in options:
        if opt in ('-c', '--config'):
            m["config"] = arg

    if not m.get("config"):
        raise getopt.GetoptError("--config option is mandatory")

    return m

async def run(opts):
    mapping = config.json.load(opts["config"])
    preferences = config.from_mapping(mapping)
    logger = log.new_logger("avatar", log.Verbosity.DEBUG, log.SIMPLE_TEXT_FORMAT)

    logger.info("Starting avatar process with interval %.2f.", preferences.avatar_interval)

    container = di.default_container

    container.register(config.Config, preferences)
    container.register(logging.Logger, logger)
    container.register(avatar.Connection, sqlite.Connection(preferences.database_filename))
    container.register(avatar.Reader, avatar.sqlite.Reader())
    container.register(avatar.Writer, avatar.sqlite.Writer(preferences.avatar_reload_timeout,
                                                           preferences.avatar_retry_timeout))
    container.register(avatar.Storage, avatar.fs.Storage(preferences.avatar_directory,
                                                         preferences.avatar_ascii_width,
                                                         preferences.avatar_ascii_height))

    download = Download()

    timeout_f = asyncio.ensure_future(asyncio.sleep(1))
    signal_q = asyncio.Queue()
    signal_f = asyncio.ensure_future(signal_q.get())

    if os.name == "posix":
        loop = asyncio.get_event_loop()

        logger.debug("Registerung SIGTERM handler.")

        loop.add_signal_handler(signal.SIGTERM, lambda: signal_q.put_nowait(signal.SIGTERM))

        logger.debug("Registerung SIGINT handler.")

        loop.add_signal_handler(signal.SIGINT, lambda: None)

        logger.debug("Registerung SIGUSR1 handler.")

        loop.add_signal_handler(signal.SIGUSR1, lambda: signal_q.put_nowait(signal.SIGUSR1))
    else:
        logger.warning("No signal handlers registered.")

    quit = False

    while not quit:
        done, _ = await asyncio.wait([timeout_f, signal_f], return_when=asyncio.FIRST_COMPLETED)

        trigger = True
        quit = False

        for f in done:
            if f is signal_f:
                sig = signal_f.result()

                logger.debug("%s received.", sig)

                trigger = (sig == signal.SIGUSR1)
                quit = (sig == signal.SIGTERM)
            else:
                trigger = True

        if trigger:
            download.fetch()

        for f in done:
            if f is timeout_f:
                timeout_f = asyncio.ensure_future(asyncio.sleep(preferences.avatar_interval))
            elif f is signal_f:
                signal_f = asyncio.ensure_future(signal_q.get())

    logger.info("Stopped.")

if __name__ == "__main__":
    try:
        opts = get_opts(sys.argv[1:])

        asyncio.run(run(opts))

    except getopt.GetoptError as ex:
        print(str(ex))
