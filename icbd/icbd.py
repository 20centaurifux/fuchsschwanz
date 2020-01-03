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
import logging
import asyncio
import os.path
import traceback
from datetime import datetime
import time
import getopt
import sys
import os
import multiprocessing
import signal
import core
import config
import config.json
import log
import di
from process import Process
import ipc
import network
import session
import session.memory
import broker
import broker.memory
import shutdown
import reputation
import reputation.memory
import group
import group.memory
import sqlite
import nickdb
import nickdb.sqlite
import statsdb
import statsdb.sqlite
import confirmation
import confirmation.sqlite
import passwordreset
import passwordreset.sqlite
import motd
import motd.plaintext
import manual
import manual.plaintext
import news
import news.plaintext
import template
import template.plaintext
import mail
import mail.sqlite
import timer
import avatar
import avatar.sqlite
import ipfilter
import ipfilter.sqlite
import ipfilter.cache
import ltd
import dateutils

if avatar.is_available():
    import avatar.fs
else:
    import avatar.void

class MailProcess(Process, di.Injected, mail.SinkListener):
    def __init__(self):
        Process.__init__(self, "mail")
        di.Injected.__init__(self)

    def inject(self, config: config.Config, log: logging.Logger, sink: mail.Sink):
        self.__config = config
        self.__log = log
        self.__sink = sink

        self.__sink.add_listener(self)

    def __build_args__(self, argv):
        script = os.path.join(os.path.dirname(__file__), "mail_process.py")

        return [sys.executable, script, "--config", argv["config"]]

    def put(self, receiver, subject, body):
        self.__log.info("'%s' mail enqueued.", subject)

        self.broadcast("put")

class AvatarProcess(Process, di.Injected, avatar.WriterListener):
    def __init__(self):
        Process.__init__(self, "avatar")
        di.Injected.__init__(self)

    def inject(self, config: config.Config, log: logging.Logger, broadcast: ipc.Broadcast, writer: avatar.Writer):
        self.__config = config
        self.__log = log
        self.__broadcast = broadcast
        self.__writer = writer

        self.__writer.add_listener(self)

    def __build_args__(self, argv):
        script = os.path.join(os.path.dirname(__file__), "avatar_process.py")

        return [sys.executable, script, "--config", argv["config"]]

    def put(self, nick, url):
        self.__log.info("Avatar changed: %s (%s)", url, nick)

        self.broadcast("put")

