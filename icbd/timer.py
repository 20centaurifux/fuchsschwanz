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
from timeit import default_timer as timer

class Timer:
    def __init__(self):
        self.restart()

    def restart(self):
        self.__timer = timer()

    def elapsed(self):
        return timer() - self.__timer

    def elapsed_str(self):
        total_seconds = int(self.elapsed())
        total_minutes = int(total_seconds / 60)
        total_hours = int(total_minutes / 60)
        minutes = total_minutes - (total_hours * 60)

        if total_hours > 0:
            time_elapsed = "%dh%dm"  % (total_hours, minutes)
        elif total_minutes > 0:
            time_elapsed = "%dm"  % minutes
        else:
            time_elapsed = "%ds"  % total_seconds

        return time_elapsed

class TimeoutTable:
    def __init__(self):
        self.__m = {}

    def is_alive(self, target, source):
        alive = False

        sources = self.__m.get(target, {})

        t = sources.get(source, None)

        if t:
            timer, timeout = t

            alive = timer.elapsed() < timeout

            if not alive:
                del sources[source]

                if not sources:
                    del self.__m[target]

        return alive

    def set_alive(self, target, tag, timeout_seconds):
        m = self.__m.get(target, {})

        m[tag] = (Timer(), timeout_seconds)

        self.__m[target] = m

    def remove_target(self, target):
        if target in self.__m:
            del self.__m[target]

    def remove_source(self, source):
        for sources in self.__m.values():
            if source in sources:
                del sources[source]

        self.__m = dict(kv for kv in self.__m.items() if len(kv) > 0)
