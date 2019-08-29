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
from datetime import datetime
import traceback
import time
import config
import config.json
import log
import sqlite
import mail.sqlite
import mta.smtp

class Sendmail:
    def __init__(self, opts):
        mapping = config.json.load(opts["config"])

        self.__config = config.from_mapping(mapping)
        self.__log = log.new_logger(self.__config.logging_verbosity)

        self.__mta = mta.smtp.MTA(self.__config.smtp_hostname,
                                  self.__config.smtp_port,
                                  self.__config.smtp_ssl_enabled,
                                  self.__config.smtp_sender,
                                  self.__config.smtp_username,
                                  self.__config.smtp_password)

    def run(self):
        while True:
            msg = self.__next_mail__()

            if msg:
                self.__send_mail__(msg)

            time.sleep(self.__config.mailer_interval)

    def __next_mail__(self):
        connection, queue = self.__connect__()

        read_next = True
        msg = None
        commit = False

        with connection.enter_scope() as scope:
            while read_next:
                self.__log.debug("Reading next mail...")

                msg = queue.next_mail(scope)

                if msg:
                    self.__log.info("Next mail: %s", msg)

                    delta = datetime.utcnow() - msg.created_at
                    elapsed = int(delta.total_seconds())

                    if elapsed > self.__config.mailer_ttl and False:
                        self.__log.debug("Mail too old, removing from queue.")

                        queue.delete(scope, msg.msgid)

                        msg = None
                        commit = True
                    else:
                        read_next = False
                else:
                    self.__log.debug("No mails found.")

                    read_next = False

            if commit:
                scope.complete()

        return msg

    def __send_mail__(self, msg):
        self.__log.info("Sending mail...")

        try:
            self.__mta.start_session()
            self.__mta.send(msg.receiver, msg.subject, msg.body)
            self.__mta.end_session()

            self.__log.debug("Marking mail delivered.")

            connection, queue = self.__connect__()

            with connection.enter_scope() as scope:
                queue.mark_delivered(scope, msg.msgid)

                scope.complete()
        except:
            traceback.print_exc()

    def __connect__(self):
        connection = sqlite.Connection(self.__config.database_filename)
        queue = mail.sqlite.EmailQueue()

        return connection, queue

def get_opts(argv):
    options, _ = getopt.getopt(argv, 'c:d:', ['config=', 'data-dir='])
    m = {}

    for opt, arg in options:
        if opt in ('-c', '--config'):
            m["config"] = arg

    if not m.get("config"):
        raise getopt.GetoptError("--config option is mandatory")

    return m

if __name__ == "__main__":
    try:
        opts = get_opts(sys.argv[1:])

        mailer = Sendmail(opts)

        mailer.run()

    except getopt.GetoptError as ex:
        print(str(ex))
