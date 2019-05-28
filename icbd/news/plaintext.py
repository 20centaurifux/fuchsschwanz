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
import os
import os.path
import re
import news

class News(news.News):
    def __init__(self, path):
        self.__path = path

    def all(self):
        items = []

        for f in os.listdir(self.__path):
            m = re.match("news\\.(\\d+)", f)

            if m:
                items.append(int(m.group(1)))

        return [self.get_item(n) for n in sorted(items)]

    def get_item(self, n):
        return self.__load_file__("news.%d" % n)

    def __load_file__(self, filename):
        contents = None

        try:
            path = os.path.join(self.__path, filename)

            with open(path) as f:
                contents = f.read()

            contents = [l.rstrip() for l in contents.split("\n")][:-1]
        except: pass

        return contents
