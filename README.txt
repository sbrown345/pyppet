Pyppet2 - Feb22, 2012
by The Blender Research Lab. (Philippines)
http://pyppet.blogspot.com
License: BSD

======================================================
Pyppet Requires:
	Linux
	Blender2.6.1
	GTK3
	ODE
	OpenCV
	Python-Wnck

GTK/Blender SDK Requires:
	Linux
	Blender2.6.1
	GTK3
	Python-Wnck

======================================================
Basic Usage:
	./Pyppet.sh

The script "Pyppet.sh" expects you have installed Blender to "~/Blender2.6"
You can modify Pyppet.sh to match the path to your installed Blender.

If Blender opens without the GTK interface, something is not installed correctly,
see Installing Libraries below. If your using Ubuntu, get GTK3 from the Gnome PPA.

======================================================
For Developers:
	run ./gtk-blender-helloworld.sh
	read the source in "pyppet/helloworld.py"

The generic GTK/Blender API is in "pyppet/core.py"
This will be documented later...

======================================================
Having a hard time installing GTK3 in Ubuntu?
http://abhizweblog.blogspot.com/2011/04/gnome-3-in-natty.html

======================================================
Installing a better GTK3 Theme
	Pyppet has been optimized to work with a dark GTK theme.
	AtoLm by the DeviantMars is included, you can install it by extracting to:
	"/usr/share/themes"
	Then use gnome-tweak-tool to select the theme

========================================================

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


======================================================
WebGL Notes:
	Tested with Google Chrome 15.0.874.121
	point browser to: http://localhost:8080
	( UV/image editor window must be open for streaming textures )


=============================================================
Known Issues:
	. Xembed only works on Linux.

	. the wnck-helper.py is a hack that leaves a dead Blender window open

	. keyboard entry fails on Gtk widgets if Blender's screen is clicked
		( moving the Pyppet window captures keyboard focus again )

	. the UV/image editor must be open for WebGL streaming textures to work

	. file open is not working
		workaround set the file you wish to open as your startup default

