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
import config, tld, messages, exception, commands
import di, broker, session, groups
import database, nickdb, sqlite
import asyncore, socket
from timer import Timer
from logger import log

PROTOCOL_VERSION = "1"

class Server(asyncore.dispatcher):
    def __init__(self, address):
        asyncore.dispatcher.__init__(self)

        log.info("Listening on %s:%d" % address)

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(address)
        self.address = self.socket.getsockname()
        self.listen(5)

    def handle_accept(self):
        client_info = self.accept()

        if client_info is not None:
            log.info("Client connected: %s" % (client_info[1], ))

            Session(client_info[0], client_info[1])

MESSAGES = {cls.code: cls() for cls in filter(lambda cls: isinstance(cls, type) and "code" in cls.__dict__,
                                              messages.__dict__.values())}

class Session(asyncore.dispatcher, di.Injected):
    def __init__(self, sock, address):
        di.Injected.__init__(self)
        asyncore.dispatcher.__init__(self, sock)

        self.__session_id = self.__session_store.new(host=socket.getfqdn(address[0]))
        self.__broker.add_session(self.__session_id)
        self.__buffer = bytearray()
        self.__decoder = tld.Decoder()
        self.__decoder.add_listener(self.__message_received__)

        log.debug("Session created successfully: %s", self.__session_id)

        self.__write_protocol_info__()

    def inject(self, broker: broker.Broker, session_store: session.Store):
        self.__broker = broker
        self.__session_store = session_store

    def writable(self):
        msg = self.__broker.pop(self.__session_id)

        if msg:
            self.__buffer.extend(msg)
            self.__shutdown = (len(msg) >= 2 and msg[1] == 103)

        return bool(self.__buffer) or self.__shutdown

    def handle_write(self):
        if len(self.__buffer) > 0:
            data = self.__buffer[:1024]
            sent = self.send(data)
            self.__buffer = self.__buffer[sent:]
        elif self.__shutdown:
            self.__shutdown__()

    def handle_read(self):
        if not self.__shutdown:
            data = self.recv(1024)

            try:
                self.__decoder.write(data)

            except exception.TldResponseException as ex:
                self.__broker.deliver(self.__session_id, ex.response)
                self.__broker.deliver(self.__session_id, tld.encode_empty_cmd("g"))

            except Exception as ex:
                log.fatal("Unexpected error: session='%s', reason=%s", self.__session_id, str(ex))

                self.__broker.deliver(self.__session_id, tld.encode_str("e", "An unexpected error occured."))
                self.__broker.deliver(self.__session_id, tld.encode_empty_cmd("g"))
    
    def handle_close(self):
        self.__shutdown__()

    def __shutdown__(self):
        log.info("Closing session: '%s'", self.__session_id)

        commands.UserSession().sign_off(self.__session_id)

        self.__broker.remove_session(self.__session_id)
        self.__session_store.delete(self.__session_id)

        self.close()

    def __message_received__(self, type_id, payload):
        log.debug("Received message: type='%s', session='%s', payload (size)=%d", type_id, self.__session_id, len(payload))

        msg = MESSAGES.get(type_id)

        self.__session_store.update(self.__session_id, t_recv=Timer())

        if not msg:
            self.__broker.deliver(self.__session_id, tld.encode_str("e", "Unexpected message: '%s'" % type_id))
        else: 
            msg.process(self.__session_id, tld.split(payload))

    def __write_protocol_info__(self):
        e = tld.Encoder("j")

        e.add_field_str(PROTOCOL_VERSION)
        e.add_field_str(config.HOSTNAME, append_null=True)
        e.add_field_str(config.SERVER_ID, append_null=True)

        self.__broker.deliver(self.__session_id, e.encode())

if __name__ == "__main__":
    log.info("Starting server...")

    c = di.default_container

    c.register(broker.Broker, broker.Memory())
    c.register(session.Store, session.MemoryStore())
    c.register(groups.Store, groups.MemoryStore())
    c.register(database.Connection, sqlite.Connection(config.SQLITE_DB))
    c.register(nickdb.NickDb, sqlite.NickDb)

    with c.resolve(database.Connection).enter_scope() as scope:
        c.resolve(nickdb.NickDb).setup(scope)
        scope.complete()

    s = Server(config.SERVER_ADDRESS)
    asyncore.loop()
