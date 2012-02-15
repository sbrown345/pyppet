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
		win.set_title( 'GtkBlender SDK' )
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

		self.blender_container = eb = gtk.EventBox()
		root.pack_start( self.blender_container )

		DND.make_destination(eb)
		extra_arg = 'hello world (destination)'
		eb.connect(
			'drag-drop', self.on_drop,
			extra_arg,	# more extra args can go here
		)

		xsocket = self.create_blender_xembed_socket()
		eb.add( xsocket )

		win.show_all()				# window and all widgets shown first
		self.do_xembed( xsocket, 'Blender' )	# this must come last


	def on_click(self, button):
		print('you clicked')

	def on_drop(self, widget, gcontext, x, y, time, extra_arg):
		print( 'this is the widget you dropped on', widget )
		print( 'this is the widget you dragged from', DND.source_widget)
		print( 'mouse:', x,y )
		print( 'extra argument from destination-side', extra_arg )
		print( 'first extra argument from source-side', DND.source_object )
		print( 'all extra arguments from source-side', DND.source_args )


	def mainloop(self):
		self.active = True
		while self.active:
			self.update_blender_and_gtk()



## TODO deprecate wnck-helper hack ##
wnck_helper = os.path.join(SCRIPT_DIR, 'wnck-helper.py')
assert os.path.isfile( wnck_helper )
os.system( wnck_helper )

app = MyApp()
app.mainloop()

