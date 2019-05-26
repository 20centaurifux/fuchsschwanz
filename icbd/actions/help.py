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
import traceback
from actions import Injected
import tld
from exception import TldErrorException

class Help(Injected):
    def introduction(self, session_id, msgid=""):
        contents = self.__read_contents__(self.manual.introduction)

        if not contents:
            raise TldErrorException("No help available.")

        self.__send_contents__(session_id, contents, msgid)

    def query(self, session_id, q, msgid=""):
        domain = None

        if q.startswith("/"):
            domain = "Command"
            contents = self.__read_contents__(lambda: self.manual.command(q[1:]))
        else:
            domain = "Topic"
            contents = self.__read_contents__(lambda: self.manual.topic(q))

        if not contents:
            raise TldErrorException("%s '%s' not found." % (domain, q))

        self.__send_contents__(session_id, contents, msgid)

    def __read_contents__(self, fn):
        contents = None

        try:
            contents = fn()
        except:
            self.log.warning(traceback.format_exc())

        return contents

    def __send_contents__(self, session_id, contents, msgid):
        for line in contents.split("\n")[:-1]:
            self.broker.deliver(session_id, tld.encode_co_output(line, msgid))
