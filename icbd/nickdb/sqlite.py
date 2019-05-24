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
import sqlite3
import uuid
import secrets
import string
from hashlib import sha256
from datetime import datetime
from logging import Logger
import database
import nickdb
import core
import di
from textutils import tolower

class TransactionScope(database.TransactionScope):
    def __init__(self, db):
        database.TransactionScope.__init__(self, db)
        self.__db = db
        self.__cursor = None

    def __enter_scope__(self):
        self.__cursor = self.__db.cursor()

    def __leave_scope__(self, commit):
        if commit:
            self.__db.commit()
        else:
            self.__db.rollback()

    def get_handle(self):
        return self.__cursor

class Connection(database.Connection):
    def __init__(self, db):
        super().__init__()

        self.__conn = None
        self.__db = db

    def __connect__(self):
        if not self.__conn:
            self.__conn = sqlite3.connect(self.__db)
            self.__conn.row_factory = sqlite3.Row

            self.__conn.cursor().execute("pragma foreign_keys=on")

    def __create_transaction_scope__(self):
        self.__connect__()
        return TransactionScope(self)

    def cursor(self):
        return self.__conn.cursor()

    def commit(self):
        self.__conn.commit()

    def rollback(self):
        self.__conn.rollback()

    def close(self):
        if self.__conn is not None:
            self.__conn.close()

