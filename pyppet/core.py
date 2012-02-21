# _*_ coding: utf-8 _*_
# by Brett Hart
# http://pyppet.blogspot.com
# License: BSD

import bpy, mathutils
import os, ctypes, time, threading
import gtk3 as gtk
import icons
import Blender

MODIFIER_TYPES = ('SUBSURF', 'MULTIRES', 'ARRAY', 'HOOK', 'LATTICE', 'MIRROR', 'REMESH', 'SOLIDIFY', 'UV_PROJECT', 'VERTEX_WEIGHT_EDIT', 'VERTEX_WEIGHT_MIX', 'VERTEX_WEIGHT_PROXIMITY', 'BEVEL', 'BOOLEAN', 'BUILD', 'DECIMATE', 'EDGE_SPLIT', 'MASK', 'SCREW', 'ARMATURE', 'CAST', 'CURVE', 'DISPLACE', 'MESH_DEFORM', 'SHRINKWRAP', 'SIMPLE_DEFORM', 'SMOOTH', 'WARP', 'WAVE', 'CLOTH', 'COLLISION', 'DYNAMIC_PAINT', 'EXPLODE', 'FLUID_SIMULATION', 'OCEAN', 'PARTICLE_INSTANCE', 'PARTICLE_SYSTEM', 'SMOKE', 'SOFT_BODY', 'SURFACE')

CONSTRAINT_TYPES = ('COPY_LOCATION', 'COPY_ROTATION', 'COPY_SCALE', 'COPY_TRANSFORMS', 'DAMPED_TRACK', 'LOCKED_TRACK', 'TRACK_TO', 'LIMIT_DISTANCE', 'LIMIT_LOCATION', 'LIMIT_ROTATION', 'LIMIT_SCALE', 'MAINTAIN_VOLUME', 'TRANSFORM', 'CLAMP_TO', 'IK', 'SPLINE_IK', 'STRETCH_TO', 'ACTION', 'CHILD_OF', 'FLOOR', 'FOLLOW_PATH', 'PIVOT', 'RIGID_BODY_JOINT', 'SCRIPT', 'SHRINKWRAP', 'CAMERA_SOLVER', 'OBJECT_SOLVER', 'FOLLOW_TRACK')

def get_hsv_color_as_rgb( hsv ):
	h = ctypes.pointer( ctypes.c_double() )
	s = ctypes.pointer( ctypes.c_double() )
	v = ctypes.pointer( ctypes.c_double() )
	hsv.get_color( h,s,v )
	return gtk.hsv2rgb( h.contents.value,s.contents.value,v.contents.value )


def sort_objects_by_type( objects, types=['MESH','ARMATURE','CAMERA','LAMP','EMPTY','CURVE'] ):
	r = {}
	for type in types: r[type]=[]
	for ob in objects:
		if ob.type in r: r[ob.type].append( ob )
	return r

class BlenderContextCopy(object):
	'''
	bpy.context becomes none when blender iterates its mainloop,
	each iteration it is possible to copy the context from bpy.context,
	and then use it outside of blenders mainloop iteration.
	( this is not safe, ie. creating some types of new data make the state invalid )
	'''
	def __init__(self, context):
		copy = context.copy()		# returns dict
		for name in copy: setattr( self, name, copy[name] )
		self.blender_has_cursor = False	# extra

