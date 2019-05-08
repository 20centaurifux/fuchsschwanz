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
import sqlite3, database
from secrets import token_hex
from hashlib import sha256
from logger import log
from datetime import datetime
import nickdb

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
    def __init__(self, db, **kwargs):
        database.Connection.__init__(self)

        self.__conn = None
        self.__db = db

    def __connect__(self):
        if self.__conn == None:
            self.__conn = sqlite3.connect(self.__db)
            self.__conn.row_factory = sqlite3.Row

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

class NickDb(nickdb.NickDb):
    def setup(self, scope):
        revision = self.__get_revision__(scope)

        if revision == 0:
            self.__create_tables__(scope)
            self.__create_admin__(scope)
        elif revision > 1:
            raise Exception("Unsupported database version.")

    def __get_revision__(self, scope):
        revision = 0

        cur = scope.get_handle()
        cur.execute("select count(name) FROM sqlite_master where type='table' AND name='Version'")

        if cur.fetchone()[0] == 1:
            cur.execute("select Revision FROM Version limit 1")
            revision = cur.fetchone()[0]

        return revision

    def __create_tables__(self, scope):
        log.info("Creating initial database.")

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
                         primary key (Name))""")

    def __create_admin__(self, scope):
        log.info("Creating admin account: username='admin', password='trustno1'")

        self.create(scope, "admin")

        self.set_admin(scope, "admin", True)
        self.set_password(scope, "admin", "trustno1")
        self.set_secure(scope, "admin", True)

    def create(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("insert into Nick (Name) values (?)", (nick, ))

        return self.lookup(scope, nick)

    def exists(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select count(Name) from Nick where Name=?", (nick,))

        return cur.fetchone()[0] == 1

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

    def set_password(self, scope, nick, password):
        cur = scope.get_handle()

        salt = token_hex(20)
        cur.execute("update Nick set Salt=?, Password=? where Name=?", (salt, self.__hash_password__(password, salt), nick))

    def check_password(self, scope, nick, password):
        cur = scope.get_handle()
        cur.execute("select Salt, Password from Nick where Name=?", (nick,))

        row = cur.fetchone()
        success = False

        if not row is None:
            salt, hash = row

            if salt is not None and hash is not None:
                success = (hash == self.__hash_password__(password, salt))

        return success

    def __hash_password__(self, plain, salt):
        return sha256((plain + salt).encode("ascii")).hexdigest()

    def is_secure(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select IsSecure from Nick where Name=?", (nick,))

        return bool(cur.fetchone()["IsSecure"])

    def set_secure(self, scope, nick, secure):
        cur = scope.get_handle()
        cur.execute("update Nick set IsSecure=? where Name=?", (int(secure), nick))

    def is_admin(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select IsAdmin from Nick where Name=?", (nick,))

        return bool(cur.fetchone()["IsAdmin"])

    def set_admin(self, scope, nick, is_admin):
        cur = scope.get_handle()
        cur.execute("update Nick set IsAdmin=? where Name=?", (int(is_admin), nick))

    def get_lastlogin(self, scope, nick):
        info = None

        cur = scope.get_handle()
        cur.execute("select LastLoginID, LastLoginHost from Nick where Name=?", (nick,))

        row = cur.fetchone()

        if not row["LastLoginID"] is None and not row["LastLoginHost"] is None:
            info = (row["LastLoginID"], row["LastLoginHost"])

        return info

    def set_lastlogin(self, scope, nick, loginid, host):
        cur = scope.get_handle()
        cur.execute("update Nick set LastLoginID=?, LastLoginHost=? where Name=?", (loginid, host, nick))

    def get_signon(self, scope, nick):
        signon = None

        cur = scope.get_handle()
        cur.execute("select Signon from Nick where Name=?", (nick,))

        row = cur.fetchone()

        if not row["Signon"] is None:
            signon = datetime.fromtimestamp(row["Signon"])

        return signon

    def set_signon(self, scope, nick, timestamp=None):
        cur = scope.get_handle()

        if timestamp is None:
            timestamp = datetime.utcnow()

        cur.execute("update Nick set Signon=? where Name=?", (int(timestamp.timestamp()), nick))

    def get_signoff(self, scope, nick):
        signoff = None

        cur = scope.get_handle()
        cur.execute("select Signoff from Nick where Name=?", (nick,))

        row = cur.fetchone()

        if not row["Signoff"] is None:
            signoff = datetime.fromtimestamp(row["Signoff"])

        return signoff

    def set_signoff(self, scope, nick, timestamp=None):
        cur = scope.get_handle()

        if timestamp is None:
            timestamp = datetime.utcnow()

        cur.execute("update Nick set Signoff=? where Name=?", (int(timestamp.timestamp()), nick))

    def delete(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("delete from Nick where Name=?", (nick,))
