#!/usr/bin/python
# apt-get install gnome-python-extras
# can not be run in the the same process with gtk3 #
import wnck
screen = wnck.screen_get_default()
screen.force_update()
win = None
for w in screen.get_windows():
	if w.get_name() == 'Blender':
		print( 'FOUND BLENDER WINDOW', w )
		win = w
assert win
win.make_below()		# trick allows Pyppet not to be forced always-on-top
win.shade()


