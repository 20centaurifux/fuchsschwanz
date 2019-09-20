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
from urllib.parse import urlparse, parse_qs
import re

def __parse_netloc__(netloc, port):
    m = {}
    match = re.match(r"(.+):(\d+)", netloc)

    if match:
        m["address"] = match.group(1)
        m["port"] = int(match.group(2))
    else:
        m["address"] = netloc
        m["port"] = port

    return m

def __parse_tcp_url__(url):
    return __parse_netloc__(url.netloc, 7326)

def __parse_tcps_url__(url):
    m = __parse_netloc__(url.netloc, 7327)

    q = parse_qs(url.query)

    for k in ("key", "cert"):
        m[k] = q[k][0]

    return m

def __parse_unix_url__(url):
    return {"path": url.path}

def parse_server_address(url):
    result = urlparse(url)

    m = None

    if result.scheme == "tcp":
        m = __parse_tcp_url__(result)
    elif result.scheme == "tcps":
        m = __parse_tcps_url__(result)
    elif result.scheme == "unix":
        m = __parse_unix_url__(result)

    if m:
        m["protocol"] = result.scheme

    return m
