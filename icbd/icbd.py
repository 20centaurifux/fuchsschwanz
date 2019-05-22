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
import asyncore
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
import group
import group.memory
import database
import nickdb
import nickdb.sqlite
import timer
from actions import ACTION
import actions.usersession
import tld
import messages
from transform import Transform

import exception

class Server(asyncore.dispatcher, di.Injected):
    def __init__(self, address):
        asyncore.dispatcher.__init__(self)
        di.Injected.__init__(self)

        self.__log.info("Listening on %s:%d", *address)

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(address)
        self.address = self.socket.getsockname()
        self.listen(5)

        self.__signon_server__()

    def inject(self,
               log: logging.Logger,
               config: config.Config,
               store: session.Store,
               db_connection: database.Connection,
               nickdb: nickdb.NickDb):
        self.__log = log
        self.__config = config
        self.__session_store = store
        self.__db_connection = db_connection
        self.__nickdb = nickdb

    def handle_accept(self):
        client_info = self.accept()

        if client_info is not None:
            self.__log.info("Client connected: %s", client_info[1])

            Session(client_info[0], client_info[1])

    def __signon_server__(self):
        now = datetime.utcnow()

        session_id = self.__session_store.new(loginid=getuser(),
                                              ip=self.__config.server_address,
                                              host=socket.getfqdn(self.__config.server_address),
                                              nick=core.NICKSERV,
                                              authenticated=True,
                                              signon=now,
                                              t_recv=timer.Timer())

        with self.__db_connection.enter_scope() as scope:
            state = self.__session_store.get(session_id)

            self.__nickdb.set_lastlogin(scope, state.nick, state.loginid, state.host)
            self.__nickdb.set_signon(scope, state.nick, now)

            scope.complete()

MESSAGES = {cls.code: cls for cls in filter(lambda cls: isinstance(cls, type) and "code" in cls.__dict__,
                                            messages.__dict__.values())}

class Session(asyncore.dispatcher, di.Injected):
    def __init__(self, sock, address):
        di.Injected.__init__(self)
        asyncore.dispatcher.__init__(self, sock)

        self.__session_id = self.__session_store.new(ip=address[0], host=socket.getfqdn(address[0]))
        self.__broker.add_session(self.__session_id)
        self.__buffer = bytearray()
        self.__decoder = tld.Decoder()
        self.__decoder.add_listener(self.__message_received__)
        self.__transform = Transform()
        self.__shutdown = False

        self.__log.debug("Session created successfully: %s", self.__session_id)

        self.__write_protocol_info__()

    def inject(self,
               log: logging.Logger,
               config: config.Config,
               broker: broker.Broker,
               session_store: session.Store,
               away_table: session.AwayTimeoutTable,
               notification_table: session.NotificationTimeoutTable):
        self.__log = log
        self.__config = config
        self.__broker = broker
        self.__session_store = session_store
        self.__away_table = away_table
        self.__notification_table = away_table

    def writable(self):
        msg = self.__broker.pop(self.__session_id)

        if msg:
            self.__buffer.extend(msg)
            self.__shutdown = (len(msg) >= 2 and msg[1] == 103) # quit message ("g")

        return bool(self.__buffer) or self.__shutdown

    def handle_write(self):
        if self.__buffer:
            data = self.__buffer[:256]
            sent = self.send(data)
            self.__buffer = self.__buffer[sent:]
        elif self.__shutdown:
            self.__shutdown__()

    def handle_read(self):
        if not self.__shutdown:
            data = self.recv(256)

            try:
                self.__decoder.write(data)

            except exception.TldResponseException as ex:
                self.__broker.deliver(self.__session_id, ex.response)
                self.__broker.deliver(self.__session_id, tld.encode_empty_cmd("g"))

            except Exception:
                self.__log.fatal(traceback.format_exc())

                raise asyncore.ExitNow()

    def handle_close(self):
        self.__shutdown__()

    def __shutdown__(self):
        self.__log.info("Closing session: '%s'", self.__session_id)

        ACTION(actions.usersession.UserSession).sign_off(self.__session_id)

        self.__broker.remove_session(self.__session_id)
        self.__session_store.delete(self.__session_id)
        self.__away_table.remove_source(self.__session_id)
        self.__away_table.remove_target(self.__session_id)
        self.__notification_table.remove_target(self.__session_id)

        self.close()

    def __message_received__(self, type_id, payload):
        self.__log.debug("Received message: type='%s', session='%s', payload (size)=%d", type_id, self.__session_id, len(payload))

        type_id, payload = self.__transform.transform(type_id, payload)

        msg = MESSAGES.get(type_id)

        if not msg:
            self.__broker.deliver(self.__session_id, tld.encode_str("e", "Unexpected message: '%s'" % type_id))
        else:
            msg.process(self.__session_id, tld.split(payload))
            self.__session_store.update(self.__session_id, t_recv=timer.Timer())

    def __write_protocol_info__(self):
        e = tld.Encoder("j")

        e.add_field_str(core.PROTOCOL_VERSION)
        e.add_field_str(self.__config.server_hostname, append_null=False)
        e.add_field_str("%s %s" % (self.__config.server_hostname, core.VERSION), append_null=True)

        self.__broker.deliver(self.__session_id, e.encode())

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

def run(opts):
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
    container.register(group.Store, group.memory.Store())
    container.register(database.Connection, nickdb.sqlite.Connection(preferences.database_filename))
    container.register(nickdb.NickDb, nickdb.sqlite.NickDb)

    with container.resolve(database.Connection).enter_scope() as scope:
        container.resolve(nickdb.NickDb).setup(scope)
        scope.complete()

    Server((preferences.server_address, preferences.server_port))

    try:
        asyncore.loop()

    except (KeyboardInterrupt, Exception):
        logger.info("Server finished.")

    with container.resolve(database.Connection).enter_scope() as scope:
        container.resolve(nickdb.NickDb).set_signoff(scope, core.NICKSERV, datetime.utcnow())
        scope.complete()

if __name__ == "__main__":
    try:
        opts = get_opts(sys.argv[1:])

        run(opts)
    except getopt.GetoptError as ex:
        print(str(ex))
