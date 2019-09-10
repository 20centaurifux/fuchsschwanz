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
import logging
from core import Verbosity

LOG_LEVELS = {Verbosity.DEBUG: logging.DEBUG,
              Verbosity.INFO: logging.INFO,
              Verbosity.WARNING: logging.WARNING,
              Verbosity.ERROR: logging.ERROR,
              Verbosity.CRITICAL: logging.CRITICAL}

DEFAULT_FORMAT = "%(asctime)s [%(name)s] %(levelname)s <%(filename)s, line %(lineno)d> - %(message)s"
PROTOCOL_FORMAT = "%(asctime)s [%(name)s] %(levelname)s - %(message)s"
SIMPLE_TEXT_FORMAT = "%(message)s"

def new_logger(name="", verbosity=Verbosity.DEBUG, fmt=DEFAULT_FORMAT):
    formatter = logging.Formatter(fmt=fmt)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)

    log = logging.getLogger(name)

    log.setLevel(LOG_LEVELS[verbosity])
    log.addHandler(handler)

    return log

class Registry:
    def __init__(self):
        self.__loggers = []

    def register(self, logger):
        self.__loggers.append(logger)

    def __len__(self):
        return len(self.__loggers)

    @property
    def loggers(self):
        return iter(self.__loggers)
