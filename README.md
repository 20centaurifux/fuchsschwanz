# Fuchsschwanz

Here I create my own [icbd](http://www.icb.net/) implementation just for fun.

The project is at a *very* early stage. The following features are implemented:

* user login & authentication (/secure and /nosecure node)
* user registration
* setting personal information
* delete users
* change group
* change nick
* change topic
* basic permission management (group moderators & admins)

You need Python 3.7 to start the server.

	$ python3.7 ./icbd.py

Configure network address & database path in the ./config.py file.
