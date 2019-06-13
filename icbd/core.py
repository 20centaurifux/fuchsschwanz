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
from enum import Enum

NAME = "Fuchsschwanz"
VERSION = "0.1.3"

PROTOCOL_VERSION = "1.0"
PROTOCOL_LEVEL = 1

NICKSERV = "server"

DEFAULT_TOPIC = "If You Don't See the Fnord it Can't Eat You"
DEFAULT_GROUP = "1"

IDLE_GROUP = "~IDLE~"
IDLE_TOPIC = "Be Quiet and Drive (Far Away)"

BOOT_GROUP = "~OUTLAWS~"
BOOT_TOPIC = "Rebel Without a Cause"

class Verbosity(Enum):
    DEBUG = 4
    INFO = 3
    WARNING = 2
    ERROR = 1
    CRITICAL = 0

DEFAULT_IDLE_BOOT = 60
MIN_IDLE_BOOT = 15
MAX_IDLE_BOOT = 480

DEFAULT_IDLE_MOD = 480
MIN_IDLE_MOD = 15
MAX_IDLE_MOD = 480

MAX_INVITATION_LIST = 100
MAX_TALKER_LIST = 100
MAX_HUSH_LIST = 100
