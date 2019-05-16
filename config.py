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
import logging

SERVER_ADDRESS = ("127.0.0.1", 7326)

HOSTNAME = "localhost"
SERVER_ID = "localhost v0.1.0"

NICKSERV = "server"

#MOTD_PATH = "/usr/bin/fortune"
MOTD_PATH = "./motd"

LOG_LEVEL = logging.DEBUG

DEFAULT_TOPIC = "If You Don't See the Fnord it Can't Eat You"
DEFAULT_GROUP = "1"

IDLE_GROUP = "~IDLE~"
IDLE_TOPIC = "Be Quiet and Drive (Far Away)"

SQLITE_DB = "./icbd.db"

ENABLE_UNSECURE_LOGIN = False

MBOX_DEFAULT_LIMIT = 20
MBOX_QUOTAS = {NICKSERV: 0}

AWAY_MSG_TIMEOUT = 30.0
