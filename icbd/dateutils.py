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
from datetime import datetime
import pytz

def now():
    return pytz.utc.localize(datetime.utcnow())

def timestamp():
    return int(now().timestamp())

def elapsed_time(elapsed):
    total_seconds = int(elapsed)
    total_minutes = int(total_seconds / 60)
    total_hours = int(total_minutes / 60)
    minutes = total_minutes - (total_hours * 60)

    parts = []

    if total_hours > 23:
        days = int(total_hours / 24)

        parts.append("%dd" % days)

        hours = total_hours - (days * 24)

        if hours > 0:
            parts.append("%dh" % hours)

        if minutes > 0:
            parts.append("%dm" % minutes)
    elif total_hours > 0:
        parts.append("%dh" % total_hours)

        if minutes > 0:
            parts.append("%dm" % minutes)
    elif total_minutes > 0:
        parts.append("%dm" % minutes)
    else:
        parts.append("%ds" % total_seconds)

    return "".join(parts)
