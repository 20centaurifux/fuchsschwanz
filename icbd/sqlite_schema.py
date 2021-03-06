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
import di

class Schema(di.Injected):
    def inject(self, log: Logger):
        self.log = log

    def upgrade(self, scope):
        revision = self.__get_revision__(scope)

        if revision == 0:
            self.__revision_1__(scope)
            revision += 1

        if revision == 1:
            self.__revision_2__(scope)
            revision += 1

        if revision == 2:
            self.__revision_3__(scope)
            revision += 1

        if revision == 3:
            self.__revision_4__(scope)

    @staticmethod
    def __get_revision__(scope):
        revision = 0

        cur = scope.get_handle()
        cur.execute("select count(name) from sqlite_master where type='table' AND name='Version'")

        if cur.fetchone()[0] == 1:
            cur.execute("select Revision from Version limit 1")
            revision = cur.fetchone()[0]

        return revision

    def __revision_1__(self, scope):
        self.log.info("Upgrading database to revision 1...")

        cur = scope.get_handle()

        cur.execute("""create table Version (
                         Revision integer not null)""")

        cur.execute("""create table Nick (
                         Name varchar(16) not null,
                         Password char(20),
                         Salt char(20),
                         RealName varchar(32),
                         Phone varchar(32),
                         Address varchar(64),
                         Email varchar(32),
                         Text varchar(128),
                         WWW varchar(32),
                         IsSecure integer not null default 0,
                         IsAdmin integer,
                         LastLoginID varchar(16),
                         LastLoginHost varchar(32),
                         Signon integer,
                         Signoff integer,
                         MBoxLimit integer not null default 0,
                         primary key (Name))""")

        cur.execute("""create table Message (
                         UUID char(32) not null,
                         Sender varchar(16) not null,
                         Receiver varchar(16) not null,
                         Timestamp integer not null,
                         Message varchar(128) not null,
                         primary key (UUID),
                         constraint fk_receiver
                           foreign key (Receiver)
                           references Nick(Name)
                           on delete cascade)""")

        cur.execute("create index MessageReceiver on Message (Receiver, Timestamp)")

        cur.execute("insert into Version (Revision) values (1)")

    def __revision_2__(self, scope):
        self.log.info("Upgrading database to revision 2...")

        cur = scope.get_handle()

        cur.execute("""create table Stats (
                         Year int not null,
                         Month int not null,
                         Day int not null,
                         Signons int default 0,
                         Boots int default 0,
                         Drops int default 0,
                         IdleBoots int default 0,
                         IdleMods int default 0,
                         MaxLogins int default 0,
                         MaxGroups int default 0,
                         MaxIdleTime read default 0.0,
                         MaxIdleNick varchar(16),
                         primary key (Year, Month, Day))""")

        cur.execute("create index MaxIdleTime on Stats (MaxIdleTime desc)")

        cur.execute("update Version set Revision=2")

    def __revision_3__(self, scope):
        self.log.info("Upgrading database to revision 3...")

        cur = scope.get_handle()

        cur.execute("""alter table Nick
                         add column IsProtected int not null default 1""")

        cur.execute("""alter table Nick
                         add column IsMailConfirmed int not null default 0""")

        cur.execute("""alter table Nick
                         add column ForwardMessages int not null default 0""")

        cur.execute("""create table ConfirmationRequest (
                         Nick varchar(16) not null,
                         Email varchar(32) not null,
                         Code varchar(32) not null,
                         Timestamp int not null,
                         constraint fk_requester
                           foreign key (Nick)
                           references Nick(Name)
                           on delete cascade)""")

        cur.execute("create index ConfirmationRequester on ConfirmationRequest (Nick asc, Email asc)")

        cur.execute("""create table PasswordReset (
                         Nick varchar(16) not null,
                         Code varchar(32) not null,
                         Timestamp int not null,
                         constraint fk_nick
                           foreign key (Nick)
                           references Nick(Name)
                           on delete cascade)""")

        cur.execute("create index PasswordNick on ConfirmationRequest (Nick asc)")

        cur.execute("""create table Mail (
                         UUID char(32) not null,
                         Receiver varchar(32) not null,
                         Subject varchar(64) not null,
                         Body varchar(512) not null,
                         Timestamp int not null,
                         Sent int not null default 0,
                         MTAErrors int not null default 0,
                         primary key (UUID))""")

        cur.execute("create index MailTimestamp on Mail (Timestamp asc)")
        cur.execute("create index MailSent on Mail (Sent asc)")

        cur.execute("update Version set Revision=3")

    def __revision_4__(self, scope):
        self.log.info("Upgrading database to revision 4...")

        cur = scope.get_handle()

        cur.execute("""alter table Mail
                         add column DueDate int not null default 0""")

        cur.execute("""alter table Nick
                         add column Avatar varchar(128)""")

        cur.execute("""create table Avatar (
                         Url varchar(128) not null,
                         Nick varchar(32) not null,
                         Active int not null default 0,
                         DueDate int not null,
                         Errors int not null default 0,
                         Hash varchar(64),
                         primary key (Url, Nick)
                         constraint fk_nick
                           foreign key (Nick)
                           references Nick(Name)
                           on delete cascade)""")

        cur.execute("""create table IPFilter (
                         Expression varchar(64) not null,
                         Action int not null default -1,
                         Lifetime int not null,
                         primary key (Expression, Action))""")

        cur.execute("update Version set Revision=4")