class BlenderHack( object ):
	'''
	gtk.gtk_main_iteration() is safe to use outside of blender's mainloop,
	except that gtk callbacks might call some operators or change add/remove data,
	this invalidates the blender context and can cause a SEGFAULT.
	The only known safe way to mix GTK and blender is to call gtk.gtk_main_iteration()
	inside blender's mainloop.  This is done by attaching a callback to the VIEW_3D,
	Window region.  This is a hack because if the user hides the VIEW_3D then GTK
	will fail to update.

	TODO Workarounds:
		. from the outer python mainloop check to see if GTK updated from inside
		  blender, if not then attach new redraw callback to any visible view.

	TOO MANY HACKS:
		. request Ideasman and Ton for proper support for this.
	'''
	blender_window_ready = False
	_blender_min_width = 640
	_blender_min_height = 480
	_gtk_updated = False

	# bpy.context workaround - create a copy of bpy.context for use outside of blenders mainloop #
	def sync_context(self, region):
		self._gtk_updated = True
		self.context = BlenderContextCopy( bpy.context )
		self.lock.acquire()
		while gtk.gtk_events_pending():	# doing it here makes callbacks safe
			gtk.gtk_main_iteration()
		self.lock.release()

	def setup_blender_hack(self, context):
		if not hasattr(self,'lock') or not self.lock: self.lock = threading._allocate_lock()

		self.default_blender_screen = context.screen.name

		self.evil_C = Blender.Context( context )
		self.context = BlenderContextCopy( context )
		for area in context.screen.areas:
			if area.type == 'VIEW_3D':
				for reg in area.regions:
					if reg.type == 'WINDOW':
						## only POST_PIXEL is thread-safe and drag'n'drop safe
						## (maybe not!?) ##
						self._handle = reg.callback_add( self.sync_context, (reg,), 'PRE_VIEW' )
						return True
		return False

	_image_editor_handle = None

	def update_blender_and_gtk( self ):
		self._gtk_updated = False

		## force redraw in VIEW_3D ##
		screen = bpy.data.screens[ self.default_blender_screen ]
		for area in screen.areas:
			if area.type == 'VIEW_3D':
				for reg in area.regions:
					if reg.type == 'WINDOW':
						reg.tag_redraw()
						break

		## force redraw in secondary VIEW_3D and UV Editor ##
		for area in self.context.window.screen.areas:
			if area.type == 'VIEW_3D':
				for reg in area.regions:
					if reg.type == 'WINDOW':
						reg.tag_redraw()
						break
			elif area.type == 'IMAGE_EDITOR' and self.progressive_baking:
				for reg in area.regions:
					if reg.type == 'WINDOW':
						if not self._image_editor_handle:
							print('---------setting up image editor callback---------')
							self._image_editor_handle = reg.callback_add( 
								self.bake_hack, (reg,), 
								'POST_VIEW' 	# PRE_VIEW is invalid here
							)
						reg.tag_redraw()
						break

		Blender.iterate( self.evil_C)

		if not self._gtk_updated:	# ensures that gtk updates, so that we never get a dead UI
			print('WARN: 3D view is not shown - this is dangerous')
			self.lock.acquire()
			while gtk.gtk_events_pending():
				gtk.gtk_main_iteration()
			self.lock.release()

	################ BAKE HACK ################
	progressive_baking = False
	server = None
	def bake_hack( self, reg ):
		self.context = BlenderContextCopy( bpy.context )
		self.server.update( self.context )	# update http server



	BAKE_MODES = 'AO NORMALS SHADOW DISPLACEMENT TEXTURE SPEC_INTENSITY SPEC_COLOR'.split()
	BAKE_BYTES = 0
	## can only be called from inside the ImageEditor redraw callback ##
	def bake_image( self, ob, type='AO', width=64, height=None ):
		assert type in self.BAKE_MODES
		if height is None: height=width

		name = ob.name
		path = '/tmp/%s.%s' %(name,type)
		restore_active = self.context.active_object
		restore = []
		for o in self.context.selected_objects:
			o.select = False
			restore.append( o )
		ob.select = True
		self.context.scene.objects.active = ob

		bpy.ops.object.mode_set( mode='EDIT' )
		bpy.ops.mesh.select_all()
		bpy.ops.mesh.select_all()
		bpy.ops.image.new( name='baked', width=int(width), height=int(height) )
		bpy.ops.object.mode_set( mode='OBJECT' )	# must be in object mode for multires baking

		self.context.scene.render.bake_type = type
		self.context.scene.render.bake_margin = 5
		self.context.scene.render.use_bake_normalize = True
		self.context.scene.render.use_bake_selected_to_active = False	# required
		self.context.scene.render.use_bake_lores_mesh = False		# should be True
		self.context.scene.render.use_bake_multires = False
		if type=='DISPLACEMENT':	# can also apply to NORMALS
			for mod in ob.modifiers:
				if mod.type == 'MULTIRES':
					self.context.scene.render.use_bake_multires = True

		time.sleep(0.25)				# SEGFAULT without this sleep
		#self.context.scene.update()		# no help!? with SEGFAULT
		bpy.ops.object.bake_image()

		#img = bpy.data.images[-1]
		#img.file_format = 'jpg'
		#img.filepath_raw = '/tmp/%s.jpg' %ob.name
		#img.save()
		bpy.ops.image.save_as(
			filepath = path+'.png',
			check_existing=False,
		)

		for ob in restore: ob.select=True
		self.context.scene.objects.active = restore_active

		## 128 color PNG can beat JPG by half ##
		if type == 'DISPLACEMENT':
			os.system( 'convert %s.png -quality 75 -gamma 0.36 %s.jpg' %(path,path) )
			os.system( 'convert %s.png -colors 128 -gamma 0.36 %s.png' %(path,path) )
		else:
			os.system( 'convert %s.png -quality 75 %s.jpg' %(path,path) )
			os.system( 'convert %s.png -colors 128 %s.png' %(path,path) )

		## blender saves png's with high compressision level
		## for simple textures, the PNG may infact be smaller than the jpeg
		## check which one is smaller, and send that one, 
		## Three.js ignores the file extension and loads the data even if a png is called a jpg.
		pngsize = os.stat( path+'.png' ).st_size
		jpgsize = os.stat( path+'.jpg' ).st_size
		if pngsize < jpgsize:
			print('sending png data', pngsize)
			self.BAKE_BYTES += pngsize
			return open( path+'.png', 'rb' ).read()
		else:
			print('sending jpg data', jpgsize)
			self.BAKE_BYTES += jpgsize
			return open( path+'.jpg', 'rb' ).read()



class BlenderHackWindows( BlenderHack ): pass	#TODO
class BlenderHackOSX( BlenderHack ): pass		# TODO

