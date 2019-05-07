# Fuchsschwanz

Here I create my own [icbd](http://www.icb.net/) implementation just for fun.

The project is at a *very* early stage. The following features are implemented:

* user login & authentication (/secure and /nosecure node)
* user registration
* changing groups
* changing nicks
* changing topics
* basic permission management (group moderators & admins)
* setting personal information

You need Python 3.7 to start the server.

	$ python3.7 ./icbd.py

Configure network address & database path in the ./config.py file.
