# run: ~/Blender/blender --python helloworld.py

'''
This error means you tried to xembed your window within itself!
	(blender:3656): Gtk-WARNING **: gtksocket.c:1049: Can't add non-GtkPlug to GtkSocket
	(blender:3656): Gdk-CRITICAL **: gdk_error_trap_pop_internal: assertion `trap != NULL' failed

'''

import os, sys, time
import bpy

## make sure we can import from same directory ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.append( SCRIPT_DIR )

from core import *		# core API
gtk.init()


class MyApp( BlenderHackLinux ):
	def __init__(self):
		assert self.setup_blender_hack( bpy.context )

		self.window = win = gtk.Window()
		win.connect('destroy', lambda w: setattr(self,'active',False) )
		win.set_title( 'helloworld' )	# note blender name not allowed here
		self.root = root = gtk.VBox()
		win.add( root )

		frame = gtk.Frame()
		frame.set_border_width( 10 )
		root.pack_start( frame, expand=False )
		button = gtk.Button('hello world')
		button.set_border_width( 10 )
		button.connect('clicked', self.on_click)
		frame.add( button )

		b = gtk.ToggleButton('testing')
		root.pack_start( b, expand=False )
		b.set_label('yyy')


		b = gtk.CheckButton('testing')
		root.pack_start( b, expand=False )
		b.set_label('xxx')

		xsocket, container = self.create_embed_widget(
			on_dnd = self.drop_on_view,
			on_resize = self.on_resize_blender,	# REQUIRED
			on_plug = self.on_plug_blender,		# REQUIRED
		)
		self.blender_container = container
		root.pack_start( self.blender_container )

		win.show_all()				# window and all widgets shown first
		self.do_xembed( xsocket, 'Blender' )	# this must come last


	def on_click(self, button):
		print('you clicked')


	def mainloop(self):
		self.active = True
		while self.active:
			self.update_blender_and_gtk()



########################################

app = MyApp()
app.mainloop()