class NickDb(nickdb.NickDb, di.Injected):
    def __init__(self):
        super(NickDb, self).__init__()

    def inject(self, log: Logger):
        self.log = log

    def setup(self, scope):
        revision = self.__get_revision__(scope)

        if revision == 0:
            self.__create_tables__(scope)

            self.log.debug("Creating server account: nick='%s'", core.NICKSERV)

            self.__create_user__(scope, nick=core.NICKSERV, password=self.__generate_password__(), is_admin=False)

            password = self.__generate_password__()

            self.log.debug("Creating admin account: nick='admin'")

            self.__create_user__(scope, nick="admin", password=password, is_admin=True)

            self.log.info("Initial admin created with password '%s'." % password)
        elif revision > 1:
            raise Exception("Unsupported database version.")

    @staticmethod
    def __get_revision__(scope):
        revision = 0

        cur = scope.get_handle()
        cur.execute("select count(name) FROM sqlite_master where type='table' AND name='Version'")

        if cur.fetchone()[0] == 1:
            cur.execute("select Revision FROM Version limit 1")
            revision = cur.fetchone()[0]

        return revision

    def __create_tables__(self, scope):
        self.log.info("Creating initial database.")

        cur = scope.get_handle()

        cur.execute("""create table Version (
                         Revision integer not null)""")

        cur.execute("insert into Version (Revision) values (1)")

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

        cur.execute("create index foobar on Message (Receiver, Timestamp)")

    @staticmethod
    def __generate_password__():
        return "".join([secrets.choice(string.ascii_letters + string.digits) for _ in range(8)])

    def __create_user__(self, scope, nick, password, is_admin):
        self.create(scope, nick)

        self.set_admin(scope, nick, is_admin)
        self.set_password(scope, nick, password)
        self.set_secure(scope, nick, True)

    @tolower(argname="nick")
    def create(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("insert into Nick (Name) values (?)", (nick, ))

        return self.lookup(scope, nick)

    @tolower(argname="nick")
    def exists(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select count(Name) from Nick where Name=?", (nick,))

        return cur.fetchone()[0] == 1

    @tolower(argname="nick")
    def lookup(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select RealName, Phone, Address, Email, Text, WWW from Nick where Name=?", (nick,))

        m = cur.fetchone()

        return nickdb.UserDetails(real_name=m["RealName"],
                                  phone=m["Phone"],
                                  address=m["Address"],
                                  email=m["Email"],
                                  text=m["Text"],
                                  www=m["WWW"])

    @tolower(argname="nick")
    def update(self, scope, nick, details):
        cur = scope.get_handle()
        cur.execute("update Nick set RealName=?, Phone=?, Address=?, Email=?, Text=?, WWW=? where Name=?",
                    (details.real_name,
                     details.phone,
                     details.address,
                     details.email,
                     details.text,
                     details.www,
                     nick))

    @tolower(argname="nick")
    def set_password(self, scope, nick, password):
        cur = scope.get_handle()

        salt = secrets.token_hex(20)
        cur.execute("update Nick set Salt=?, Password=? where Name=?", (salt, self.__hash_password__(password, salt), nick))

    @tolower(argname="nick")
    def check_password(self, scope, nick, password):
        cur = scope.get_handle()
        cur.execute("select Salt, Password from Nick where Name=?", (nick,))

        row = cur.fetchone()
        success = False

        if row:
            salt, hash = row

            if salt is not None and hash is not None:
                success = (hash == self.__hash_password__(password, salt))

        return success

    @staticmethod
    def __hash_password__(plain, salt):
        return sha256((plain + salt).encode("ascii")).hexdigest()

    @tolower(argname="nick")
    def is_secure(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select IsSecure from Nick where Name=?", (nick,))

        return bool(cur.fetchone()[0])

    @tolower(argname="nick")
    def set_secure(self, scope, nick, secure):
        cur = scope.get_handle()
        cur.execute("update Nick set IsSecure=? where Name=?", (int(secure), nick))

    @tolower(argname="nick")
    def is_admin(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select IsAdmin from Nick where Name=?", (nick,))

        return bool(cur.fetchone()[0])

    @tolower(argname="nick")
    def set_admin(self, scope, nick, is_admin):
        cur = scope.get_handle()
        cur.execute("update Nick set IsAdmin=? where Name=?", (int(is_admin), nick))

    @tolower(argname="nick")
    def get_lastlogin(self, scope, nick):
        info = None

        cur = scope.get_handle()
        cur.execute("select LastLoginID, LastLoginHost from Nick where Name=?", (nick,))

        row = cur.fetchone()

        if row["LastLoginID"] and row["LastLoginHost"]:
            info = (row["LastLoginID"], row["LastLoginHost"])

        return info

    @tolower(argname="nick")
    def set_lastlogin(self, scope, nick, loginid, host):
        cur = scope.get_handle()
        cur.execute("update Nick set LastLoginID=?, LastLoginHost=? where Name=?", (loginid, host, nick))

    @tolower(argname="nick")
    def get_signon(self, scope, nick):
        signon = None

        cur = scope.get_handle()
        cur.execute("select Signon from Nick where Name=?", (nick,))

        row = cur.fetchone()

        if row[0]:
            signon = datetime.fromtimestamp(row[0])

        return signon

    @tolower(argname="nick")
    def set_signon(self, scope, nick, timestamp=None):
        cur = scope.get_handle()

        if not timestamp:
            timestamp = datetime.utcnow()

        cur.execute("update Nick set Signon=? where Name=?", (int(timestamp.timestamp()), nick))

    @tolower(argname="nick")
    def get_signoff(self, scope, nick):
        signoff = None

        cur = scope.get_handle()
        cur.execute("select Signoff from Nick where Name=?", (nick,))

        row = cur.fetchone()

        if row[0]:
            signoff = datetime.fromtimestamp(row[0])

        return signoff

    @tolower(argname="nick")
    def set_signoff(self, scope, nick, timestamp=None):
        cur = scope.get_handle()

        if not timestamp:
            timestamp = datetime.utcnow()

        cur.execute("update Nick set Signoff=? where Name=?", (int(timestamp.timestamp()), nick))

    @tolower(argname="nick")
    def get_mbox_limit(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select MBoxLimit from Nick where Name=?", (nick,))

        row = cur.fetchone()

        return int(row[0])

    def set_mbox_limit(self, scope, nick, limit):
        cur = scope.get_handle()
        cur.execute("update Nick set MBoxLimit=? where Name=?", (limit, nick))

    @tolower(argname="nick")
    def add_message(self, scope, nick, sender, text):
        msgid = uuid.uuid4().hex
        timestamp = int(datetime.utcnow().timestamp())

        cur = scope.get_handle()
        cur.execute("insert into Message (UUID, Sender, Receiver, Timestamp, Message) values (?, ?, ?, ?, ?)",
                    (msgid, sender, nick, timestamp, text))

        return msgid

    @tolower(argname="nick")
    def count_messages(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select count(UUID) from Message where Receiver=?", (nick,))

        return int(cur.fetchone()[0])

    @tolower(argname="nick")
    def get_messages(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select * from Message where Receiver=?", (nick,))

        return [nickdb.Message(uuid=uuid.UUID(row["UUID"]),
                               sender=row["Sender"],
                               date=datetime.fromtimestamp(row["Timestamp"]),
                               text=row["Message"])
                for row in cur]

    def delete_message(self, scope, msgid):
        cur = scope.get_handle()
        cur.execute("delete from Message where UUID=?", (msgid.hex,))

    @tolower(argname="nick")
    def delete(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("delete from Nick where Name=?", (nick,))