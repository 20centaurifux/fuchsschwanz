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

class TransactionScope():
    def __init__(self, connection):
        self.__completed = False
        self.__listener = []
        self.__conn = connection

    def __enter__(self):
        self.__enter_scope__()

        for l in self.__listener:
            l.scope_entered(self)

        return self

    def __exit__(self, type, value, traceback):
        self.__leave_scope__(self.__completed)

        for l in self.__listener:
            l.scope_leaved(self)

    def complete(self):
        self.__completed = True

    def add_listener(self, listener):
        self.__listener.append(listener)

    def remove_listener(self, listener):
        self.__listener.append(listener)

    def get_handle(self): return None

    def __enter_scope__(self): pass

    def __leave_scope__(self, commit): pass

class Connection():
    def __init__(self):
        self.__scope = None

    def __enter__(self):
        return self

    def __exit__(self, t, value, traceback):
        self.close()

    def enter_scope(self):
        if self.__scope is not None:
            raise Exception("Cannot nest transaction scopes.")

        self.__scope = self.__create_transaction_scope__()
        self.__scope.add_listener(self)

        return self.__scope

    def __create_transaction_scope__(self): return None

    def close(self): pass

    def scope_entered(self, scope): pass

    def scope_leaved(self, scope):
        self.__scope = None
