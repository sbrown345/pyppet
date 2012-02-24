#!/usr/bin/python
# apt-get install gnome-python-extras
# can not be run in the the same process with gtk3 #
import sys
import wnck

NAME = 'Blender'
use_startswith = '--use-starts-with' in sys.argv
use_icon_name = '--use-icon-name' in sys.argv
if len(sys.argv) >= 1: NAME = sys.argv[-1]


print('wnck-helper looking for window named:', NAME)

screen = wnck.screen_get_default()
screen.force_update()
win = None
for w in screen.get_windows():
	if use_icon_name:
		print( 'ICON NAME:', w.get_icon_name() )
		if w.get_icon_name() == NAME:
			win = w; break
		elif use_startswith and w.get_icon_name().startswith(NAME):
			win = w; break

	else:
		if w.get_name() == NAME:
			win = w; break
		elif use_startswith and w.get_name().startswith( NAME ):
			win = w; break

if win:
	win.make_below()		# trick allows Pyppet not to be forced always-on-top
	win.shade()
	print( 'XID=%s' %win.get_xid() )

screen.force_update()

