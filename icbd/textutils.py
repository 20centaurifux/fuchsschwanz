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
import inspect
import secrets
import string

def decode(data):
    text = ""

    if data:
        text = data.decode("UTF-8", errors="backslashreplace")

    return text

def tolower(argname=None, argnames=None):
    def decorator(fn):
        spec = inspect.getfullargspec(fn)

        def wrapper(*args):
            vals = []

            for i in range(len(args)):
                val = args[i]

                if (argname and spec.args[i] == argname) or (argnames and spec.args[i] in argnames):
                    val = val.lower()

                vals.append(val)

            return fn(*vals)

        return wrapper

    return decorator

def hide_chars(text):
    hidden = ""

    if text:
        hidden = len(text) * "*"

    return hidden

def make_password(length):
    return "".join([secrets.choice(string.ascii_letters + string.digits) for _ in range(length)])