class BlenderHackLinux( BlenderHack ):
	# ( this is brutal, ideally blender API supports embeding from python )
	def create_blender_xembed_socket(self):
		self._blender_xsocket = sock = gtk.Socket()
		sock.connect('plug-added', self.on_plug_blender)
		sock.connect('size-allocate',self.on_resize_blender)
		return sock

	def do_xembed(self, xsocket, window_name='Blender'):
		while gtk.gtk_events_pending(): gtk.gtk_main_iteration()
		xid = self.get_window_xid( window_name )
		xsocket.add_id( xid )

	def on_plug_debug(self, xsocket):
		print('----------on plug debug', xsocket)
		gdkwin = xsocket.get_plug_window()
		width = gdkwin.get_width()
		height = gdkwin.get_height()
		gdkwin.show()
		print('gdkwin', width,height)

	def on_plug_blender(self, args):
		self.blender_window_ready = True
		self._blender_xsocket.set_size_request(
			self._blender_min_width, 
			self._blender_min_height
		)
		gdkwin = self._blender_xsocket.get_plug_window()
		gdkwin.set_title( 'EMBED' )
		Blender.window_expand()
		self.after_on_plug_blender()

	def after_on_plug_blender(self): pass		# overload me

	def on_resize_blender(self,sock,rect):
		rect = gtk.cairo_rectangle_int()
		sock.get_allocation( rect )
		if self.blender_window_ready and self._gtk_updated:
			print('Xsocket Resize', rect.width, rect.height)
			self.blender_width = rect.width
			self.blender_height = rect.height
			Blender.window_resize( self.blender_width, self.blender_height )


	def get_window_xid( self, name ):
		import os
		p =os.popen('xwininfo -int -name "%s" ' %name)
		data = p.read().strip()
		p.close()
		if data.startswith('xwininfo: error:'): return None
		elif data:
			lines = data.splitlines()
			return int( lines[0].split()[3] )



	def do_wnck_hack(self, name='Blender'):
		## TODO deprecate wnck-helper hack ##
		SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
		wnck_helper = os.path.join(SCRIPT_DIR, 'wnck-helper.py')
		assert os.path.isfile( wnck_helper )
		os.system( '%s "%s"' %(wnck_helper,name) )


#########################################################

class DriverManagerSingleton(object):
	def __init__(self):
		self.drivers = []
	def update(self):
		for driver in self.drivers: driver.update()
	def append(self,driver):
		self.drivers.append( driver )

DriverManager = DriverManagerSingleton()

class DeviceOutput( object ):
	'''
	a single device output, ie. axis1 of gamepad1
	wraps multiple drivers under one DeviceOutput object

	'''
	def __init__(self,name, source=None, index=None, attribute_name=None, type=float):
		self.name = name
		self.drivers = {}		# (mode,target,target_path,target_index) : Driver
		self.type = type
		self.source	= source					# can be any object or list
		self.index = index						# index in list, assumes source is a list
		self.attribute_name = attribute_name	# name of attribute, assumes source is an object


	def bind(self, tag, target=None, path=None, index=None, mode='=', min=.0, max=1.0):
		key = (tag, target, path, index)
		if key not in self.drivers:
			self.drivers[ key ] = Driver(
				name = self.name,
				target = target,
				target_path = path,
				target_index = index,
				source = self.source,
				source_index = self.index,
				mode = mode,
				min = min,
				max = max,
			)
		driver = self.drivers[ key ]
		DriverManager.append( driver )
		return driver


