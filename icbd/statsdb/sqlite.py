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
from datetime import datetime
import statsdb
from sqlite_schema import Schema
import dateutils

class StatsDb(statsdb.StatsDb):
    def __init__(self):
        self.__running = statsdb.Stats()
        self.__stats = None
        self.__date = None

    def setup(self, scope):
        Schema().upgrade(scope)

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

    def set_max_logins(self, scope, max_logins):
        self.__set_max_logins__(self.__running, max_logins)
        self.__set_max_logins__(self.__get_today__(scope), max_logins)
        self.__update_today__(scope)

    @staticmethod
    def __set_max_logins__(stats, max_logins):
        stats.max_logins = max(stats.max_logins, max_logins)

    def set_max_groups(self, scope, max_groups):
        self.__set_max_groups__(self.__running, max_groups)
        self.__set_max_groups__(self.__get_today__(scope), max_groups)
        self.__update_today__(scope)

    @staticmethod
    def __set_max_groups__(stats, max_groups):
        stats.max_groups = max(stats.max_groups, max_groups)

    def set_max_idle(self, scope, idle_time, idle_nick):
        self.__set_max_idle__(self.__running, idle_time, idle_nick)
        self.__set_max_idle__(self.__get_today__(scope), idle_time, idle_nick)
        self.__update_today__(scope)

    @staticmethod
    def __set_max_idle__(stats, idle_time, idle_nick):
        max_idle = stats.max_idle[0] if stats.max_idle else 0.0

        if idle_time > max_idle:
            stats.max_idle = (idle_time, idle_nick)

    def __get_today__(self, scope):
        now = dateutils.now()

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

        cur.execute("""update Stats
                         set Signons=?,
                         Boots=?,
                         Drops=?,
                         IdleBoots=?,
                         IdleMods=?,
                         MaxLogins=?,
                         MaxGroups=?,
                         MaxIdleTime=?,
                         MaxIdleNick=?
                         where Year=? and Month=? and Day=?""",
                    (self.__stats.signons,
                     self.__stats.boots,
                     self.__stats.drops,
                     self.__stats.idleboots,
                     self.__stats.idlemods,
                     self.__stats.max_logins,
                     self.__stats.max_groups,
                     self.__stats.max_idle[0] if self.__stats.max_idle else None,
                     self.__stats.max_idle[1] if self.__stats.max_idle else None,
                     self.__date.year,
                     self.__date.month,
                     self.__date.day))

    def start(self, scope):
        return self.__running

    def today(self, scope):
        return self.__get_today__(scope)

    def month(self, scope):
        now = dateutils.now()

        cur = scope.get_handle()

        cur.execute(self.__build_accumulate_query__("where Year=%d and Month=%d" % (now.year, now.month)))

        return self.__create_stats__(cur.fetchone())

    def year(self, scope):
        now = dateutils.now()

        cur = scope.get_handle()

        cur.execute(self.__build_accumulate_query__("where Year=%d" % now.year))

        return self.__create_stats__(cur.fetchone())

    def all(self, scope):
        cur = scope.get_handle()

        cur.execute(self.__build_accumulate_query__())

        return self.__create_stats__(cur.fetchone())

    @staticmethod
    def __build_accumulate_query__(where_clause=""):
        return """select sum(Signons) as Signons,
                         sum(Boots) as Boots,
                         sum(Drops) as Drops,
                         sum(IdleBoots) as IdleBoots,
                         sum(IdleMods) as IdleMods,
                         max(MaxLogins) as MaxLogins,
                         max(MaxGroups) as MaxGroups,
                         max(MaxIdleTime) as MaxIdleTime,
                         (select (MaxIdleNick) from Stats %s order by MaxIdleTime desc limit 1) as MaxIdleNick
                         from Stats %s""" % (where_clause, where_clause)

    @staticmethod
    def __create_stats__(row):
        record = statsdb.Stats()

        if row:
            record.signons = row["Signons"]
            record.boots = row["Boots"]
            record.drops = row["Drops"]
            record.idleboots = row["IdleBoots"]
            record.idlemods = row["IdleMods"]
            record.max_logins = row["MaxLogins"]
            record.max_groups = row["MaxGroups"]

            if row["MaxIdleTime"] or row["MaxIdleNick"]:
                record.max_idle = (row["MaxIdleTime"], row["MaxIdleNick"])

        return record
