Pyppet2 - Feb4 2012
by Brett Hart - bhartsho@yahoo.com
http://pyppet.blogspot.com
License: BSD

Usage:
	./Pyppet.sh

The script "Pyppet.sh" expects you have installed Blender to "~/Blender2.6"
You can modify Pyppet.sh to match the path to your installed Blender.

======================================================

Requires:
	Linux
	Blender2.6.1
	GTK3
	ODE

WebGL:
	Tested with Google Chrome 15.0.874.121


======================================================

Installing Libraries:
	You must install and/or compile these libraries to "/usr/lib" or "/usr/local/lib":
		. gtk3
		. opencv
		. SDL
		. libfreenect
		. ode (open dynamics engine)
		. wnck
		. fftw3
		. openAL

	Ubuntu:
		you can apt-get all of the required librarys

	Wnck:
		sudo apt-get install python-wnck

	Libfreenect:
		git clone https://github.com/OpenKinect/libfreenect.git
		cd libfreenect
		mkdir build
		cd build
		cmake -g "Unix Makefiles" ../.
		make
		sudo make install

	Wiiuse:
		apt-get install bluez bluetooth
		git clone http://github.com/rpavlik/wiiuse.git

========================================================

Known Issues:
	. Xembed only works on Linux, what about OSX with X11?
	. the wnck-helper.py is a hack that leaves a dead Blender window open
	. keyboard entry fails on Gtk widgets if Blender's screen is clicked
		( moving the Pyppet window captures keyboard focus again )

