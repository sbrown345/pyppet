Pyppet2 - March, 2012
by The Blender Research Lab. (Philippines)
http://pyppet.blogspot.com
License: BSD

======================================================
Basic Usage:
	./Pyppet.sh

If Blender opens without the GTK interface, the installer failed.

Installing:
	./install-ubuntu.sh

======================================================
Installing a better GTK3 Theme
	Pyppet has been optimized to work with a dark GTK theme.
	AtoLm by the DeviantMars is included, you can install it by extracting to:
	"/usr/share/themes"
	Then use gnome-tweak-tool to select the theme

========================================================

Installing Libraries:

	Ubuntu 11.10 32/64bits:
		apt-get:
			bluez
			bluetooth
			libfreenect-dev
			libfftw3-dev
			libCV-dev
			libhighgui-dev
			libsdl-dev
			libopenal-dev
			libilmbase-dev
			libopenexr-dev
			libopenjpeg-dev
			libspnav-dev
			python-wnck
			libgtk-3-dev
			libfluidsynth-dev
			libode-dev
			libmlt-dev
			libavcodec-dev
			libavformat-dev


	Wiiuse:
		apt-get install bluez bluetooth
		git clone http://github.com/rpavlik/wiiuse.git


=============================================================
Known Issues:
	. Xembed only works on Linux, and better with Gnome3 (Ubuntu Unity has problems?)

	. the wnck-helper.py is a hack that may leave a dead Blender window open

	. keyboard entry fails on Gtk widgets if Blender's screen is clicked
		( moving the Pyppet window captures keyboard focus again )

	. the UV/image editor must be open for WebGL streaming textures to work


======================================================
For Developers:
	run ./gtk-blender-helloworld.sh
	read the source in "pyppet/helloworld.py"

The generic GTK/Blender API is in "pyppet/core.py"
This will be documented later...

======================================================