class Driver(object):
	INSTANCES = []
	MODES = ('+', icons.SUBTRACT, '=', icons.MULTIPLY)
	@classmethod
	def get_drivers(self,oname, aname):
		r = []
		for d in self.INSTANCES:
			if d.target==oname and d.target_path.split('.')[0] == aname:
				r.append( d )
		return r
		
	def __init__(self, name='', target=None, target_path=None, target_index=None, source=None, source_index=None, source_attribute_name=None, mode='+', min=.0, max=420):
		self.name = name
		self.target = target		# if string assume blender object by name
		self.target_path = target_path
		self.target_index = target_index
		self.source = source
		self.source_index = source_index
		self.source_attribute_name = source_attribute_name
		self.active = True
		self.gain = 0.0
		self.mode = mode
		self.min = min
		self.max = max
		self.delete = False
		Driver.INSTANCES.append(self)	# TODO use DriverManager


	def drop_active_driver(self, button, context, x, y, time, frame):
		frame.remove( button )
		frame.add( gtk.Label(icons.DRIVER) )
		frame.show_all()

	def get_widget(self, title=None, extra=None, expander=True):
		if title is None: title = self.name
		if expander:
			ex = gtk.Expander( title ); ex.set_expanded(True)
			ex.set_border_width(4)
		else:
			ex = gtk.Frame()

		root = gtk.HBox(); ex.add( root )

		frame = gtk.Frame(); root.pack_start(frame, expand=False)
		b = gtk.CheckButton()
		#b.set_tooltip_text('toggle driver')	# BUG missing?
		b.set_active(self.active)
		b.connect('toggled', lambda b,s: setattr(s,'active',b.get_active()), self)
		frame.add( b )

		DND.make_destination( b )
		b.connect('drag-drop', self.drop_active_driver, frame)

		adjust = gtk.Adjustment( value=self.gain, lower=self.min, upper=self.max )
		adjust.connect('value-changed', lambda adj,s: setattr(s,'gain',adj.get_value()), self)
		scale = gtk.HScale( adjust )
		scale.set_value_pos(gtk.POS_RIGHT)
		scale.set_digits(2)
		root.pack_start( scale )

		scale.add_events(gtk.GDK_BUTTON_PRESS_MASK)
		scale.connect('button-press-event', self.on_click, ex)

		combo = gtk.ComboBoxText()
		root.pack_start( combo, expand=False )
		for i,mode in enumerate( Driver.MODES ):
			combo.append('id', mode)
			if mode == self.mode: gtk.combo_box_set_active( combo, i )
		combo.set_tooltip_text( 'driver mode' )
		combo.connect('changed',lambda c,s: setattr(s,'mode',c.get_active_text()), self )

		return ex

	def on_click(self,scale,event, container):
		event = gtk.GdkEventButton( pointer=ctypes.c_void_p(event), cast=True )
		#print(event)
		#print(event.x, event.y)
		#event.C_type	# TODO fixme event.type	# gtk.gdk._2BUTTON_PRESS
		if event.button == 3:	# right-click deletes
			container.hide()
			self.active = False
			self.delete = True

			#b = gtk.Button('x')
			#b.set_relief( gtk.RELIEF_NONE )
			#b.set_tooltip_text( 'delete driver' )
			#b.connect('clicked', self.cb_delete, ex)
			#root.pack_start( b, expand=False )


	#def cb_delete(self, b, container):
	#	container.hide()
	#	self.active = False
	#	self.delete = True
	#	Driver.INSTANCES.remove(self)


	def update(self):
		if not self.active: return

		if type(self.target) is str: ob = bpy.data.objects[ self.target ]
		else: ob = self.target

		if '.' in self.target_path:
			sname,aname = self.target_path.split('.')
			sub = getattr(ob,sname)
		else:
			sub = ob
			aname = self.target_path

		if self.source_index is not None:
			a = (self.source[ self.source_index ] * self.gain)

			if self.target_index is not None:
				vec = getattr(sub,aname)
				if self.mode == '+':
					vec[ self.target_index ] += a
				elif self.mode == '=':
					vec[ self.target_index ] = a
				elif self.mode == icons.SUBTRACT:
					vec[ self.target_index ] -= a
				elif self.mode == icons.MULTIPLY:
					vec[ self.target_index ] *= a

			else:
				if self.mode == '+':
					value = getattr(sub,aname) + a
				elif self.mode == '=':
					value = a
				elif self.mode == icons.SUBTRACT:
					value = getattr(sub,aname) - a
				elif self.mode == icons.MULTIPLY:
					value = getattr(sub,aname) * a

				setattr(sub, aname, value)
		else:
			assert 0

##############################################################################

class ToolWindow(object):
	def __init__(self, title='', x=0, y=0, width=100, height=40, child=None):
		self.object = None
		self.window = win = gtk.Window()
		win.set_title( title )
		win.move( x, y )
		win.set_keep_above(True)
		win.set_skip_pager_hint(True)
		win.set_skip_taskbar_hint(True)
		win.set_size_request( width, height )
		if child:
			self.root = child
			win.add( child )



################## simple drag'n'drop API ################
class SimpleDND(object):
	target = gtk.target_entry_new( 'test',1,gtk.TARGET_SAME_APP )		# GTK's confusing API

	def __init__(self):
		self.dragging = False
		self.source_widget = None	# the destination may want to use the source widget directly
		self.source_object = None	# the destination will likely use this source data
		self.source_args = None

		## make_source_with_callback - DEPRECATE? ##
		self._callback = None		# callback the destination should call
		self._args = None

	def make_source(self, widget, *args):
		## a should be an gtk.EventBox or have an eventbox as its parent, how strict is this rule? ##
		widget.drag_source_set(
			gtk.GDK_BUTTON1_MASK, 
			self.target, 1, 
			gtk.GDK_ACTION_COPY
		)
		widget.connect('drag-begin', self.drag_begin, args)
		widget.connect('drag-end', self.drag_end)

	def drag_begin(self, source, c, args):
		print('DRAG BEGIN')
		self.dragging = time.time()		# if dragging went to long may need to force off
		self.source_widget = source
		if len(args) >= 1: self.source_object = args[0]
		else: self.source_object = None
		self.source_args = args
		self._callback = None
		self._args = None


	def drag_end(self, w,c):
		print('DRAG END')
		self.dragging = False
		self.source_widget = None
		self.source_object = None
		self.source_args = None
		self._callback = None
		self._args = None

	def make_destination(self, a):
		a.drag_dest_set(
			gtk.DEST_DEFAULT_ALL, 
			self.target, 1, 
			gtk.GDK_ACTION_COPY
		)

	###################### DEPRECATE? ##################
	def make_source_with_callback(self, a, callback, *exargs):
		a.drag_source_set(
			gtk.GDK_BUTTON1_MASK, 
			self.target, 1, 
			gtk.GDK_ACTION_COPY
		)
		a.connect('drag-begin', self.drag_begin_with_callback, callback, exargs)
		a.connect('drag-end', self.drag_end)

	def drag_begin_with_callback(self, source, c, callback, args):
		print('DRAG BEGIN')
		self.dragging = time.time()		# if dragging went to long may need to force off
		self.source_widget = source
		self.source_object = None
		self.source_args = None
		self._callback = callback
		self._args = args

	def callback(self, *args):
		print('DND doing callback')
		self.dragging = False
		if self._args: a = args + self._args
		else: a = args
		return self._callback( *a )

