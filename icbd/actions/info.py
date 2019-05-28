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
import ltd
from exception import LtdStatusException

class Info(Injected):
    def version(self, session_id, msgid=""):
        self.broker.deliver(session_id, ltd.encode_co_output("%s v%s" % (core.NAME, core.VERSION), msgid))
        self.broker.deliver(session_id,
                            ltd.encode_co_output("Proto Level: %d Max Users: %d" % (core.PROTOCOL_LEVEL, self.config.server_max_logins),
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
