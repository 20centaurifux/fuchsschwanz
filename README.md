# Fuchsschwanz

Here I create my own [icbd](http://www.icb.net/) implementation just for fun.

The project is at a *very* early stage. The following features are implemented:

* SSL support
* UTF-8 support instead of ANSI
* user login & authentication (/secure and /nosecure mode)
* user registration
* setting personal information
* away status
* delete users
* change group
* change nick
* public messages
* group topics
* group visibility (visible, secret, invisible)
* group volume (quiet, normal, loud)
* group control (public, moderated, restricted, controlled)
* boot users (automatically)
* private messages
* personal message box
* "beep" users
* echoback
* permission management (group moderators & admins)
* query online users
* notify sign on/off
* hush annoying users
* motd
* show news & version
* integrated help

You need Python 3.7 to start the server.

	$ ./run.sh

Configure network address & database path in the ./icbd/data/config.json file.

A test instance is running on internetcitizens.band (port 7326).
