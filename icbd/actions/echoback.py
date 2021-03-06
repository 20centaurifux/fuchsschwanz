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
import session
import ltd
from exception import LtdErrorException

class Echoback(Injected):
    def set_mode(self, session_id, mode):
        if not mode in ["on", "off", "verbose"]:
            raise LtdErrorException("Usage: /echoback on|off|verbose")

        real_mode = session.EchoMode.OFF

        if mode == "on":
            real_mode = session.EchoMode.ON
        elif mode == "verbose":
            real_mode = session.EchoMode.VERBOSE

        self.session.update(session_id, echo=real_mode)

        self.broker.deliver(session_id, ltd.encode_status_msg("Echo", "Echoback is now %s." % mode))
