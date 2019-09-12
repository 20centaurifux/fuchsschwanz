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
from enum import Enum
import traceback
import logging
import config
import config.json
import log
import sqlite
import mail.sqlite
import mail.smtp
import di

class TransferStatus(Enum):
    SERVER_ERROR = 0
    DELIVERED = 1
    MTA_ERROR = 2

class Sendmail(di.Injected):
    def inject(self, config: config.Config, log: logging.Logger, mta: mail.MTA, connection: mail.Connection, queue: mail.Queue):
        self.__config = config
        self.__log = log
        self.__mta = mta
        self.__connection = connection
        self.__queue = queue

        self.__prepare_db__()

    def send(self):
        read_next = True

        while read_next:
            with self.__connection.enter_scope() as scope:
                msg = self.__queue.head(scope)

            if msg:
                self.__send_mail__(msg)
            else:
                read_next = False

    def __send_mail__(self, msg):
        self.__log.info("Sending mail: %s", msg)

        status = TransferStatus.SERVER_ERROR

        try:
            self.__mta.start_session()

            try:
                self.__mta.send(msg.receiver, msg.subject, msg.body)

                status = TransferStatus.DELIVERED
            except:
                self.__log.warning(traceback.format_exc())

                status = TransferStatus.MTA_ERROR

            self.__mta.end_session()
        except:
            self.__log.error(traceback.format_exc())

        if status != TransferStatus.SERVER_ERROR:
            with self.__connection.enter_scope() as scope:
                if status == TransferStatus.DELIVERED:
                    self.__log.debug("Marking mail delivered.")

                    self.__queue.delivered(scope, msg.msgid)
                else:
                    self.__log.debug("Incrementing MTA error counter.")

                    self.__queue.mta_error(scope, msg.msgid)

                scope.complete()

    def cleanup(self):
        with self.__connection.enter_scope() as scope:
            self.__log.debug("Cleaning up mail queue.")

            self.__queue.cleanup(scope)

            scope.complete()

    def __prepare_db__(self):
        with self.__connection.enter_scope() as scope:
            self.__queue.setup(scope)

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
    logger = log.new_logger("mail", log.Verbosity.DEBUG, log.SIMPLE_TEXT_FORMAT)

    logger.info("Starting mail process with interval %.2f.", preferences.mail_interval)

    container = di.default_container

    container.register(config.Config, preferences)
    container.register(logging.Logger, logger)
    container.register(mail.Connection, sqlite.Connection(preferences.database_filename))

    container.register(mail.Queue, mail.sqlite.Queue(preferences.mail_ttl,
                                                     preferences.mail_max_errors,
                                                     preferences.mail_retry_timeout))

    container.register(mail.MTA, mail.smtp.MTA(preferences.smtp_hostname,
                                               preferences.smtp_port,
                                               preferences.smtp_ssl_enabled,
                                               preferences.smtp_start_tls,
                                               preferences.smtp_sender,
                                               preferences.smtp_username,
                                               preferences.smtp_password))

    mailer = Sendmail()

    cleanup_f = asyncio.ensure_future(asyncio.sleep(0))
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

    class Action(Enum):
        NONE = 0
        SEND = 1
        CLEANUP = 2
        QUIT = 3

    while not quit:
        done, _ = await asyncio.wait([cleanup_f, timeout_f, signal_f], return_when=asyncio.FIRST_COMPLETED)

        action = Action.NONE

        for f in done:
            if f is signal_f:
                sig = signal_f.result()

                logger.debug("%s received.", sig)

                action = Action.SEND

                if sig == signal.SIGTERM:
                    action = Action.QUIT
            elif f is cleanup_f:
                action = Action.CLEANUP
            else:
                action = Action.SEND

        if action == Action.SEND:
            mailer.send()
        elif action == Action.CLEANUP:
            mailer.cleanup()
        elif action == Action.QUIT:
            quit = True

        for f in done:
            if f is cleanup_f:
                cleanup_f = asyncio.ensure_future(asyncio.sleep(preferences.mail_cleanup_interval))
            if f is timeout_f:
                timeout_f = asyncio.ensure_future(asyncio.sleep(preferences.mail_interval))
            elif f is signal_f:
                signal_f = asyncio.ensure_future(signal_q.get())

    logger.info("Stopped.")

if __name__ == "__main__":
    try:
        opts = get_opts(sys.argv[1:])

        asyncio.run(run(opts))

    except getopt.GetoptError as ex:
        print(str(ex))
