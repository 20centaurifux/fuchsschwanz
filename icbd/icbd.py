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
import socket
import ssl
import os.path
import traceback
from datetime import datetime
import time
from getpass import getuser
import getopt
import sys
import os
from subprocess import Popen, DEVNULL, PIPE, TimeoutExpired
import multiprocessing
import signal
import math
import core
import config
import config.json
import log
from log.asyncio import LogProtocol
import di
import shutdown
import session
import session.memory
import broker
import broker.memory
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
import avatar
import avatar.sqlite

if avatar.is_available():
    import avatar.fs
else:
    import avatar.void

import timer
from actions import ACTION
import actions.usersession
import ltd
import messages
from transform import Transform
from exception import LtdResponseException, LtdErrorException

MESSAGES = {cls.code: cls for cls in filter(lambda cls: isinstance(cls, type) and "code" in cls.__dict__,
                                            messages.__dict__.values())}

class ICBServerProtocol(asyncio.Protocol, di.Injected):
    def __init__(self, connections):
        asyncio.Protocol.__init__(self)
        di.Injected.__init__(self)

        self.__connections = connections

    def inject(self,
               log: logging.Logger,
               config: config.Config,
               broker: broker.Broker,
               session_store: session.Store,
               away_table: session.AwayTimeoutTable,
               reputation: reputation.Reputation):
        self.__log = log
        self.__config = config
        self.__broker = broker
        self.__session_store = session_store
        self.__away_table = away_table
        self.__notification_table = away_table
        self.__reputation = reputation

    def connection_made(self, transport):
        address = transport.get_extra_info("peername")

        self.__log.info("Client connected: %s:%d", address[0], address[1])

        cipher = transport.get_extra_info("cipher")
        tls = False

        if cipher:
            self.__log.info("Cipher: %s", cipher)
            tls = True

        self.__transport = transport
        self.__session_id = self.__session_store.new(ip=address[0],
                                                     host=socket.getfqdn(address[0]),
                                                     tls=tls,
                                                     t_recv=timer.Timer(),
                                                     t_alive=timer.Timer())
        self.__broker.add_session(self.__session_id, self.__handle_write__)
        self.__reputation.add_session(self.__session_id)
        self.__buffer = bytearray()
        self.__decoder = ltd.Decoder()
        self.__decoder.add_listener(self.__message_received__)
        self.__transform = Transform()
        self.__shutdown = False

        self.__log.debug("Session created successfully: %s", self.__session_id)

        self.__connections[self.__session_id] = self

        self.__write_protocol_info__()

    def __handle_write__(self, message):
        if not self.__reject__(message):
            self.__transport.write(message)

        self.__shutdown = (len(message) >= 2 and message[1] == 103) # quit message ("g")

    def __reject__(self, message):
        rejected = False

        if len(message) >= 5 and (message[1] == 98 or message[1] == 99): # public or private message
            state = self.__session_store.get(self.__session_id)

            if not state.hushlist.empty():
                is_public = message[1] == 98

                sender = self.__message_from__(message)

                rejected = self.__hushed__(state.hushlist, sender, public=is_public)

                if rejected and message[1] == 99:
                    self.__notify_sender__(sender)

        return rejected

    def __message_from__(self, message):
        payload = message[2:]
        index = payload.find(1)

        sender = None

        if index > 0:
            sender = payload[:index].decode("UTF-8", errors="backslashreplace").strip()

        return sender

    def __hushed__(self, hushlist, sender, public):
        hushed = False

        if public:
            hushed = hushlist.nick_public_hushed(sender)
        else:
            hushed = hushlist.nick_private_hushed(sender)

        if not hushed:
            sender_session = self.__session_store.find_nick(sender)
            sender_state = self.__session_store.get(sender_session)

            if public:
                hushed = hushlist.site_public_hushed(sender_state.address)
            else:
                hushed = hushlist.site_private_hushed(sender_state.address)

        return hushed

    def __notify_sender__(self, sender):
        session_id = self.__session_store.find_nick(sender)

        if session_id:
            self.__broker.deliver(session_id, ltd.encode_status_msg("Bounce", "Message did not go trough."))

    def data_received(self, data):
        if not self.__shutdown:
            try:
                self.__decoder.write(data)

            except LtdResponseException as ex:
                self.__broker.deliver(self.__session_id, ex.response)
                self.__broker.deliver(self.__session_id, ltd.encode_empty_cmd("g"))

            except Exception:
                self.__abort__()

    def __abort__(self):
        self.__log.fatal(traceback.format_exc())

        loop = asyncio.get_running_loop()

        loop.stop()

    def connection_lost(self, ex):
        if ex:
            self.__log.info(ex)

        self.__shutdown__()

    def __shutdown__(self):
        self.__log.info("Closing session: '%s'", self.__session_id)

        ACTION(actions.usersession.UserSession).sign_off(self.__session_id)

        del self.__connections[self.__session_id]

        self.__broker.remove_session(self.__session_id)
        self.__session_store.delete(self.__session_id)
        self.__away_table.remove_source(self.__session_id)
        self.__away_table.remove_target(self.__session_id)
        self.__notification_table.remove_target(self.__session_id)
        self.__reputation.remove_session(self.__session_id)

        self.__transport.abort()

    def timeout(self):
        self.__transport.abort()

    def __message_received__(self, type_id, payload):
        self.__log.debug("Received message: type='%s', session='%s', payload (size)=%d", type_id, self.__session_id, len(payload))

        type_id, payload = self.__transform.transform(type_id, payload)

        state = self.__session_store.get(self.__session_id)

        elapsed = state.t_recv.elapsed() if state.t_recv else 0

        old_reputation = self.__reputation.get(self.__session_id)

        if not type_id in ["m", "n"]:
            self.__session_store.update(self.__session_id, t_recv=timer.Timer(), t_alive=timer.Timer())
        else:
            self.__session_store.update(self.__session_id, t_alive=timer.Timer())

        msg = None

        if not type_id in ["b", "c"] or elapsed >= self.__config.timeouts_time_between_messages:
            msg = MESSAGES.get(type_id)

            if not msg:
                self.__broker.deliver(self.__session_id, ltd.encode_str("e", "Unexpected message: '%s'" % type_id))
        else:
            self.__log.debug("Time between messages too short.")

        if msg:
            msg.process(self.__session_id, ltd.split(payload))

            new_reputation = self.__reputation.get(self.__session_id)

            if old_reputation == new_reputation:
                self.__reputation.ok(self.__session_id)
        else:
            self.__reputation.warning(self.__session_id)

        if self.__reputation.get(self.__session_id) == 0.0:
            raise LtdErrorException("Suspicious activity detected.")

    def __write_protocol_info__(self):
        e = ltd.Encoder("j")

        e.add_field_str(core.PROTOCOL_VERSION)
        e.add_field_str(self.__config.server_hostname, append_null=False)
        e.add_field_str("%s %s" % (self.__config.server_hostname, core.VERSION), append_null=True)

        self.__broker.deliver(self.__session_id, e.encode())

