#!/usr/bin/python
# can not be run in the the same process with gtk3 #
import wnck	# apt-get install gnome-python-extras

screen = wnck.screen_get_default()
screen.force_update()
win = None
for w in screen.get_windows():
	if w.get_name() == 'Blender':
		print( 'FOUND BLENDER WINDOW', w )
		win = w
assert win
win.make_below()		# trick allows Pyppet not to be forced always-on-top
#x,y,width,height = win.get_geometry()
#win.set_geometry(x=x,y=height, width=width, height=height, gravity=1, geometry_mask=4)
print('SHADING...')
win.shade()

#time.sleep(10)
#print('UNSHADING...')
#win.unshade()

