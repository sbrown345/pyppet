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
		button = gtk.Button('hello world')
		button.set_border_width( 10 )
		button.connect('clicked', self.on_click)
		frame.add( button )

		self.blender_container = eb = gtk.EventBox()
		root.pack_start( self.blender_container )

		xsocket = self.create_xembed_socket()
		eb.add( xsocket )

		win.show_all()
		self.do_embed_blender()		# this must come last

	def on_click(self, button):
		print('you clicked')


	def mainloop(self):
		self.active = True
		C = Blender.Context( bpy.context )
		while self.active:
			Blender.iterate(C)
			## force redraw in VIEW_3D ##
			for area in self.context.window.screen.areas:
				if area.type == 'VIEW_3D':
					for reg in area.regions:
						if reg.type == 'WINDOW':
							reg.tag_redraw()
							break


## TODO deprecate wnck-helper hack ##
wnck_helper = os.path.join(SCRIPT_DIR, 'wnck-helper.py')
assert os.path.isfile( wnck_helper )
os.system( wnck_helper )

app = MyApp()
app.mainloop()