class Server(di.Injected, shutdown.ShutdownListener):
    def __init__(self):
        di.Injected.__init__(self)

        self.__connections = {}
        self.__max_idle_time = 0.0
        self.__servers = []
        self.__shutdown_task = None
        self.__exit_code = core.EXIT_SUCCESS

    def inject(self,
               log: logging.Logger,
               config: config.Config,
               shutdown: shutdown.Shutdown,
               store: session.Store,
               broker: broker.Broker,
               groups: group.Store,
               nickdb_connection: nickdb.Connection,
               nickdb: nickdb.NickDb,
               statsdb_connection: statsdb.Connection,
               statsdb: statsdb.StatsDb,
               cfm_connection: confirmation.Connection,
               cfm: confirmation.Confirmation,
               pwdreset_connection: passwordreset.Connection,
               pwdreset: passwordreset.PasswordReset):
        self.__log = log
        self.__config = config
        self.__shutdown = shutdown
        self.__session_store = store
        self.__broker = broker
        self.__groups = groups
        self.__nickdb_connection = nickdb_connection
        self.__nickdb = nickdb
        self.__statsdb_connection = statsdb_connection
        self.__statsdb = statsdb
        self.__cfm_connection = cfm_connection
        self.__cfm = cfm
        self.__pwdreset_connection = pwdreset_connection
        self.__pwdreset = pwdreset

    async def run(self):
        self.__signon_server__()

        loop = asyncio.get_running_loop()

        loop.create_task(self.__process_idling_sessions__())
        loop.create_task(self.__cleanup_dbs_())

        if self.__config.tcp_enabled:
            self.__log.info("Listening on %s:%d (tcp)", self.__config.tcp_address, self.__config.tcp_port)

            server = await loop.create_server(lambda: ICBServerProtocol(self.__connections),
                                                                        self.__config.tcp_address,
                                                                        self.__config.tcp_port)

            self.__servers.append(server)

        if self.__config.tcp_tls_enabled:
            self.__log.info("Listening on %s:%d (tcp/tls)", self.__config.tcp_tls_address, self.__config.tcp_tls_port)

            sc = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            sc.load_cert_chain(self.__config.tcp_tls_cert, self.__config.tcp_tls_key)

            server = await loop.create_server(lambda: ICBServerProtocol(self.__connections),
                                              self.__config.tcp_tls_address,
                                              self.__config.tcp_tls_port, ssl=sc)

            self.__servers.append(server)

        self.__shutdown.add_listener(self)

        await asyncio.gather(*(map(lambda s: s.serve_forever(), self.__servers)))

    def close(self):
        self.__log.info("Stopping server.")

        for s in self.__servers:
            s.close()

    def __signon_server__(self):
        now = datetime.utcnow()

        self.__session_id = self.__session_store.new(loginid=getuser(),
                                                     ip=self.__config.tcp_address,
                                                     host=socket.getfqdn(self.__config.tcp_address),
                                                     nick=core.NICKSERV,
                                                     authenticated=True,
                                                     signon=now,
                                                     t_recv=timer.Timer())

        with self.__nickdb_connection.enter_scope() as scope:
            state = self.__session_store.get(self.__session_id)

            self.__nickdb.set_lastlogin(scope, state.nick, state.loginid, state.host)
            self.__nickdb.set_signon(scope, state.nick, now)

            scope.complete()

    @property
    def exit_code(self):
        return self.__exit_code

    def shutdown(self, delay, restart):
        self.cancel_shutdown()

        loop = asyncio.get_running_loop()

        self.__shutdown_task = loop.create_task(self.__shutdown_task__(delay, restart))

    def cancel_shutdown(self):
        if self.__shutdown_task:
            self.__log.info("Cancelling pending shutdown task.")

            self.__shutdown_task.cancel()

    async def __shutdown_task__(self, delay, restart):
        self.__log.info("%s in %d second(s).", "Restart" if restart else "Shutdown", delay)

        await asyncio.sleep(delay)

        self.close()

        e = ltd.Encoder("f")

        e.add_field_str("WALL", append_null=False)
        e.add_field_str("Server is %s." % ("restarting, please stay patient" if restart else "shutting down"), append_null=True)

        self.__broker.broadcast(e.encode())

        self.__exit_code = core.EXIT_RESTART if restart else core.EXIT_SUCCESS

    async def __process_idling_sessions__(self):
        while True:
            interval = int(self.__config.timeouts_ping)
            sessions = {k: v for k, v in self.__session_store if k != self.__session_id}

            self.__log.debug("Processing idling sessions.")

            max_idle_time = None
            max_idle_nick = None

            for k, v in sessions.items():
                if k != self.__session_id:
                    alive = v.t_alive.elapsed()

                    if alive >= self.__config.timeouts_connection:
                        self.__log.info("Connection timeout, session='%s', last activity=%.2f", k, alive)

                        self.__connections[k].timeout()
                    else:
                        elapsed = v.t_recv.elapsed()

                        if not max_idle_time or elapsed > max_idle_time:
                            max_idle_time = elapsed
                            max_idle_nick = v.nick

                        if elapsed >= self.__config.timeouts_ping:
                            last_ping = v.t_ping.elapsed() if v.t_ping else 0.0

                            if not v.t_ping or last_ping >= self.__config.timeouts_ping:
                                self.__log.debug("Sending ping message to session %s (idle=%.2f, ping timeout=%.2f).",
                                                 k,
                                                 elapsed, last_ping)

                                self.__broker.deliver(k, ltd.encode_empty_cmd("l"))

                                self.__session_store.update(k, t_ping=timer.Timer())
                            else:
                                interval = self.__next_interval__(interval, self.__config.timeouts_ping - last_ping)
                        else:
                            interval = self.__next_interval__(interval, self.__config.timeouts_ping - elapsed)

                        if v.group:
                            info = self.__groups.get(v.group)

                            if info.moderator and k == info.moderator and info.idle_mod > 0:
                                if elapsed > info.idle_mod * 60:
                                    ACTION(actions.usersession.UserSession).idle_mod(k)
                                else:
                                    interval = self.__next_interval__(interval, (info.idle_mod * 60) - elapsed)

                            if (not info.moderator or k != info.moderator) and info.idle_boot > 0:
                                if elapsed > info.idle_boot * 60:
                                    ACTION(actions.usersession.UserSession).idle_boot(k)
                                else:
                                    interval = self.__next_interval__(interval, (info.idle_boot * 60) - elapsed)

            if max_idle_time and max_idle_time > self.__max_idle_time:
                max_idle_time = round(max_idle_time)

                self.__log.debug("Max idle time: %.2f (%s)", max_idle_time, max_idle_nick)

                with self.__statsdb_connection.enter_scope() as scope:
                    self.__statsdb.set_max_idle(scope, max_idle_time, max_idle_nick)

                    scope.complete()

                    self.__max_idle_time = max_idle_time

            self.__log.debug("Next interval: %.2f", interval)

            await asyncio.sleep(interval)

    @staticmethod
    def __next_interval__(interval, next_interval):
        return int(min(interval, math.ceil(next_interval)))

    async def __cleanup_dbs_(self):
        while True:
            self.__log.info("Cleaning up confirmation requests.")

            with self.__cfm_connection.enter_scope() as scope:
                self.__cfm.cleanup(scope, self.__config.timeouts_confirmation_code)

                scope.complete()

            self.__log.info("Cleaning up password reset codes.")

            with self.__pwdreset_connection.enter_scope() as scope:
                self.__pwdreset.cleanup(scope, self.__config.timeouts_password_reset_request)

                scope.complete()

            self.__log.debug("Next cleanup in %.2f seconds.", self.__config.database_cleanup_interval)

            await asyncio.sleep(self.__config.database_cleanup_interval)