DND = SimpleDND()	# singleton

class ExternalDND( SimpleDND ):	# NOT WORKING YET!! #
	#target = gtk.target_entry_new( 'text/plain',2,gtk.TARGET_OTHER_APP )
	target = gtk.target_entry_new( 'file://',2,gtk.TARGET_OTHER_APP )
	#('text/plain', gtk.TARGET_OTHER_APP, 0),	# gnome
	#('text/uri-list', gtk.TARGET_OTHER_APP, 1),	# XFCE
	#('TEXT', 0, 2),
	#('STRING', 0, 3),
XDND = ExternalDND()


############## Simple Driveable Slider ##############
class Slider(object):
	def __init__(self, object=None, name=None, title=None, target_index=None, value=0, min=0, max=1, border_width=2, driveable=True, no_show_all=False, tooltip=None, integer=False):
		self.min = min
		self.max = max


		if title is not None: self.title = title
		else: self.title = name.replace('_',' ')

		if len(self.title) < 20:
			self.widget = gtk.Frame()
			self.modal = row = gtk.HBox()
			row.pack_start( gtk.Label(self.title), expand=False )
		else:
			self.widget = gtk.Frame( self.title )
			self.modal = row = gtk.HBox()
		self.widget.add( row )

		if tooltip: self.widget.set_tooltip_text( tooltip )

		if object is not None:
			if target_index is not None:
				value = getattr( object, name )[ target_index ]
			else:
				value = getattr( object, name )

		self.adjustment = adjust = gtk.Adjustment( value=value, lower=min, upper=max )
		scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
		row.pack_start( scale )

		if integer: scale.set_digits(0)
		else: scale.set_digits(2)

		if object is not None:
			if target_index is not None:
				func = lambda a,o,n,idx: getattr(o, n).__setitem__(idx, a.get_value())
				adjust.connect(
					'value-changed', func,
					object, name, target_index
				)
			else:
				func = lambda a,o,n: setattr(o, n, a.get_value())
				adjust.connect(
					'value-changed', func,
					object, name
				)

		self.widget.set_border_width( border_width )

		if driveable:
			DND.make_destination( self.widget )
			self.widget.connect(
				'drag-drop', self.drop_driver,
				object, name, target_index,
			)

		self.widget.show_all()
		if no_show_all: self.widget.set_no_show_all(True)


	def drop_driver(self, wid, context, x, y, time, target, path, target_index):
		output = DND.source_object
		assert isinstance( output, DeviceOutput )

		driver = output.bind( 
			'YYY', 
			target=target, 
			path=path, 
			index=target_index, 
			min=self.min, 
			max=self.max 
		)
		self.widget.set_tooltip_text( '%s (%s%s)' %(self.title, icons.DRIVER, driver.name) )
		self.widget.remove( self.modal )
		self.modal = driver.get_widget( title='', expander=False )
		self.widget.add( self.modal )
		self.modal.show_all()


###########################################################

class ToggleButton(object):
	_type = 'toggle'
	def __init__(self, name=None, driveable=True, tooltip=None):
		self.name = name

		self.widget = gtk.Frame()
		if tooltip: self.widget.set_tooltip_text( tooltip )
		self.box = gtk.HBox(); self.widget.add( self.box )

		if self._type == 'toggle':
			self.button = gtk.ToggleButton( self.name )
		elif self._type == 'check':
			self.button = gtk.CheckButton( self.name )

		self.box.pack_start( self.button, expand=False )

		self.button.connect('button-press-event', self.on_click )

		self.driver = False
		if driveable:
			DND.make_destination( self.widget )
			self.widget.connect( 'drag-drop', self.drop_driver )

	def on_click(self, button, event):
		event = gtk.GdkEventButton( pointer=ctypes.c_void_p(event), cast=True )
		if event.button==3 and self.driver:		# right-click
			widget = self.driver.get_widget( title='', expander=False )
			win = ToolWindow( title=self.driver.name, x=int(event.x_root), y=int(event.y_root), width=240, child=widget )
			win.window.show_all()

	def cb( self, button ):
		setattr( self.target, self.target_path, self.cast(button.get_active()) )

	def cb_by_index( self, button ):
		vec = getattr( self.target, self.target_path )
		vec[ self.target_index ] = self.cast( button.get_active() )

	def connect( self, object, path=None, index=None, cast=bool ):
		self.target = object
		self.target_path = path
		self.target_index = index
		self.cast = cast
		if index is not None:
			value = getattr(self.target,self.target_path)[index]
			#print('target index value', value)
			self.button.set_active( bool(value) )
			self.button.connect('toggled', self.cb_by_index)
		else:
			value = getattr(self.target,self.target_path)
			self.button.set_active( bool(value) )
			self.button.connect('toggled', self.cb)


	def drop_driver(self, wid, context, x, y, time):
		output = DND.source_object
		self.driver = output.bind( 'UUU', target=self.target, path=self.target_path, index=self.target_index, min=-2, max=2, mode='=' )
		self.driver.gain = 1.0
		self.button.set_label( '%s%s' %(icons.DRIVER,self.name.strip()))

class CheckButton( ToggleButton ): _type = 'check'


