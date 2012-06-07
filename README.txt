Pyppet2 - June, 2012
by The Blender Research Lab. (Philippines)
http://pyppet.blogspot.com
License: BSD

======================================================
Basic Usage:
	./Pyppet.sh

Installing:
	./install-fedora.sh


Known Issues:
	. Only works on Fedora, (Ubuntu is broken)

	. Xembed only works on Linux

	. the wnck-helper.py is a hack that may leave a dead Blender window open

	. keyboard entry fails on Gtk widgets if Blender's screen is clicked
		( moving the Pyppet window captures keyboard focus again )

	. the UV/image editor must be open for WebGL streaming textures to work

	. Blender window xembed only works properly in Gnome3 desktop

	. Drag'n'drop will freeze up if you drag over the blender window before its embedded
		[ workaround: always embed blenders window before using drag and drop ]


=============================================================

=============================================================
For Developers:
	run ./gtk-blender-helloworld.sh
	read the source in "pyppet/helloworld.py"

The generic GTK/Blender API is in "pyppet/core.py"
This will be documented later...

======================================================

Fedora16 Notes:
	Chromium is easier to install with Fedora than Google-Chrome
	go to "chrome://flags/" and make sure "Override software rendering list" is enabled
	http://morecode.wordpress.com/2012/01/15/enabling-webgl-with-fedora-16/



======================================================

	Ubuntu 11.10 32/64bits:	(BROKEN)
		[Google Chrome]
		http://www.liberiangeek.net/2011/12/install-google-chrome-using-apt-get-in-ubuntu-11-10-oneiric-ocelot/

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

