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
import sqlite3
import database

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

            cur = self.__conn.cursor()

            cur.execute("pragma foreign_keys=on")
            cur.execute("pragma journal_mode=memory")
            cur.execute("pragma synchronous=normal")
            cur.execute("pragma locking_mode=exlusive")

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
