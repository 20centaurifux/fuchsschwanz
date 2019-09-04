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
from email.mime.text import MIMEText
import smtplib
import mail

class MTA(mail.MTA):
    def __init__(self, host, port, ssl, start_tls, sender, username=None, password=None):
        self.server = host
        self.port = port
        self.ssl = ssl
        self.start_tls = start_tls
        self.sender = sender
        self.username = username
        self.password = password
        self.__client = None

    def start_session(self):
        if self.ssl:
            self.__client = smtplib.SMTP(self.server, self.port)
            self.__client.ehlo()
        else:
            self.__client = smtplib.SMTP()

        if self.start_tls:
            self.__client.starttls()
            self.__client.ehlo()

        self.__client.connect(self.server, self.port)

        if self.username and self.password:
            self.__client.login(self.username, self.password)

    def send(self, receiver, subject, body):
        msg = MIMEText(body, 'plain', 'utf-8')

        msg['Subject'] = subject.strip()
        msg['From'] = self.sender.strip()
        msg['To'] = receiver.strip()

        self.__client.sendmail(self.sender, [receiver], msg.as_string())

    def end_session(self):
        self.__client.quit()
