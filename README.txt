Pyppet2 - May, 2012
by The Blender Research Lab. (Philippines)
http://pyppet.blogspot.com
License: BSD

======================================================
Basic Usage:
	./Pyppet.sh

Installing:
	./install-fedora.sh

[ Pyppet development has moved from Ubuntu to Fedora ]

========================================================

Installing Libraries:
	Fedora 16:
		[Google Chrome]
		http://www.if-not-true-then-false.com/2010/install-google-chrome-with-yum-on-fedora-red-hat-rhel/


	Ubuntu 11.10 32/64bits:
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


=============================================================
Known Issues:
	. Xembed only works on Linux

	. the wnck-helper.py is a hack that may leave a dead Blender window open

	. keyboard entry fails on Gtk widgets if Blender's screen is clicked
		( moving the Pyppet window captures keyboard focus again )

	. the UV/image editor must be open for WebGL streaming textures to work

	. Blender window xembed only works properly in Gnome3 desktop

======================================================
For Developers:
	run ./gtk-blender-helloworld.sh
	read the source in "pyppet/helloworld.py"

The generic GTK/Blender API is in "pyppet/core.py"
This will be documented later...

======================================================

Fedora16 Notes:
	Chromium is easier to install with Fedora
	go to "chrome://flags/" and make sure "Override software rendering list" is enabled
	http://morecode.wordpress.com/2012/01/15/enabling-webgl-with-fedora-16/

	(Google Chrome not tested yet on Fedora)
	Add following to /etc/yum.repos.d/google.repo file:

[google-chrome]
name=google-chrome - 32-bit
baseurl=http://dl.google.com/linux/chrome/rpm/stable/i386
enabled=1
gpgcheck=1
gpgkey=https://dl-ssl.google.com/linux/linux_signing_key.pub
[google-chrome]
name=google-chrome - 64-bit
baseurl=http://dl.google.com/linux/chrome/rpm/stable/x86_64
enabled=1
gpgcheck=1
gpgkey=https://dl-ssl.google.com/linux/linux_signing_key.pub


