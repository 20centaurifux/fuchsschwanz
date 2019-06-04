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
from logging import Logger
from datetime import datetime
import di
import statsdb

class StatsDb(statsdb.StatsDb, di.Injected):
    def __init__(self):
        super(StatsDb, self).__init__()

        self.__running = statsdb.Stats()
        self.__stats = None
        self.__date = None

    def inject(self, log: Logger):
        self.log = log

    def setup(self, scope):
        revision = self.__get_revision__(scope)

        if revision == 1:
            self.__create_tables__(scope)

    @staticmethod
    def __get_revision__(scope):
        cur = scope.get_handle()
        cur.execute("select Revision FROM Version limit 1")

        return cur.fetchone()[0]

    def __create_tables__(self, scope):
        self.log.info("Creating stats table.")

        cur = scope.get_handle()

        cur.execute("""create table Stats (
                         Year int not null,
                         Month int not null,
                         Day int not null,
                         Signons int default 0,
                         Boots int default 0,
                         Drops int default 0,
                         Idleboots int default 0,
                         IdleMods int default 0,
                         primary key (Year, Month, Day))""")

        cur.execute("update Version set Revision=2")

    def add_signon(self, scope):
        self.__running.signons += 1
        self.__get_today__(scope).signons += 1
        self.__update_today__(scope)

    def add_boot(self, scope):
        self.__running.boots += 1
        self.__get_today__(scope).boots += 1
        self.__update_today__(scope)

    def add_drop(self, scope):
        self.__running.drops += 1
        self.__get_today__(scope).drops += 1
        self.__update_today__(scope)

    def add_idleboot(self, scope):
        self.__running.idleboots += 1
        self.__get_today__(scope).idleboots += 1
        self.__update_today__(scope)

    def add_idlemod(self, scope):
        self.__running.idlemods += 1
        self.__get_today__(scope).idlemods += 1
        self.__update_today__(scope)

    def __get_today__(self, scope):
        now = datetime.utcnow()

        if not self.__date or (self.__date.year != now.year or self.__date.month != now.month or self.__date.day != now.day):
            self.__date = now
            self.__stats = None

        if not self.__stats:
            cur = scope.get_handle()

            cur.execute("select * from Stats where Year=? and Month=? and Day=?", (self.__date.year, self.__date.month, self.__date.day))

            row = cur.fetchone()

            if row:
                self.__stats = self.__create_stats__(row)
            else:
                cur.execute("insert into Stats (Year, Month, Day) values (?, ?, ?) ",
                            (self.__date.year, self.__date.month, self.__date.day))

                self.__stats = statsdb.Stats()

        return self.__stats

    def __update_today__(self, scope):
        cur = scope.get_handle()

        cur.execute("update Stats set Signons=?, Boots=?, Drops=?, Idleboots=?, Idlemods=? where Year=? and Month=? and Day=?",
                    (self.__stats.signons, self.__stats.boots, self.__stats.drops, self.__stats.idleboots, self.__stats.idlemods,
                     self.__date.year, self.__date.month, self.__date.day))

    def start(self, scope):
        return self.__running

    def today(self, scope):
        return self.__get_today__(scope)

    def month(self, scope):
        now = datetime.utcnow()

        cur = scope.get_handle()

        cur.execute(self.__build_sum_query__("where Year=%d and Month=%d" % (now.year, now.month)))

        return self.__create_stats__(cur.fetchone())

    def year(self, scope):
        now = datetime.utcnow()

        cur = scope.get_handle()

        cur.execute(self.__build_sum_query__("where Year=%d" % now.year))

        return self.__create_stats__(cur.fetchone())

    def all(self, scope):
        cur = scope.get_handle()

        cur.execute(self.__build_sum_query__())

        return self.__create_stats__(cur.fetchone())

    @staticmethod
    def __build_sum_query__(where_clause=""):
        return """select sum(Signons) as Signons,
                         sum(Boots) as Boots,
                         sum(Drops) as Drops,
                         sum(IdleBoots) as IdleBoots,
                         sum(IdleMods) as IdleMods
                         from Stats %s""" % where_clause

    def __create_stats__(self, row):
        record = statsdb.Stats()

        if row:
            record.signons = row["Signons"]
            record.boots = row["Boots"]
            record.drops = row["Drops"]
            record.idleboots = row["Idleboots"]
            record.idlemods = row["Idlemods"]

        return record
