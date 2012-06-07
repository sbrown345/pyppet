#!/usr/bin/python
# apt-get install gnome-python-extras
# can not be run in the the same process with gtk3 #
import os, sys, time
import wnck

NAME = 'Blender'
use_startswith = '--use-starts-with' in sys.argv
use_icon_name = '--use-icon-name' in sys.argv
if len(sys.argv) >= 1: NAME = sys.argv[-1]


print('wnck-helper looking for window named:', NAME)

screen = wnck.screen_get_default()
screen.force_update()

if '--close-all-windows' in sys.argv:	# not working!
	#./wnck-helper.py --close-all-windows "Untitled window"
	for w in screen.get_windows():
		print( 'ICON NAME:', w.get_icon_name() )
		win = None
		if w.get_icon_name() == NAME:
			win = w
		elif use_startswith and w.get_icon_name().startswith(NAME):
			win = w
		if win:
			print('closing ->', win)
			pid = win.get_pid()
			print('pid', pid)
			if pid:
				os.system( 'kill -9 %s' %pid )
			win.shade()
			win.minimize()
			win.close( -1 )


else:
	wins = []
	for w in screen.get_windows():
		if use_icon_name:
			print( 'ICON NAME:', w.get_icon_name() )
			if w.get_icon_name() == NAME:
				wins.append( w )
			elif use_startswith and w.get_icon_name().startswith(NAME):
				wins.append( w )

		else:
			if use_startswith and w.get_name().startswith( NAME ):
				wins.append( w )
			elif NAME in w.get_name():
				wins.append( w )

	for win in wins:
		## make_below allows drag and drop/move in parent window to work
		## otherwise parent window must use always-on-top ##
		win.make_below()	# REQUIRED FOR BLENDER
		win.shade()
		print( 'XID=%s' %win.get_xid() )

screen.force_update()

