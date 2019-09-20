# Fuchsschwanz

Fuchsschwanz is a cross-platform [ICB](http://www.icb.net/) server written in Python. It's the
first ICB server supporting TLS, UTF-8 & IPv6 out of the box :)

# Running Fuchsschwanz

You need Python 3.7 to start the server. It requires a data directory and a
configuration file.

	$ python3.7 icbd/icbd.py --config=./config.json --data-dir=$(pwd)/data

The data directory contains help files, news and the message of the day (which
can be an executable!).

You can use the run.sh script to start the server. This script will also
generate a self-signed certificate for TLS (this requires openssl).

	$ AUTO_RESPAWN=1 ./run.sh # activate failure recovery

Running for the first time an administrative user will be created. You should
note down the password.

	2019-09-10 ... [icbd] INFO <sqlite.py, line 59> - Initial admin created with password '2vTOAlzv'.

# Configuration

Please find below a list with the most important settings.

## server

* hostname: hostname of your server

## bindings

Array containing network bindings (TCP and TCP over TCP).

	"bindings":
	[
		"tcp://localhost",
		"tcps://localhost?cert=./runtime/selfsigned.cert&key=./runtime/selfsigned.key"
	]

## timeouts

* connection: defines after what period of time (seconds) the peer TCP connection
  should be considered unreachable
* ping: a ping message is sent at this regular interval (seconds) if no
  activity from a client connection is detected
* timeBetweenMessages: minimum allowed seconds between two client messages
* idleBoot: default idle-boot setting for new created groups
* idleMod: default idle-mod setting for new created groups

## database

* filename: filename of the internal SQLite database
