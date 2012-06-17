# run: ~/Blender/blender --python helloworld-dnd.py

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
		win.set_title( 'hello world DND' )
		self.root = root = gtk.VBox()
		win.add( root )

		frame = gtk.Frame()
		frame.set_border_width( 10 )
		root.pack_start( frame, expand=False )
		button = gtk.Button('drag me onto the blender window')
		button.set_border_width( 10 )
		button.connect('clicked', self.on_click)
		frame.add( button )

		someobject = 'hello world (source)'
		DND.make_source( button, someobject, 'arg2', 'arg3', 'arg4' )


		xsocket, container = self.create_embed_widget(
			on_dnd = self.on_drop,
			on_resize = self.on_resize_blender,		# REQUIRED
			on_plug = self.on_plug_blender,		# REQUIRED
		)
		self.blender_container = container
		root.pack_start( self.blender_container )

		win.show_all()				# window and all widgets shown first
		xid = self.do_xembed( xsocket, 'Blender' )	# this must come last
		print('<< do xembed done >>')

	def on_click(self, button):
		print('you clicked')

	def on_drop(self, widget, gcontext, x, y, time):
		print( 'this is the widget you dropped on', widget )
		print( 'this is the widget you dragged from', DND.source_widget)
		print( 'mouse:', x,y )
		print( 'first extra argument from source-side', DND.source_object )
		print( 'all extra arguments from source-side', DND.source_args )

	def mainloop(self):
		self.active = True
		while self.active:
			self.update_blender_and_gtk()

########################################

app = MyApp()
app.mainloop()

