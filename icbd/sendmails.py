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
import asyncio
import signal
from datetime import datetime
import traceback
import logging
import time
import config
import config.json
import log
import sqlite
import mail.sqlite
import mail.smtp
import di

class Sendmail(di.Injected):
    def inject(self, config: config.Config, log: logging.Logger, mta: mail.MTA, connection: mail.Connection, queue: mail.EmailQueue):
        self.__config = config
        self.__log = log
        self.__mta = mta
        self.__connection = connection
        self.__queue = queue

        self.__prepare_db__()

    def send(self):
        self.__log.debug("Reading batch from mail queue.")

        batch = []

        with self.__connection.enter_scope() as scope:
            batch = self.__queue.next_batch(scope, self.__config.mailer_batch_size)

            self.__log.debug("Filtering batch of size %d." % len(batch))

            if batch:
                batch = self.__filter__(scope, batch)

                scope.complete()

        self.__log.debug("%d message(s) left for sending." % len(batch))

        for msg in batch:
            self.__send_mail__(msg)

    def __filter__(self, scope, batch):
        filtered = []

        for msg in batch:
            delta = datetime.utcnow() - msg.created_at
            elapsed = int(delta.total_seconds())

            if elapsed > self.__config.mailer_ttl or msg.mta_errors >= self.__config.mailer_max_errors:
                self.__log.debug("Mail %s too old or too many transfer failures, removing from queue.", msg.msgid)

                self.__queue.delete(scope, msg.msgid)
            else:
                filtered.append(msg)

        return filtered

    def __send_mail__(self, msg):
        self.__log.info("Sending mail: %s", msg)

        delivered = False
        error = False

        try:
            self.__mta.start_session()

            try:
                self.__mta.send(msg.receiver, msg.subject, msg.body)
                delivered = True
            except:
                self.__log.warning(traceback.format_exc())

                error = True

            self.__mta.end_session()
        except:
            self.__log.error(traceback.format_exc())

        if delivered or error:
            with self.__connection.enter_scope() as scope:
                if delivered:
                    self.__log.debug("Marking mail delivered.")

                    self.__queue.mark_delivered(scope, msg.msgid)
                elif error:
                    self.__log.debug("Incrementing MTA error counter.")

                    self.__queue.mta_error(scope, msg.msgid)

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
    conf = config.from_mapping(mapping)
    logger = log.new_logger(conf.logging_verbosity)

    logger.info("Starting mailer...")

    container = di.default_container

    container.register(config.Config, conf)
    container.register(logging.Logger, logger)
    container.register(mail.Connection, sqlite.Connection(conf.database_filename))
    container.register(mail.EmailQueue, mail.sqlite.EmailQueue())
    container.register(mail.MTA, mail.smtp.MTA(conf.smtp_hostname,
                                               conf.smtp_port,
                                               conf.smtp_ssl_enabled,
                                               conf.smtp_start_tls,
                                               conf.smtp_sender,
                                               conf.smtp_username,
                                               conf.smtp_password))

    logger.debug("Interval: %.2f", conf.mailer_interval)

    mailer = Sendmail()

    timeout_f = asyncio.ensure_future(asyncio.sleep(0))
    signal_q = asyncio.Queue()
    signal_f = asyncio.ensure_future(signal_q.get())

    if hasattr(signal, "SIGUSR1"):
        logger.debug("Registerung SIGUSR1 handler.")

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGUSR1, lambda: signal_q.put_nowait(signal.SIGUSR1))

    while True:
        done, _ = await asyncio.wait([timeout_f, signal_f], return_when=asyncio.FIRST_COMPLETED)

        mailer.send()

        for f in done:
            if f is timeout_f:
                logger.debug("Resetting timeout.")

                timeout_f = asyncio.ensure_future(asyncio.sleep(conf.mailer_interval))
            elif f is signal_f:
                logger.debug("Reading from signal queue.")

                signal_f = asyncio.ensure_future(signal_q.get())

if __name__ == "__main__":
    try:
        opts = get_opts(sys.argv[1:])

        asyncio.run(run(opts))

    except getopt.GetoptError as ex:
        print(str(ex))