class VStacker( object ):
	'''
	Forget about GtkTreeView!
	VStack: makes drag and drop reordering simple.
	'''
	def __init__(self, callback=None, padding=3):
		assert padding >= 2	# reording logic fails without a few pixels of padding
		self.padding = padding
		self.callback = None

		self.widget = gtk.EventBox()
		self.root = root = gtk.VBox()
		self.widget.add( root )
		DND.make_destination(self.widget)
		self.widget.connect('drag-drop', self.on_drop)
		self.children = []

		#self.footer = gtk.HBox()
		#self.root.pack_end( self.footer, expand=False )

	def append( self, widget ):
		self.children.append( widget )
		self.root.pack_start( widget, expand=False, padding=self.padding )
		DND.make_source( widget )

	def set_callback( self, callback, *args ):
		self.callback = callback
		self.callback_args = args

	def on_drop(self, widget, context, x,y, time):
		source = DND.source_widget
		assert source in self.children
		children = []

		for i,child in enumerate(self.children):
			if child is source:
				continue

			rect = gtk.cairo_rectangle_int()
			child.get_allocation( rect )

			if i == 0 and y < rect.y:	# insert at top
				children.append( source )
				children.append( child )

			elif y > rect.y and y < rect.y+rect.height+(self.padding*2):
				if y > rect.y+rect.height:
					children.append( child )
					children.append( source )
				else:
					children.append( source )
					children.append( child )

			else:
				children.append( child )

		if source not in children: return		# dropped on self, nothing to do

		oldindex = self.children.index( source )
		newindex = children.index( source )
		self.root.reorder_child( source, newindex )
		self.children = children
		if self.callback:
			self.callback( oldindex, newindex, *self.callback_args )

class Expander(object):
	'''
	Like gtk.Expander but can have extra buttons on header
	'''
	def __init__(self, name='', border_width=4, full_header_toggle=True, insert=None):
		self.name = name
		self._full_header_toggle = full_header_toggle

		self.widget = gtk.EventBox()
		frame = gtk.Frame()
		self.widget.add( frame )
		self.root = gtk.VBox()
		frame.add( self.root )
		self.root.set_border_width( border_width )

		self.header = gtk.HBox()
		self.root.pack_start( self.header, expand=False )

		if insert:
			self.header.pack_start( insert, expand=False )

		if full_header_toggle:
			self.toggle_button = b = gtk.ToggleButton( '%s  %s' %(icons.EXPANDER_UP,self.name) )
			self.header.pack_start( b, expand=True )
			b.set_alignment( 0.0, 0.5 )	# align text to the left (default is 0.5, 0.5)
		else:
			self.toggle_button = b = gtk.ToggleButton( icons.EXPANDER_UP )
			self.header.pack_start( b, expand=False )
			if name: self.header.pack_start( gtk.Label(self.name), expand=False )
			self.header.pack_start( gtk.Label() )

		b.set_relief( gtk.RELIEF_NONE )
		b.connect('toggled', self.toggle)

		self.children = []

	def toggle(self,b):
		if b.get_active():
			if self._full_header_toggle: b.set_label( '%s  %s' %(icons.EXPANDER_DOWN,self.name) )
			else: b.set_label( icons.EXPANDER_DOWN )
			for child in self.children: child.show()
		else:
			if self._full_header_toggle: b.set_label( '%s  %s' %(icons.EXPANDER_UP,self.name) )
			else: b.set_label( icons.EXPANDER_UP )
			for child in self.children: child.hide()

	def append(self, child):
		child.show_all()
		child.set_no_show_all(True)
		child.hide()
		self.children.append( child )
		self.root.pack_start( child, expand=False )
	def add( self, child): self.append( child )


