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
import re

def has_valid_length(text, min_length, max_length):
    return len(text) >= min_length and len(text) <= max_length

NICK_MIN = 1
NICK_MAX = 12

def is_valid_nick(nick):
    return re.match(r"^[\w\-]{1,12}$", nick)

LOGINID_MIN = 1
LOGINID_MAX = 12

def is_valid_loginid(loginid):
    return re.match(r"^[A-Za-z0-9\-]{1,12}$", loginid)

GROUP_MIN = 1
GROUP_MAX = 12

def is_valid_group(group):
    return has_valid_length(group, GROUP_MIN, GROUP_MAX)

TOPIC_MIN = 0
TOPIC_MAX = 64

def is_valid_topic(topic):
    return has_valid_length(topic, TOPIC_MIN, TOPIC_MAX)

PASSWORD_MIN = 6
PASSWORD_MAX = 64

def is_valid_password(password):
    return has_valid_length(password, PASSWORD_MIN, PASSWORD_MAX)

REALNAME_MIN = 0
REALNAME_MAX = 12

def is_valid_realname(real_name):
    return has_valid_length(real_name, REALNAME_MIN, REALNAME_MAX)

ADDRESS_MIN = 0
ADDRESS_MAX = 64

def is_valid_address(address):
    return has_valid_length(address, ADDRESS_MIN, ADDRESS_MAX)

PHONE_MIN = 0
PHONE_MAX = 24

def is_valid_phone(phone):
    return has_valid_length(phone, PHONE_MIN, PHONE_MAX)

EMAIL_MIN = 0
EMAIL_MAX = 32

def is_valid_email(email):
    valid = False

    if has_valid_length(email, EMAIL_MIN, EMAIL_MAX):
        valid = not email or re.match(r"^(.+)@(.+)\.(.+)$", email)

    return valid

TEXT_MIN = 0
TEXT_MAX = 128

def is_valid_text(text):
    return has_valid_length(text, TEXT_MIN, TEXT_MAX)

WWW_MIN = 0
WWW_MAX = 32

def is_valid_www(www):
    return has_valid_length(www, WWW_MIN, WWW_MAX)

MESSAGE_MIN = 1
MESSAGE_MAX = 128

def is_valid_message(msg):
    return has_valid_length(msg, MESSAGE_MIN, MESSAGE_MAX)
