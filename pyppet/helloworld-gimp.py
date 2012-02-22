# run: ~/Blender/blender --python helloworld-gimp.py
'''
notes:
	looks like there is a problem that if:
		. a new image is created and not saved, then,
		. gimp prompts "do you want to save", but,
		. the layers tool-window has already been closed, so,
		. then the next time you reopen gimp,
		. the layers tools-window is now closed, and
		. then we can not xembed it!

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
		self.do_wnck_hack('Blender')
		self.do_wnck_hack('Toolbox')

		assert self.setup_blender_hack( bpy.context )

		self.window = win = gtk.Window()
		win.connect('destroy', lambda w: setattr(self,'active',False) )
		win.set_title( 'GtkBlender SDK' )
		self.root = root = gtk.HPaned()
		win.add( root )

		bx = gtk.VBox(); root.add1( bx )

		frame = gtk.Frame()
		frame.set_border_width( 10 )
		bx.pack_start( frame, expand=False )
		button = gtk.Button('hello world')
		button.set_border_width( 10 )
		button.connect('clicked', self.on_click)
		frame.add( button )

		self.blender_container = eb = gtk.EventBox()
		bx.pack_start( self.blender_container )
		xsocket = self.create_blender_xembed_socket()
		eb.add( xsocket )

		self._gimp_page = gtk.HBox()
		root.add2( self._gimp_page )
		self._gimp_toolbox_xsocket = soc = gtk.Socket()
		soc.set_size_request( 170, 560 )
		self._gimp_image_xsocket = soc = gtk.Socket()
		soc.set_size_request( 320, 560 )
		self._gimp_layers_xsocket = soc = gtk.Socket()
		soc.set_size_request( 240, 560 )

		self._gimp_page.pack_start( self._gimp_toolbox_xsocket, expand=False )
		self._gimp_page.pack_start( self._gimp_image_xsocket, expand=True )
		self._gimp_page.pack_start( self._gimp_layers_xsocket, expand=False )


		win.show_all()				# window and all widgets shown first

		self.do_xembed( self._gimp_toolbox_xsocket, "Toolbox")
		self.do_xembed( self._gimp_image_xsocket, "GNU Image Manipulation Program")
		self.do_xembed( self._gimp_layers_xsocket, "Layers, Channels, Paths, Undo - Brushes, Patterns, Gradients")

		self.do_xembed( xsocket, 'Blender' )	# this must come last

	def on_map(self,widget):
		print('-----------on map----------')

	def on_click(self, button):
		print('you clicked')


	def mainloop(self):
		self.active = True
		while self.active:
			self.update_blender_and_gtk()




app = MyApp()
app.mainloop()