class RNAWidget( object ):
	skip = 'rna_type show_in_editmode show_expanded show_on_cage show_viewport show_render'.split()

	def __init__(self, ob):
		assert hasattr( ob, 'bl_rna' )
		rna = ob.bl_rna

		props = {}
		for name in rna.properties.keys():
			if name not in self.skip:
				prop = rna.properties[ name ]
				if not prop.is_readonly and not prop.is_hidden:
					if prop.type not in props: props[ prop.type ] = {}
					props[ prop.type ][ name ] = prop

		print( props.keys() )

		self.widget = note = gtk.Notebook()

		if 'INT' in props or 'FLOAT' in props or 'ENUM' in props or 'POINTER' in props:
			root = gtk.VBox()
			note.append_page( root, gtk.Label('settings') )

		N = 0
		for ptype in 'INT FLOAT'.split():
			if ptype not in props: continue
			for name in props[ ptype ]:
				prop = props[ ptype ][name]
				#prop.identifier is name
				if not prop.array_length:
					slider = Slider( 
						ob, 
						name = name,
						title = prop.name,
						value = getattr( ob, name ), 
						min = prop.soft_min, 
						max = prop.soft_max,
						tooltip = prop.description,
						integer = (ptype=='INT'),
						#driveable = (ptype=='FLOAT'),
					)
					root.pack_start( slider.widget, expand=False )
					N += 1

		ptype = 'ENUM'
		if ptype in props:
			for name in props[ ptype ]:
				prop = props[ ptype ][name]

				combo = gtk.ComboBoxText()
				root.pack_start( combo, expand=False )

				attr = getattr(ob,name)
				for i,type in enumerate( prop.enum_items.keys() ):
					combo.append('id', type)
					if type == attr: gtk.combo_box_set_active( combo, i )

				combo.set_tooltip_text( prop.description )
				combo.connect('changed', lambda c,o,n: setattr(o,n,c.get_active_text()), ob, name)
				N += 1

		ptype = 'POINTER'
		if ptype in props:
			if len(props[ptype]) + N >= 8:
				root = gtk.VBox()
				note.append_page( root, gtk.Label('objects') )

			for name in props[ ptype ]:
				prop = props[ ptype ][name]
				eb = gtk.EventBox(); eb.set_border_width(3)
				root.pack_start( eb, expand=False )
				frame = gtk.Frame( prop.name )
				eb.add( frame )
				DND.make_destination( eb )
				label = gtk.Label()
				eb.connect('drag-drop', self.on_drop, ob, name, label)
				eb.set_tooltip_text( prop.description )
				frame.add( label )


		ptype = 'BOOLEAN'
		if ptype in props:
			root = gtk.VBox()
			note.append_page( root, gtk.Label('options') )

			for name in props[ ptype ]:
				prop = props[ ptype ][name]
				b = CheckButton( name=prop.name, tooltip=prop.description )
				b.connect( ob, path=name )
				root.pack_start( b.widget, expand=False )


	def on_drop(self, widget, gcontext, x,y, time, ob, name, label):
		print( DND.source_object )
		if type(DND.source_object) is bpy.types.Object:
			setattr(ob,name, DND.source_object)
			if getattr(ob,name) == DND.source_object:
				label.set_text( DND.source_object.name )
			else:
				label.set_text( '<invalid object>' )


class RNASlider(object):		# TODO, make driveable
	def adjust_by_name( self, adj, ob, name): setattr(ob,name, adj.get_value())
	def adjust_by_index( self, adj, ob, index): ob[index] = adj.get_value()

	def __init__(self, ob, name, title=None, min=None, max=None):
		self.object = ob
		self.min = min
		self.max =max
		#print(ob.bl_rna.properties.keys() )
		self.rna = ob.bl_rna.properties[name]
		self.adjustments = {}
		attr = getattr( ob, name )
		if type(attr) is mathutils.Vector or (self.rna.type=='FLOAT' and self.rna.array_length==3):
			assert self.rna.array_length == 3
			self.widget = ex = gtk.Expander( title or self.rna.name )
			ex.set_expanded( True )
			root = gtk.VBox(); ex.add( root )
			root.set_border_width(8)
			root.pack_start( self.make_row(attr, index=0, label='x'), expand=False )
			root.pack_start( self.make_row(attr, index=1, label='y'), expand=False )
			root.pack_start( self.make_row(attr, index=2, label='z'), expand=False )
		elif self.rna.type in ('INT','FLOAT'):
			self.widget = self.make_row(ob,name, label=title or self.rna.name)
		else:
			print('unknown RNA type', self.rna.type)

	def make_row(self, ob, name=None, index=None, label=None):
		if name is not None: value = getattr(ob,name)
		elif index is not None: value = ob[index]
		else: assert 0

		row = gtk.HBox()
		if label: row.pack_start( gtk.Label(label), expand=False )
		elif name: row.pack_start( gtk.Label(name.split('ode_')[-1]), expand=False )
		elif index is not None:
			if index==0:
				row.pack_start( gtk.Label('x'), expand=False )
			elif index==1:
				row.pack_start( gtk.Label('y'), expand=False )
			elif index==2:
				row.pack_start( gtk.Label('z'), expand=False )

		b = gtk.SpinButton()
		self.adjustments[name] = adj = b.get_adjustment()

		scale = gtk.HScale( adj )
		#scale.set_value_pos(gtk.POS_RIGHT)
		row.pack_start( scale )
		row.pack_start( b, expand=False )

		if self.rna.type == 'FLOAT':
			scale.set_digits( self.rna.precision )
			step = 0.1
		else:
			scale.set_digits( 0 )
			step = 1

		if self.min is not None: min = self.min
		else: min = self.rna.soft_min
		if self.max is not None: max = self.max
		else: max = self.rna.soft_max
		#print(value,min,max,step)
		adj.configure( 
			value=value, 
			lower=min, 
			upper=max, 
			step_increment=step,
			page_increment=0.1,
			page_size=0.1
		)
		#print('CONFIG OK')
		if name is not None: adj.connect('value-changed', self.adjust_by_name, ob, name)
		else: adj.connect('value-changed', self.adjust_by_index, ob, index)
		#print('CONNECT OK')
		return row



