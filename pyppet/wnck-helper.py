#!/usr/bin/python
# apt-get install gnome-python-extras
# can not be run in the the same process with gtk3 #
import sys
import wnck

NAME = 'Blender'
if len(sys.argv) > 1: NAME = sys.argv[-1]
print('wnck-helper looking for window named:', NAME)

screen = wnck.screen_get_default()
screen.force_update()
win = None
for w in screen.get_windows():
	if w.get_name() == 'Blender': win = w
assert win
win.make_below()		# trick allows Pyppet not to be forced always-on-top
win.shade()