async def run_services(opts):
    data_dir = opts.get("data_dir")

    mapping = config.json.load(opts["config"])
    preferences = config.from_mapping(mapping)

    logger = log.new_logger("icbd", preferences.logging_verbosity)

    registry = log.Registry()

    registry.register(logger)

    logger.info("Starting server process with pid %d.", os.getpid())

    container = di.default_container

    connection = sqlite.Connection(preferences.database_filename)

    ipfilter_storage = ipfilter.sqlite.Storage()
    ipfilter_cached = ipfilter.cache.Storage(ipfilter_storage)

    container.register(logging.Logger, logger)
    container.register(log.Registry, registry)
    container.register(config.Config, preferences)
    container.register(ipc.Broadcast, ipc.Broadcast())
    container.register(shutdown.Shutdown, shutdown.Shutdown())
    container.register(ipfilter.Connection, connection)
    container.register(ipfilter.Storage, ipfilter_cached)
    container.register(broker.Broker, broker.memory.Broker())
    container.register(session.Store, session.memory.Store())
    container.register(session.AwayTimeoutTable, timer.TimeoutTable())
    container.register(session.NotificationTimeoutTable, timer.TimeoutTable())
    container.register(reputation.Reputation, reputation.memory.Reputation())
    container.register(group.Store, group.memory.Store())
    container.register(nickdb.Connection, connection)
    container.register(nickdb.NickDb, nickdb.sqlite.NickDb())
    container.register(statsdb.Connection, connection)
    container.register(statsdb.StatsDb, statsdb.sqlite.StatsDb())
    container.register(confirmation.Connection, connection)
    container.register(confirmation.Confirmation, confirmation.sqlite.Confirmation())
    container.register(passwordreset.Connection, connection)
    container.register(passwordreset.PasswordReset, passwordreset.sqlite.PasswordReset())
    container.register(motd.Motd, motd.plaintext.Motd(os.path.join(data_dir, "motd")))
    container.register(manual.Manual, manual.plaintext.Manual(os.path.join(data_dir, "help")))
    container.register(news.News, news.plaintext.News(os.path.join(data_dir, "news")))
    container.register(template.Template, template.plaintext.Template(os.path.join(data_dir, "templates")))
    container.register(mail.Connection, connection)
    container.register(mail.Sink, mail.sqlite.Sink())
    container.register(avatar.Connection, connection)
    container.register(avatar.Reader, avatar.sqlite.Reader())
    container.register(avatar.Writer, avatar.sqlite.Writer(preferences.avatar_reload_timeout,
                                                           preferences.avatar_retry_timeout,
                                                           preferences.avatar_max_errors,
                                                           preferences.avatar_error_timeout))
    if avatar.is_available():
        container.register(avatar.Storage, avatar.fs.AsciiFiles(preferences.avatar_directory,
                                                                preferences.avatar_ascii_width,
                                                                preferences.avatar_ascii_height))
    else:
        logger.info("Avatar preview not available.")

        container.register(avatar.Storage, avatar.void.Storage())

    with connection.enter_scope() as scope:
        container.resolve(ipfilter.Storage).setup(scope)
        container.resolve(nickdb.NickDb).setup(scope)
        container.resolve(statsdb.StatsDb).setup(scope)
        container.resolve(confirmation.Confirmation).setup(scope)
        container.resolve(mail.Sink).setup(scope)
        container.resolve(avatar.Reader).setup(scope)
        container.resolve(avatar.Writer).setup(scope)
        container.resolve(passwordreset.PasswordReset).setup(scope)

        scope.complete()

    container.resolve(avatar.Storage).setup()

    bus = ipc.Bus()

    await bus.start()

    if os.name == "posix":
        loop = asyncio.get_event_loop()

        loop.add_signal_handler(signal.SIGINT, lambda: server.close())
        loop.add_signal_handler(signal.SIGTERM, lambda: server.close())

    processes = [MailProcess()]

    if avatar.is_available():
        processes.append(AvatarProcess())

    asyncio.gather(*[p.spawn(opts) for p in processes])

    failed = False

    try:
        server = network.Server()

        await server.run()
    except asyncio.CancelledError:
        pass
    except:
        logger.warning(traceback.format_exc())

        failed = True

    await bus.close()

    for p in processes:
        p.exit()

    logger.info("Server stopped.")

    with container.resolve(nickdb.Connection).enter_scope() as scope:
        container.resolve(nickdb.NickDb).set_signoff(scope, core.NICKSERV, dateutils.now())

        scope.complete()

    sys.exit(server.exit_code if not failed else core.EXIT_FAILURE)

def run(opts):
    asyncio.run(run_services(opts))

def get_opts(argv):
    options, _ = getopt.getopt(argv, 'c:d:', ['config=', 'data-dir=', 'auto-respawn'])

    m = {"auto-respawn": False}

    for opt, arg in options:
        if opt in ('-c', '--config'):
            m["config"] = arg
        elif opt in ('-d', '--data-dir'):
            m["data_dir"] = arg
        elif opt in ('--auto-respawn',):
            m["auto-respawn"] = True

    if not m.get("config"):
        raise getopt.GetoptError("--config option is mandatory")

    if not m.get("data_dir"):
        raise getopt.GetoptError("--data-dir option is mandatory")

    return m

if __name__ == "__main__":
    try:
        opts = get_opts(sys.argv[1:])

        spawn = True

        while spawn:
            p = multiprocessing.Process(target=run, args=(opts,))

            p.start()
            p.join()

            if p.exitcode != core.EXIT_RESTART:
                if p.exitcode == core.EXIT_SUCCESS or not opts["auto-respawn"]:
                    spawn = False
                else:
                    for _ in range(10):
                        sys.stdout.write(".")
                        sys.stdout.flush()
                        time.sleep(1)

                    sys.stdout.write("\n")

    except getopt.GetoptError as ex:
        print(str(ex))
    except:
        traceback.print_exc()
