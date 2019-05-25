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
import asyncio
import socket
import traceback
from datetime import datetime
from getpass import getuser
import getopt
import sys
import os
import core
import config
import config.json
import log
import di
import session
import session.memory
import broker
import broker.memory
import reputation
import reputation.memory
import group
import group.memory
import database
import nickdb
import nickdb.sqlite
import manual
import manual.plaintext
import timer
from actions import ACTION
import actions.usersession
import tld
import messages
from transform import Transform
from exception import TldResponseException, TldErrorException

MESSAGES = {cls.code: cls for cls in filter(lambda cls: isinstance(cls, type) and "code" in cls.__dict__,
                                            messages.__dict__.values())}

class ICBServerProtocol(asyncio.Protocol, di.Injected):
    def inject(self,
               log: logging.Logger,
               config: config.Config,
               broker: broker.Broker,
               session_store: session.Store,
               away_table: session.AwayTimeoutTable,
               notification_table: session.NotificationTimeoutTable,
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

        self.__transport = transport
        self.__session_id = self.__session_store.new(ip=address[0], host=socket.getfqdn(address[0]))
        self.__broker.add_session(self.__session_id, self.__handle_write__)
        self.__reputation.add_session(self.__session_id)
        self.__buffer = bytearray()
        self.__decoder = tld.Decoder()
        self.__decoder.add_listener(self.__message_received__)
        self.__transform = Transform()
        self.__shutdown = False

        self.__log.debug("Session created successfully: %s", self.__session_id)

        self.__write_protocol_info__()

    def __handle_write__(self, message):
        self.__transport.write(message)
        self.__shutdown = (len(message) >= 2 and message[1] == 103) # quit message ("g")

    def data_received(self, data):
        if not self.__shutdown:
            try:
                self.__decoder.write(data)

            except TldResponseException as ex:
                self.__broker.deliver(self.__session_id, ex.response)
                self.__broker.deliver(self.__session_id, tld.encode_empty_cmd("g"))

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

        self.__broker.remove_session(self.__session_id)
        self.__session_store.delete(self.__session_id)
        self.__away_table.remove_source(self.__session_id)
        self.__away_table.remove_target(self.__session_id)
        self.__notification_table.remove_target(self.__session_id)
        self.__reputation.remove_session(self.__session_id)

        self.__transport.abort()

    def __message_received__(self, type_id, payload):
        self.__log.debug("Received message: type='%s', session='%s', payload (size)=%d", type_id, self.__session_id, len(payload))

        type_id, payload = self.__transform.transform(type_id, payload)

        state = self.__session_store.get(self.__session_id)

        elapsed = state.t_recv.elapsed() if state.t_recv else None

        old_reputation = self.__reputation.get(self.__session_id)

        if type != "m":
            self.__session_store.update(self.__session_id, t_recv=timer.Timer())

        msg = None

        if not elapsed or elapsed > self.__config.protection_time_between_messages:
            msg = MESSAGES.get(type_id)

            if not msg:
                self.__broker.deliver(self.__session_id, tld.encode_str("e", "Unexpected message: '%s'" % type_id))
        else:
            self.__log.debug("Time between messages too short.")

        if msg:
            msg.process(self.__session_id, tld.split(payload))

            new_reputation = self.__reputation.get(self.__session_id)

            if old_reputation == new_reputation:
                self.__reputation.ok(self.__session_id)
        else:
            self.__reputation.warning(self.__session_id)

        if self.__reputation.get(self.__session_id) == 0.0:
            raise TldErrorException("Suspicious activity detected.")

    def __write_protocol_info__(self):
        e = tld.Encoder("j")

        e.add_field_str(core.PROTOCOL_VERSION)
        e.add_field_str(self.__config.server_hostname, append_null=False)
        e.add_field_str("%s %s" % (self.__config.server_hostname, core.VERSION), append_null=True)

        self.__broker.deliver(self.__session_id, e.encode())

class Server(di.Injected):
    def inject(self,
               log: logging.Logger,
               config: config.Config,
               store: session.Store,
               broker: broker.Broker,
               db_connection: database.Connection,
               nickdb: nickdb.NickDb):
        self.__log = log
        self.__config = config
        self.__session_store = store
        self.__broker = broker
        self.__db_connection = db_connection
        self.__nickdb = nickdb

    async def run(self, address):
        self.__log.info("Listening on %s:%d", address[0], address[1])

        loop = asyncio.get_running_loop()

        server = await loop.create_server(lambda: ICBServerProtocol(), *address)

        self.__signon_server__()

        loop.create_task(self.__send_ping__())

        async with server:
            await server.serve_forever()

    def __signon_server__(self):
        now = datetime.utcnow()

        self.__session_id = self.__session_store.new(loginid=getuser(),
                                                     ip=self.__config.server_address,
                                                     host=socket.getfqdn(self.__config.server_address),
                                                     nick=core.NICKSERV,
                                                     authenticated=True,
                                                     signon=now,
                                                     t_recv=timer.Timer())

        with self.__db_connection.enter_scope() as scope:
            state = self.__session_store.get(self.__session_id)

            self.__nickdb.set_lastlogin(scope, state.nick, state.loginid, state.host)
            self.__nickdb.set_signon(scope, state.nick, now)

            scope.complete()

    async def __send_ping__(self):
        t = timer.Timer()

        while True:
            for k, v in self.__session_store:
                if k != self.__session_id and v.t_recv.elapsed() >= 15.0:
                    self.__broker.deliver(k, tld.encode_empty_cmd("l"))

            await asyncio.sleep(15.0)

async def run(opts):
    working_dir = opts.get("working_dir")

    if working_dir:
        os.chdir(working_dir)

    mapping = config.json.load(opts["config"])
    preferences = config.from_mapping(mapping)

    logger = log.new_logger(preferences.logging_verbosity)

    logger.info("Starting server...")

    container = di.default_container

    container.register(logging.Logger, logger)
    container.register(config.Config, preferences)
    container.register(broker.Broker, broker.memory.Broker())
    container.register(session.Store, session.memory.Store())
    container.register(session.AwayTimeoutTable, timer.TimeoutTable())
    container.register(session.NotificationTimeoutTable, timer.TimeoutTable())
    container.register(reputation.Reputation, reputation.memory.Reputation())
    container.register(group.Store, group.memory.Store())
    container.register(database.Connection, nickdb.sqlite.Connection(preferences.database_filename))
    container.register(nickdb.NickDb, nickdb.sqlite.NickDb)
    container.register(manual.Manual, manual.plaintext.Manual(preferences.help_path))

    with container.resolve(database.Connection).enter_scope() as scope:
        container.resolve(nickdb.NickDb).setup(scope)
        scope.complete()

    address = (preferences.server_address, preferences.server_port)
    server = Server()

    await server.run(address)

    logger.info("Server stopped.")

    with container.resolve(database.Connection).enter_scope() as scope:
        container.resolve(nickdb.NickDb).set_signoff(scope, core.NICKSERV, datetime.utcnow())
        scope.complete()

def get_opts(argv):
    options, _ = getopt.getopt(argv, '-c:w:', ['config=', 'working-dir='])
    m = {}

    for opt, arg in options:
        if opt in ('-c', '--config'):
            m["config"] = arg
        if opt in ('-w', '--working-dir'):
            m["working_dir"] = arg

    if not m.get("config"):
        raise getopt.GetoptError("--config option is mandatory")

    return m

if __name__ == "__main__":
    try:
        opts = get_opts(sys.argv[1:])

        asyncio.run(run(opts))
    except getopt.GetoptError as ex:
        print(str(ex))
    except:
        traceback.print_exc()