class Process:
    def __init__(self, name):
        self.__name = name
        self.__process = None
        self.__log = di.default_container.resolve(logging.Logger)
        self.__config = di.default_container.resolve(config.Config)

    async def spawn(self, argv):
        log = di.default_container.resolve(logging.Logger)

        args = self.__build_args__(argv)

        self.__log.info("Spawning '%s' process: %s", self.__name, " ".join(args))

        if os.name == "posix":
            self.__process = Popen(args, stdout=DEVNULL, stderr=PIPE)

            loop = asyncio.get_event_loop()
            conf = di.default_container.resolve(config.Config)

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

        if hasattr(signal, "SIGUSR1"):
            self.signal(signal.SIGUSR1)

class AvatarProcess(Process, di.Injected, avatar.WriterListener):
    def __init__(self):
        Process.__init__(self, "avatar")
        di.Injected.__init__(self)

    def inject(self, config: config.Config, log: logging.Logger, writer: avatar.Writer):
        self.__config = config
        self.__log = log
        self.__writer = writer

        self.__writer.add_listener(self)

    def __build_args__(self, argv):
        script = os.path.join(os.path.dirname(__file__), "avatar_process.py")

        return [sys.executable, script, "--config", argv["config"]]

    def put(self, nick, url):
        self.__log.info("Avatar changed: %s (%s)", url, nick)

        if hasattr(signal, "SIGUSR1"):
            self.signal(signal.SIGUSR1)

