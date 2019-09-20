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
import uuid
import secrets
from logging import Logger
from hashlib import sha256
from datetime import datetime
import nickdb
from sqlite_schema import Schema
import di
import core
from textutils import tolower, make_password
import dateutils

class NickDb(nickdb.NickDb, di.Injected):
    def __init__(self):
        super(NickDb, self).__init__()

    def inject(self, log: Logger):
        self.log = log

    def setup(self, scope):
        Schema().upgrade(scope)

        if not self.exists(scope, core.NICKSERV):
            self.log.debug("Creating server account: nick='%s'", core.NICKSERV)

            self.__create_user__(scope, nick=core.NICKSERV, password=make_password(8), is_admin=False)

            password = make_password(8)

        if not self.exists(scope, "admin"):
            self.log.debug("Creating admin account: nick='%s'", core.ADMIN)

            self.__create_user__(scope, nick=core.ADMIN, password=password, is_admin=True)

            self.log.info("Initial admin created with password '%s'." % password)

    def __create_user__(self, scope, nick, password, is_admin):
        cur = scope.get_handle()
        cur.execute("insert into Nick (Name, IsAdmin, IsSecure) values (?, ?, 1)", (nick, int(is_admin)))

        self.set_password(scope, nick, password)

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
        cur.execute("select RealName, Phone, Address, Email, Text, WWW, Avatar from Nick where Name=?", (nick,))

        m = cur.fetchone()

        return nickdb.UserDetails(real_name=m["RealName"],
                                  phone=m["Phone"],
                                  address=m["Address"],
                                  email=m["Email"],
                                  text=m["Text"],
                                  www=m["WWW"],
                                  avatar=m["Avatar"])

    @tolower(argname="nick")
    def update(self, scope, nick, details):
        cur = scope.get_handle()
        cur.execute("update Nick set RealName=?, Phone=?, Address=?, Email=?, Text=?, WWW=?, Avatar=? where Name=?",
                    (details.real_name,
                     details.phone,
                     details.address,
                     details.email,
                     details.text,
                     details.www,
                     details.avatar,
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
    def is_email_confirmed(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select IsMailConfirmed from Nick where Name=?", (nick,))

        return bool(cur.fetchone()[0])

    @tolower(argname="nick")
    def set_email_confirmed(self, scope, nick, confirmed):
        cur = scope.get_handle()
        cur.execute("update Nick set IsMailConfirmed=? where Name=?", (int(confirmed), nick))

    @tolower(argname="nick")
    def is_message_forwarding_enabled(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select ForwardMessages from Nick where Name=?", (nick,))

        return bool(cur.fetchone()[0])

    @tolower(argname="nick")
    def enable_message_forwarding(self, scope, nick, enabled):
        cur = scope.get_handle()
        cur.execute("update Nick set ForwardMessages=? where Name=?", (int(enabled), nick))

    @tolower(argname="nick")
    def is_protected(self, scope, nick):
        cur = scope.get_handle()
        cur.execute("select IsProtected from Nick where Name=?", (nick,))

        return bool(cur.fetchone()[0])

    @tolower(argname="nick")
    def set_protected(self, scope, nick, protected):
        cur = scope.get_handle()
        cur.execute("update Nick set IsProtected=? where Name=?", (int(protected), nick))

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
        timestamp = dateutils.now()

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
