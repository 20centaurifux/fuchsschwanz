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
from actions import Injected
import core
import news
import ltd
from exception import LtdStatusException

class Info(Injected):
    def __init__(self):
        super().__init__()

        self.news = self.resolve(news.News)

    def version(self, session_id, msgid=""):
        self.broker.deliver(session_id, ltd.encode_co_output("%s v%s" % (core.NAME, core.VERSION), msgid))
        self.broker.deliver(session_id,
                            ltd.encode_co_output("Protocol Level: %d Max Users: %d" % (core.PROTOCOL_LEVEL, self.config.server_max_logins),
                                                 msgid))

    def all_news(self, session_id, msgid=""):
        news = self.news.all()

        if not news:
            raise LtdStatusException("News", "No news.")

        self.broker.deliver(session_id, ltd.encode_co_output("-" * 64, msgid))
        
        for item in news:
            for line in item:
                self.broker.deliver(session_id, ltd.encode_co_output(line, msgid))

            self.broker.deliver(session_id, ltd.encode_co_output("-" * 64, msgid))

    def news_item(self, session_id, news_item, msgid=""):
        item = self.news.get_item(news_item)

        if not item:
            raise LtdStatusException("News", "Entry not found.")

        self.broker.deliver(session_id, ltd.encode_co_output("-" * 64, msgid))

        for line in item:
            self.broker.deliver(session_id, ltd.encode_co_output(line, msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("-" * 64, msgid))

    def stats(self, session_id, timeframe="s", msgid=""):
        nickserv_id = self.session.find_nick(core.NICKSERV)
        nickserv_state = self.session.get(nickserv_id)

        stats = None
        description = None

        with self.statsdb_connection.enter_scope() as scope:
            if timeframe == "s":
                stats = self.statsdb.start(scope)
                description = "since start"
            elif timeframe == "t":
                stats = self.statsdb.today(scope)
                description = "today"
            elif timeframe == "m":
                stats = self.statsdb.month(scope)
                description = "this month"
            elif timeframe == "y":
                stats = self.statsdb.year(scope)
                description = "this year"
            elif timeframe == "a":
                stats = self.statsdb.all(scope)
                description = "overall"

        users_n = len(self.session) - 1
        groups_n = len(self.groups)
        away_n = len([kv for kv in self.session if kv[1].away])

        user_args = [users_n, "" if users_n == 1 else "s", groups_n, "" if groups_n == 1 else "s", away_n, "" if away_n == 1 else "s"]

        self.broker.deliver(session_id, ltd.encode_co_output("Server Settings:", msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("  Version: %s v%s" % (core.NAME, core.VERSION), msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("  Protocol Level: %d, Max Users: %d"
                                                             % (core.PROTOCOL_LEVEL, self.config.server_max_logins),
                                                             msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("", msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("General:", msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("  Started: %s (UTC)" % nickserv_state.signon, msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("  Logins: %d user%s in %d group%s (%d away user%s)"
                                                             % tuple(user_args), msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("", msgid))

        self.broker.deliver(session_id, ltd.encode_co_output("Server Stats (%s):" % description, msgid))

        self.broker.deliver(session_id,
                            ltd.encode_co_output("  Signons: %d, Boots: %d, Drops: %d" % (stats.signons, stats.boots, stats.drops), msgid))

        self.broker.deliver(session_id,
                            ltd.encode_co_output("  Idle-Boots: %d, Idle-Boots (mod): %d" % (stats.idleboots, stats.idlemods), msgid))
