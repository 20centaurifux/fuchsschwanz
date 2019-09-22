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
from secrets import token_hex
import config
import di
import ltd
import url

class Broadcast:
    def __init__(self):
        self.__listeners = []

    def send(self, receiver, message):
        for l in self.__listeners:
            l(receiver, message)

    def add_listener(self, listener):
        self.__listeners.append(listener)

    def remove_listener(self, listener):
        self.__listeners.remove(listener)

class IPCServerProtocol(asyncio.Protocol, di.Injected):
    def __init__(self, connections):
        asyncio.Protocol.__init__(self)
        di.Injected.__init__(self)

        loop = asyncio.get_event_loop()

        self.__id = token_hex(20)
        self.__connections = connections
        self.__on_conn_lost = loop.create_future()

    def inject(self, log: logging.Logger):
        self.__log = log

    async def abort(self):
        self.__log.info("Aborting client connection: %s", self.__id)

        self.__transport.abort()

        await self.__on_conn_lost

    def connection_made(self, transport):
        self.__log.info("Client connected: %s", self.__id)

        self.__transport = transport

        self.__connections.append(self)

    def write(self, message):
        self.__transport.write(message)

    def data_received(self, data):
        pass

    def connection_lost(self, ex):
        self.__log.info("Client disconnected: %s", self.__id)

        self.__connections.remove(self)

        if ex:
            self.__log.info(ex)

        self.__transport.abort()
        self.__on_conn_lost.set_result(None)

class Bus(di.Injected):
    def inject(self, log: logging.Logger, config: config.Config, broadcast: Broadcast):
        self.__log = log
        self.__config = config
        self.__broadcast = broadcast
        self.__server = None
        self.__connections = []

        self.__broadcast.add_listener(self.__broadcast__)

    async def start(self):
        loop = asyncio.get_running_loop()

        self.__log.info("Starting IPC bus: %s", self.__config.server_ipc_binding)

        binding = url.parse_server_address(self.__config.server_ipc_binding)

        if binding["protocol"] == "tcp":
            self.__log.info("Listening on %s:%d (tcp)", binding["address"], binding["port"])

            self.__server = await loop.create_server(lambda: IPCServerProtocol(self.__connections), binding["address"], binding["port"])
        elif binding["protocol"] == "unix":
            self.__log.info("Listening on %s (unix)", binding["path"])

            self.__server = await loop.create_unix_server(lambda: IPCServerProtocol(self.__connections), binding["path"])
        else:
            raise NotImplementedError("Unsupported protocol: %s", binding["protocol"])

        await self.__server.start_serving()

    def __broadcast__(self, receiver, message):
        e = ltd.Encoder("m")

        e.add_field_str(receiver, append_null=False)
        e.add_field_str(message, append_null=True)

        pkg = e.encode()

        for c in self.__connections:
            c.write(pkg)

    async def close(self):
        self.__log.info("Stopping IPC bus.")

        self.__server.close()

        await self.__server.wait_closed()

        if self.__connections:
            self.__log.info("Aborting client connections...")

            await asyncio.gather(*[c.abort() for c in self.__connections])

            self.__log.info("All connections closed.")

class IPCClientProtocol(asyncio.Protocol):
    def __init__(self, on_conn_lost, queue):
        self.__on_conn_lost = on_conn_lost
        self.__transport = None
        self.__decoder = ltd.Decoder()
        self.__decoder.add_listener(self.__message_received__)
        self.__queue = queue

    def connection_made(self, transport):
        self.__transport = transport

    def data_received(self, data):
        try:
            self.__decoder.write(data)

        except Exception as ex:
            self.__shutdown__(ex)

    def connection_lost(self, ex):
        self.__shutdown__(ex)

    def __shutdown__(self, ex=None):
        self.__on_conn_lost.set_result(ex)

    def __message_received__(self, type_id, payload):
        self.__queue.put_nowait((type_id, payload))

class Client:
    def __init__(self, address):
        self.__address = address
        self.__queue = asyncio.Queue()
        self.__transport = None

    async def connect(self):
        loop = asyncio.get_event_loop()

        on_conn_lost = loop.create_future()

        binding = url.parse_server_address(self.__address)

        if binding["protocol"] == "tcp":
            self.__transport, _ = await loop.create_connection(lambda: IPCClientProtocol(on_conn_lost, self.__queue),
                                                                                         binding["address"],
                                                                                         binding["port"])
        elif binding["protocol"] == "unix":
            self.__transport, _ = await loop.create_unix_connection(lambda: IPCClientProtocol(on_conn_lost, self.__queue),
                                                                                              binding["path"])
        else:
            raise NotImplementedError("Unsupported protocol: %s", binding["protocol"])

        return on_conn_lost

    async def read(self):
        t, p = await self.__queue.get()

        if t == "m":
            fields = [f.decode("UTF-8").strip(" \0") for f in ltd.split(p)]

            if len(fields) == 2:
                return fields
