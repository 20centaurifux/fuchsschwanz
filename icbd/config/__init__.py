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
from dataclasses import dataclass, field
from typing import List
import copy
import core

@dataclass
class Config:
    server_hostname: str = "localhost"
    server_unsecure_login: bool = False
    server_max_logins: int = 500
    server_ipc_binding: str = "unix:///tmp/fuchsschwanz.sock"
    bindings: List[str] = field(default_factory=list)
    logging_verbosity: core.Verbosity = core.Verbosity.INFO
    database_filename: str = None
    database_cleanup_interval: float = 3600.0
    mbox_limit: int = 25
    timeouts_connection: float = 120.0
    timeouts_ping: float = 45.0
    timeouts_away_message: float = 30.0
    timeouts_mbox_full_message: float = 30.0
    timeouts_idle_boot: int = core.DEFAULT_IDLE_BOOT
    timeouts_idle_mod: int = core.DEFAULT_IDLE_MOD
    timeouts_time_between_messages: float = 0.5
    timeouts_confirmation_request: float = 60.0
    timeouts_confirmation_code: float = 1800.0
    timeouts_password_reset_request: float = 60.0
    timeouts_password_reset_code: float = 1800.0
    mail_ttl: int = 480
    mail_max_errors: int = 3
    mail_interval: int = 60.0
    mail_retry_timeout: int = 120
    mail_cleanup_interval: int = 900
    smtp_hostname: str = "127.0.0.1"
    smtp_port: int = 25
    smtp_ssl_enabled: bool = False
    smtp_start_tls: bool = False
    smtp_sender: str = "root@localhost"
    smtp_username: str = None
    smtp_password: str = None
    avatar_directory: str = "avatars"
    avatar_max_file_size: int = 1024*2048
    avatar_max_width: int = 2048
    avatar_max_height: int = 2048
    avatar_thumbnail_width: int = 320
    avatar_thumbnail_height: int = 320
    avatar_ascii_width: int = 64
    avatar_ascii_height: int = 40
    avatar_interval: int = 900
    avatar_reload_timeout: int = 60 * 60 * 24
    avatar_retry_timeout: int = 300
    avatar_max_errors: int = 5
    avatar_error_timeout: int = 60 * 60 * 48

def transform_map(m):
    m = copy.deepcopy(m)

    try:
        m["logging_verbosity"] = core.Verbosity(m["logging_verbosity"])
    except KeyError: pass

    return m

def from_mapping(m):
    m = transform_map(m)

    return Config(**m)
