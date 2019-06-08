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
import config
import session
import reputation
import broker
import group
import nickdb
import statsdb
import di

class Injected(di.Injected):
    def inject(self,
               log: logging.Logger,
               config: config.Config,
               session: session.Store,
               reputation: reputation.Reputation,
               broker: broker.Broker,
               groups: group.Store,
               nickdb_connection: nickdb.Connection,
               nickdb: nickdb.NickDb,
               statsdb_connection: statsdb.Connection,
               statsdb: statsdb.StatsDb):
        self.log = log
        self.config = config
        self.session = session
        self.reputation = reputation
        self.broker = broker
        self.groups = groups
        self.nickdb_connection = nickdb_connection
        self.nickdb = nickdb
        self.statsdb_connection = statsdb_connection
        self.statsdb = statsdb

    def resolve(self, T):
        return di.default_container.resolve(T)

def cache():
    m = {}

    return lambda T: m.get(T, T())

class UserStatus(di.Injected):
    def inject(self, nickdb_connection: nickdb.Connection, nickdb: nickdb.NickDb):
        self.nickdb_connection = nickdb_connection
        self.nickdb = nickdb

    def get_flags(self, state, scope=None):
        flags = []

        if state.authenticated:
            flags.append("r")

            if scope:
                flags.extend(self.__lookup_flags__(scope, state.nick))
            else:
                with self.nickdb_connection.enter_scope() as scope:
                    flags.extend(self.__lookup_flags__(scope, state.nick))
        else:
            flags.append("nr")

        if state.away:
            flags.append("aw")

        if state.tls:
            flags.append("ssl")

        return flags

    def __lookup_flags__(self, scope, nick):
        flags = []

        user = self.nickdb.lookup(scope, nick)

        if self.nickdb.is_admin(scope, nick):
            flags.append("a")

        if not user.real_name:
            flags.append("nr")

        return flags

ACTION = cache()