class NotebookVectorWidget( object ):
	def __init__( self, ob, name, title=None, expanded=True ):
		drivers = Driver.get_drivers(ob.name, name)	# classmethod

		vec = getattr(ob,name)

		if title: ex = gtk.Expander(title)
		else: ex = gtk.Expander(name)
		ex.set_expanded( expanded )
		self.widget = ex

		note = gtk.Notebook(); ex.add( note )
		note.set_tab_pos( gtk.POS_RIGHT )

		if type(vec) is mathutils.Color:
			tags = 'rgb'
			nice = icons.RGB
		else:
			tags = 'xyz'
			nice = icons.XYZ

		for i,axis in enumerate( tags ):
			a = gtk.Label( nice[axis] )
			page = gtk.VBox(); page.set_border_width(3)
			note.append_page( page, a )

			DND.make_destination(a)
			a.connect(
				'drag-drop', self.cb_drop_driver,
				ob, name, i, page
			)

			for driver in drivers:
				if driver.target_index == i:
					page.pack_start( driver.get_widget(), expand=False )


	def cb_drop_driver(self, wid, context, x, y, time, target, path, index, page):
		print('on drop')
		output = DND.source_object
		#driver = output.bind( 'XXX', target=self.object, path=path, index=index )
		if path.startswith('ode_'):
			driver = output.bind( 'XXX', target=target, path=path, index=index, max=500 )
		else:
			driver = output.bind( 'XXX', target=target, path=path, index=index )
		widget = driver.get_widget()
		page.pack_start( widget, expand=False )
		widget.show_all()


#########################################################

class PopupWindow(object):
	def __init__(self, title='', width=100, height=40, child=None):
		self.object = None
		self.window = win = gtk.Window()
		win.set_title( title )
		win.set_position( gtk.WIN_POS_MOUSE )
		win.set_keep_above(True)
		win.set_skip_pager_hint(True)
		win.set_skip_taskbar_hint(True)
		#win.set_size_request( width, height )
		win.set_deletable(False)

		#win.set_decorated( False )

		#color = gtk.GdkRGBA(0.0,50000.5,0.3,0.1)
		#win.override_background_color( gtk.STATE_NORMAL, color )	# not allowed?
		#win.set_app_paintable(True)	# tell GTK we will paint the background
		#eb = gtk.EventBox(); win.add( eb )
		#eb.connect('draw', self.expose)	# looks like expose-event is deprecated?
		#screen = widget.get_screen()		# this was pygtk only?
		#colormap = screen.get_rgba_colormap()
		#win.set_colormap(colormap)

		#self.window.add_events( gtk.GDK_BUTTON_PRESS_MASK )
		#self.window.connect('button-press-event', self.on_press)
		if child:
			self.root = child
			win.add( child )

	def expose(self, widget, event):
		gdkwin = self.window.get_window()
		c = gdkwin.cairo_create()	# segfaults here
		c.set_source_rgba(0.5, 0.75, 0.5, 0.1)
		c.set_operator( gtk.cairo_operator['CAIRO_OPERATOR_SOURCE'] )
		c.paint_with_alpha( 0.5 )


	def on_press(self, widget, event):
		event = gtk.GdkEventButton( pointer=ctypes.c_void_p(event), cast=True )
		if event.button == 1:
			self.window.begin_move_drag( 
				event.button, 
				int(event.x_root), 	# c_double
				int(event.y_root), 
				event.time
			)

_detachable_target_ = gtk.target_entry_new( 'detachable',2,gtk.TARGET_OTHER_APP )	
def make_detachable( widget ):
	widget.drag_source_set(
		gtk.GDK_BUTTON1_MASK, 
		_detachable_target_, 1, 
		gtk.GDK_ACTION_COPY
	)
	#widget.connect('drag-begin', self.drag_begin, args)
	widget.connect('drag-end', _on_detach)
def _on_detach( widget, gcontext ):
	print(widget, gcontext)
	parent = widget.get_parent()
	#parent.remove( widget )		# getting confused with "remove" function in gtk wrapper?
	gtk.container_remove( parent, widget )
	w = ToolWindow( child=widget )
	w.window.show_all()

class DetachableExpander( object ):
	def __init__(self, name):
		self.name = name
		self.detached = False
		self.popup = False
		self.widget = gtk.Expander(name)
		self.widget.connect('activate', self.on_expand)
		###### problem, very hard to click on a button on an expander ####
		#self.widget.set_label_fill(True)
		#bx = gtk.HBox()
		#bx.pack_start( gtk.Label(name), expand=False )
		#bx.pack_start( gtk.Label() )
		#self.button = gtk.Button('.')
		#bx.pack_start( self.button, expand=False )
		#self.widget.set_label_widget( bx )

		self.widget.drag_source_set(
			gtk.GDK_BUTTON1_MASK, 
			_detachable_target_, 1, 
			gtk.GDK_ACTION_COPY
		)
		self.widget.connect('drag-end', self.on_detach)
		#self.widget.connect('drag-motion', self.on_drag)	# this is drag motion over me

	def on_expand(self,widget):
		if self.popup:
			if widget.get_expanded():
				self.popup.window.resize( 60, 20 )

	#def on_drag(self, widget, gcontext, x,y, time): print(x,y)


	def add(self,child):
		self.child = child
		self.widget.add( child )

	def remove(self,child):
		self.widget.remove( child )
		self.child = None

	def show_all(self): self.widget.show_all()

	def on_detach(self, widget, gcontext):
		if self.detached: return
		self.detached = True
		parent = widget.get_parent()
		#child = widget.get_children().nth_data(0)	# some bug here
		#gtk.container_remove( widget, child )
		gtk.container_remove( parent, widget )
		self.popup = PopupWindow( title=self.name, child=self.widget )
		self.widget.set_expanded(True)
		self.popup.window.show_all()






