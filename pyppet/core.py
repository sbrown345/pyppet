# _*_ coding: utf-8 _*_
# by Brett Hart
# http://pyppet.blogspot.com
# License: BSD

import bpy
import ctypes, time, threading
import gtk3 as gtk
import icons
import Blender

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

	_blender_min_width = 640
	_blender_min_height = 480
	blender_window_ready = False

	# bpy.context workaround - create a copy of bpy.context for use outside of blenders mainloop #
	def sync_context(self, region):
		self.context = BlenderContextCopy( bpy.context )
		self.lock.acquire()
		while gtk.gtk_events_pending():	# required to make callbacks safe
			gtk.gtk_main_iteration()
		self.lock.release()

	def setup_blender_hack(self, context):
		if not hasattr(self,'lock'): self.lock = threading._allocate_lock()
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

class BlenderHackWindows( BlenderHack ): pass	#TODO
class BlenderHackOSX( BlenderHack ): pass		# TODO

class BlenderHackLinux( BlenderHack ):
	def Xsocket_resize(self,sock,rect):
		rect = gtk.cairo_rectangle_int()
		sock.get_allocation( rect )
		if self.blender_window_ready:
			print('Xsocket Resize', rect.width, rect.height)
			self.blender_width = rect.width
			self.blender_height = rect.height
			Blender.window_resize( self.blender_width, self.blender_height )

	def create_xembed_socket(self):
		self.Xsocket = gtk.Socket()	# the XEMBED hack - TODO MSWindows solution?
		self.Xsocket.connect('plug-added', self.on_plug_Xsocket)
		self.Xsocket.connect('size-allocate',self.Xsocket_resize)
		return self.Xsocket

	def do_embed_blender(self):
		############## get XID and then Embed Blender ##########
		while gtk.gtk_events_pending(): gtk.gtk_main_iteration()
		print('ready to xembed...')
		xid = self.get_window_xid( 'Blender' )
		print('got blender XID', xid)
		self.Xsocket.add_id( xid )
		# ( this is brutal, ideally blender API supports embeding from python )


	def on_plug_Xsocket(self, args):
		print( 'on_plug_Xsocket')
		self.blender_window_ready = True
		self.Xsocket.set_size_request(
			self._blender_min_width, 
			self._blender_min_height
		)

	def get_window_xid( self, name ):
		import os
		p =os.popen('xwininfo -int -name %s' %name)
		data = p.read().strip()
		p.close()
		if data.startswith('xwininfo: error:'): return None
		elif data:
			lines = data.splitlines()
			return int( lines[0].split()[3] )






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


	def bind(self, tag, target=None, path=None, index=None, mode='+', min=.0, max=1.0):
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



################## simple drag'n'drop API ################
class SimpleDND(object):
	target = gtk.target_entry_new( 'test',1,gtk.TARGET_SAME_APP )

	def __init__(self):
		self.dragging = False
		self.source = None			# the destination may want to use the source widget directly
		self.object = None
		self._callback = None		# callback the destination should call
		self._args = None

	def make_source(self, a, ob):
		## a should be an gtk.EventBox or have an eventbox as its parent, how strict is this rule? ##
		a.drag_source_set(
			gtk.GDK_BUTTON1_MASK, 
			self.target, 1, 
			gtk.GDK_ACTION_COPY
		)
		a.connect('drag-begin', self.drag_begin, ob)
		a.connect('drag-end', self.drag_end)

	def drag_begin(self, source, c, ob):
		print('DRAG BEGIN')
		self.dragging = time.time()		# if dragging went to long may need to force off
		self.source = source
		self._callback = None
		self._args = None
		self.object = ob


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
		self.source = source
		self._callback = callback
		self._args = args
		self.object = None

	def drag_end(self, w,c):
		print('DRAG END')
		self.dragging = False
		self.source = None
		self._callback = None
		self._args = None
		self.object = None

	def make_destination(self, a):
		a.drag_dest_set(
			gtk.DEST_DEFAULT_ALL, 
			self.target, 1, 
			gtk.GDK_ACTION_COPY
		)

	def callback(self, *args):
		print('DND doing callback')
		self.dragging = False
		if self._args: a = args + self._args
		else: a = args
		return self._callback( *a )

DND = SimpleDND()	# singleton

class ExternalDND( SimpleDND ):
	#target = gtk.target_entry_new( 'text/plain',2,gtk.TARGET_OTHER_APP )
	target = gtk.target_entry_new( 'file://',2,gtk.TARGET_OTHER_APP )
	#('text/plain', gtk.TARGET_OTHER_APP, 0),	# gnome
	#('text/uri-list', gtk.TARGET_OTHER_APP, 1),	# XFCE
	#('TEXT', 0, 2),
	#('STRING', 0, 3),
XDND = ExternalDND()


############## Simple Driveable Slider ##############
class SimpleSlider(object):
	def __init__(self, object=None, name=None, title=None, value=0, min=0, max=1, border_width=2, driveable=False, no_show_all=False, tooltip=None):
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

		if object is not None: value = getattr( object, name )
		self.adjustment = adjust = gtk.Adjustment( value=value, lower=min, upper=max )
		scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
		scale.set_digits(2)
		row.pack_start( scale )

		if object is not None:
			adjust.connect(
				'value-changed', lambda a,o,n: setattr(o, n, a.get_value()),
				object, name
			)

		self.widget.set_border_width( border_width )

		if driveable:
			#scale.override_color( gtk.STATE_NORMAL, DRIVER_COLOR )

			DND.make_destination( self.widget )
			self.widget.connect(
				'drag-drop', self.drop_driver,
				object, name
			)

		self.widget.show_all()
		if no_show_all: self.widget.set_no_show_all(True)


	def drop_driver(self, wid, context, x, y, time, target, path):
		print('on drop')
		output = DND.object
		if path.startswith('ode_'):
			driver = output.bind( 'YYY', target=target, path=path, max=500 )
		else:
			driver = output.bind( 'YYY', target=target, path=path, min=-2, max=2 )

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
		output = DND.object
		self.driver = output.bind( 'UUU', target=self.target, path=self.target_path, index=self.target_index, min=-2, max=2, mode='=' )
		self.driver.gain = 1.0
		self.button.set_label( '%s%s' %(icons.DRIVER,self.name.strip()))

class CheckButton( ToggleButton ): _type = 'check'

