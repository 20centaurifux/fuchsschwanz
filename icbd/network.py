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
import traceback
from datetime import datetime
from getpass import getuser
import math
import core
import config
import config.json
import di
import ipfilter
import broker
import session
import group
import nickdb
import statsdb
import reputation
import url
import shutdown
import session
import session.memory
import confirmation
import passwordreset
import timer
import dateutils
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

        self.__log.info("Client address: %s:%d", address[0], address[1])

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
        self.__log.debug("Received message: type='%s', session='%s', payload (size=%d)", type_id, self.__session_id, len(payload))

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
               ipfilter_connection: ipfilter.Connection,
               ipfilters: ipfilter.Storage,
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
        self.__ipfilter_connection = ipfilter_connection
        self.__ipfilters = ipfilters
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

        for addr in self.__config.bindings:
            self.__log.info("Found binding: %s", addr)

            binding = url.parse_server_address(addr)

            if binding["protocol"] == "tcp":
                self.__log.info("Listening on %s:%d (tcp)", binding["address"], binding["port"])

                server = await loop.create_server(lambda: ICBServerProtocol(self.__connections),
                                                                            binding["address"],
                                                                            binding["port"])

                self.__servers.append(server)
            elif binding["protocol"] == "tcps":
                self.__log.info("Listening on %s:%d (tcp/tls)", binding["address"], binding["port"])

                sc = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                sc.load_cert_chain(binding["cert"], binding["key"])

                server = await loop.create_server(lambda: ICBServerProtocol(self.__connections),
                                                                            binding["address"],
                                                                            binding["port"],
                                                                            ssl=sc)
            else:
                raise NotImplementedError("Unsupported protocol: %s", binding["protocol"])

        self.__shutdown.add_listener(self)

        await asyncio.gather(*(map(lambda s: s.serve_forever(), self.__servers)))

    def close(self):
        self.__log.info("Stopping server.")

        for s in self.__servers:
            s.close()

    def __signon_server__(self):
        now = dateutils.now()

        self.__session_id = self.__session_store.new(loginid=getuser(),
                                                     ip="127.0.0.1",
                                                     host=self.__config.server_hostname,
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

            self.__log.info("Cleaning up IP filters.")

            with self.__ipfilter_connection.enter_scope() as scope:
                self.__ipfilters.cleanup(scope)

                scope.complete()

            self.__log.debug("Next cleanup in %.2f seconds.", self.__config.database_cleanup_interval)

            await asyncio.sleep(self.__config.database_cleanup_interval)
