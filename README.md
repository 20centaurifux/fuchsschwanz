# Fuchsschwanz

Fuchsschwanz is a cross-platform [ICB](http://www.icb.net/) server written in Python. It supports
TLS and UTF-8 out of the box.

# Running Fuchsschwanz

You need Python 3.7 to start the server. It requires a data directory and a
configuration file.

	$ python3.7 icbd/icbd.py --config=./config.json --data-dir=$(pwd)/data

The data directory contains help files, news and the message of the day.

You can use the run.sh script to start the server. This script will also
generate a self-signed certificate for TLS (this requires openssl).

Running for the first time an administrative user will be created. You should
note down the password.

	2019-06-03 ... DEBUG ... Creating admin account: nick='admin'
	2019-06-03 ... INFO ... Initial admin created with password 'HPjkVtiS'.

# Configuration

Please find below a list with the most important settings.

## server

* hostname: hostname of your server

## tcp

* enabled: enable (true) or disable (false) TCP without encryption
* address, port: network address and port used for TCP connections

## tcp\_tls

* enabled: enable (true) or disable (false) TCP with TLS encryption
* address, port: network address and port used for encrypted TCP connections
* key, cert: private key and certificate

## mbox

* limit: message box limit for new registered users

## timeouts

* ping: the server sends a ping message at this interval (in seconds) if no other client activity is detected
* timeBetweenMessages: minimum allowed seconds between two client messages
* idleBoot: default idle-boot setting for new created groups
* idleMod: default idle-mod setting for new created groups

## database

* filename: filename of the internal SQLite database
