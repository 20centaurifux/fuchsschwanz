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
import hashlib
import os
import avatar
import PIL.Image
import aalib

class AsciiFiles(avatar.Storage):
    def __init__(self, directory, width, height):
        self.__directory = directory
        self.__width = width
        self.__height = height

    def setup(self):
        if not os.path.exists(self.__directory):
            os.makedirs(self.__directory)

    def store(self, image):
        bytes = image.read()
        checksum = self.__checksum__(bytes)
        path = os.path.join(self.__directory, checksum)

        filename = path + ".png"

        if not os.path.isfile(filename):
            with open(filename, "wb") as f:
                f.write(bytes)

        txt = self.__to_ascii__(image)
        filename = path + ".txt"

        if not os.path.isfile(filename):
            with open(filename, "w") as f:
                f.write(txt)

        return checksum

    @staticmethod
    def __checksum__(bytes):
        return hashlib.sha256(bytes).hexdigest()

    def __to_ascii__(self, f):
        screen = aalib.AsciiScreen(width=self.__width, height=self.__height)

        image = PIL.Image.open(f).convert("L").resize(screen.virtual_size)

        screen.put_image((0, 0), image)

        return screen.render()

    def load(self, key):
        contents = None

        try:
            path = os.path.join(self.__directory, key + ".txt")

            with open(path) as f:
                contents = [l.rstrip() for l in f.read().split('\n')]
        except:
            pass

        return contents