async def run_icbd(opts):
    data_dir = opts.get("data_dir")

    mapping = config.json.load(opts["config"])
    preferences = config.from_mapping(mapping)

    logger = log.new_logger("icbd", preferences.logging_verbosity)

    registry = log.Registry()

    registry.register(logger)

    logger.info("Starting server process with pid %d.", os.getpid())

    container = di.default_container

    connection = sqlite.Connection(preferences.database_filename)

    container.register(logging.Logger, logger)
    container.register(log.Registry, registry)
    container.register(config.Config, preferences)
    container.register(shutdown.Shutdown, shutdown.Shutdown())
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
        container.resolve(nickdb.NickDb).setup(scope)
        container.resolve(statsdb.StatsDb).setup(scope)
        container.resolve(confirmation.Confirmation).setup(scope)
        container.resolve(avatar.Reader).setup(scope)
        container.resolve(avatar.Writer).setup(scope)
        container.resolve(passwordreset.PasswordReset).setup(scope)
        container.resolve(mail.Sink).setup(scope)

        scope.complete()

    container.resolve(avatar.Storage).setup()

    server = Server()

    if os.name == "posix":
        loop = asyncio.get_event_loop()

        loop.add_signal_handler(signal.SIGINT, lambda: server.close())
        loop.add_signal_handler(signal.SIGTERM, lambda: server.close())
    else:
        logger.warning("No signal handlers registered.")

    processes = [MailProcess()]

    if avatar.is_available():
        processes.append(AvatarProcess())

    await asyncio.gather(*(map(lambda p: p.spawn(opts), processes)))
 
    failed = False

    try:
        await server.run()
    except asyncio.CancelledError:
        pass
    except:
        logger.warning(traceback.format_exc())

        failed = True

    for p in processes:
        p.kill()

    logger.info("Server stopped.")

    with container.resolve(nickdb.Connection).enter_scope() as scope:
        container.resolve(nickdb.NickDb).set_signoff(scope, core.NICKSERV, datetime.utcnow())
        scope.complete()

    sys.exit(server.exit_code if not failed else core.EXIT_FAILURE)

def run(opts):
    asyncio.run(run_icbd(opts))

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
