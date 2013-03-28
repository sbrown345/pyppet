# _*_ coding: utf-8 _*_
# by Brett Hart
# http://pyppet.blogspot.com
# License: BSD

try: import bpy, mathutils
except: print('WARN: unable to import bpy')

import sys, os, time, ctypes, threading, urllib
if sys.version_info[0] >= 3:
	import urllib.request
	import urllib.parse

import cv
import highgui as gui
if hasattr(gui,'CreateCameraCapture'):
	USE_OPENCV = True
	DEFAULT_WEBCAM_CAPTURE = gui.CreateCameraCapture(0)
else:
	USE_OPENCV = False
	DEFAULT_WEBCAM_CAPTURE = None

#import libclutter_gtk as clutter
import gtk3 as gtk

if hasattr(gtk, 'target_entry_new'): GTK3 = True
else: GTK3 = False


import icons
import Blender

import subprocess
import math

## make sure we can import and load data from same directory ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.append( SCRIPT_DIR )

PYPPET_LITE = 'pyppet-lite' in sys.argv

#assert clutter.gtk_clutter_init( ctypes.pointer(ctypes.c_int(0)) )
gtk.init()	# comes after clutter init


def start_new_thread( func, *args ):
	return threading._start_new_thread( func, args )


MODIFIER_TYPES = ('SUBSURF', 'MULTIRES', 'ARRAY', 'HOOK', 'LATTICE', 'MIRROR', 'REMESH', 'SOLIDIFY', 'UV_PROJECT', 'VERTEX_WEIGHT_EDIT', 'VERTEX_WEIGHT_MIX', 'VERTEX_WEIGHT_PROXIMITY', 'BEVEL', 'BOOLEAN', 'BUILD', 'DECIMATE', 'EDGE_SPLIT', 'MASK', 'SCREW', 'ARMATURE', 'CAST', 'CURVE', 'DISPLACE', 'MESH_DEFORM', 'SHRINKWRAP', 'SIMPLE_DEFORM', 'SMOOTH', 'WARP', 'WAVE', 'CLOTH', 'COLLISION', 'DYNAMIC_PAINT', 'EXPLODE', 'FLUID_SIMULATION', 'OCEAN', 'PARTICLE_INSTANCE', 'PARTICLE_SYSTEM', 'SMOKE', 'SOFT_BODY', 'SURFACE')

MODIFIER_TYPES_MINI = ('SUBSURF', 'MULTIRES', 'ARRAY', 'HOOK', 'LATTICE', 'MIRROR', 'REMESH', 'SOLIDIFY', 'UV_PROJECT', 'BEVEL', 'BOOLEAN', 'BUILD', 'DECIMATE', 'EDGE_SPLIT', 'MASK', 'SCREW', 'ARMATURE', 'CAST', 'CURVE', 'DISPLACE', 'MESH_DEFORM', 'SHRINKWRAP', 'SIMPLE_DEFORM', 'SMOOTH', 'WARP', 'WAVE', 'COLLISION', 'DYNAMIC_PAINT', 'EXPLODE', 'SURFACE')


CONSTRAINT_TYPES = ('COPY_LOCATION', 'COPY_ROTATION', 'COPY_SCALE', 'COPY_TRANSFORMS', 'DAMPED_TRACK', 'LOCKED_TRACK', 'TRACK_TO', 'LIMIT_DISTANCE', 'LIMIT_LOCATION', 'LIMIT_ROTATION', 'LIMIT_SCALE', 'MAINTAIN_VOLUME', 'TRANSFORM', 'CLAMP_TO', 'IK', 'SPLINE_IK', 'STRETCH_TO', 'ACTION', 'CHILD_OF', 'FLOOR', 'FOLLOW_PATH', 'PIVOT', 'RIGID_BODY_JOINT', 'SCRIPT', 'SHRINKWRAP', 'CAMERA_SOLVER', 'OBJECT_SOLVER', 'FOLLOW_TRACK')


def set_selection(ob):
	for o in bpy.context.scene.objects:
		if o.name == ob.name: ob.select = True
		else: ob.select = False

def save_selection():
	r = {}
	for ob in bpy.context.scene.objects: r[ ob.name ] = ob.select
	return r

def restore_selection( state ):
	for name in state:
		bpy.context.scene.objects[ name ].select = state[name]



def clear_cloth_caches():
	for ob in bpy.data.objects:
		if ob.type=='MESH':
			for mod in ob.modifiers:
				if mod.type=='CLOTH':
					print('clearing cloth cache:', ob.name)
					mod.show_viewport = False
					mod.show_viewport = True


def create_cube():
	_obs_ = bpy.data.objects.keys()
	bpy.ops.mesh.primitive_cube_add()
	cube = None
	for name in bpy.data.objects.keys():
		if name not in _obs_:
			cube = bpy.data.objects[ name ]
			break
	assert cube
	return cube


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

def get_ancestors( ob ):
	result = []
	_get_ancestors( ob, result )
	return result

def _get_ancestors( child, result ):
	result.append( child )
	if child.parent: _get_ancestors( child.parent, result )



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
	_blender_window_ready = False
	_blender_min_width = 240
	_blender_min_height = 320


	def open_3dsmax(self, button=None): self._3dsmax.run()
	def setup_3dsmax(self, clipboard):
		# system clipboard is current workaround for talking to 3dsmax
		#import Server
		self._clipboard = clipboard



	# bpy.context workaround - create a copy of bpy.context for use outside of blenders mainloop #
	def sync_context(self, region):
		'''
		Even with a large timeout websockets fail to work here inside the blender redraw callback.
		Websockets need to be updated from mainloop or another thread.

		#if self.websocket_server and not self.__websocket_updated:  # this is slower or faster?
		#	self.__websocket_updated = True
		#	self.websocket_server.update( bpy.context, timeout=1.0 )
		'''

		self.context = BlenderContextCopy( bpy.context )  ## this state might not be fully thread safe?
		## TODO store region types, and order


		if self.__use_3dsmax and self._3dsmax and self._clipboard: self._3dsmax.update( self._clipboard )
		if self.__use_gtk and not self._gtk_updated:
			self.lock.acquire() ## this allows gtk to work with other threads that might update pixbuffers, like opencv.
			i = 0
			while gtk.gtk_events_pending() and i < 100:
				gtk.gtk_main_iteration()
				i += 1
			self._gtk_updated = True
			self.lock.release()
		self.__blender_redraw = True

	def setup_blender_hack(self, context, use_gtk=True, use_3dsmax=False, headless=False):
		self.__use_gtk = use_gtk
		self.__use_3dsmax = use_3dsmax
		self.__websocket_updated = False
		self.headless = headless

		self._clipboard = None
		if use_3dsmax:
			import Server # TODO move Remote3dsMax its own module.
			self._3dsmax = Server.Remote3dsMax( bpy )
		else:
			self._3dsmax = None

		self.__blender_redraw = False

		if not hasattr(self,'lock') or not self.lock: self.lock = threading._allocate_lock()

		self.default_blender_screen = context.screen.name
		self.evil_C = Blender.Context( context )
		self.context = BlenderContextCopy( context )

		self._sync_hack_handles = {}	# region : handle
		if not headless:
			for area in context.screen.areas:
				if area.type == 'IMAGE_EDITOR': continue	# always checks for in update_blender_and_gtk
				#if area.type == 'VIEW_3D':
				for reg in area.regions:
					if reg.type == 'WINDOW':
						## only POST_PIXEL is thread-safe and drag'n'drop safe
						## (maybe not!?) ##
						handle = reg.callback_add( self.sync_context, (reg,), 'POST_PIXEL' )
						self._sync_hack_handles[ reg ] = handle
		return self._sync_hack_handles

	_image_editor_handle = None

	def force_blender_redraw(self, view3d=True, imageview=True):
		'''
		if Blenders window is minimized then the callbacks in the redraw (threadsafe zone) will not be called.
		after Blender.iterate(C) is called return self.__blender_redraw so the app-level can know if those call backs happen.
		'''
		self.__blender_redraw = False
		self.__websocket_updated = False

		## force redraw in VIEW_3D ##
		screen = bpy.data.screens[ self.default_blender_screen ]
		if view3d:
			for area in screen.areas:
				if area.type == 'VIEW_3D':
					for reg in area.regions:
						if reg.type == 'WINDOW':
							reg.tag_redraw()
							break

		## force redraw in secondary VIEW_3D and UV Editor ##
		if imageview:
			for area in self.context.window.screen.areas:
				if area.type == 'VIEW_3D':  ## TODO clean this up
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
									'POST_VIEW'
								)
							reg.tag_redraw()
							break

	def update_blender( self, draw=True ):
		'''
		note: when Blender is in headless mode these things can cause it to segfault crash:
		  . reg.callback_add
		  . Blender.iterate
		'''
		if not self.headless:
			self.force_blender_redraw()
			Blender.iterate( self.evil_C, draw=not self.headless)
		return self.__blender_redraw

	def update_blender_and_gtk( self, drop_frame=False ):
		self._gtk_updated = False
		if not drop_frame: self.force_blender_redraw()
		# note even updating GTK first wont fix the freeze on DND over blenders window! #
		Blender.iterate( self.evil_C, draw=not drop_frame)
		# its ok not to force gtk to update (this happens when ODE physics is on)
		#assert self._gtk_updated
		return self.__blender_redraw



	################ BAKE HACK ################
	progressive_baking = True
	server = None
	_image_editor_handle = None
	def bake_hack( self, reg ):
		self.context = BlenderContextCopy( bpy.context )
		if self.server: # DEPRECATED
			self.server.update( bpy.context )	# update http server



	BAKE_MODES = 'AO NORMALS SHADOW DISPLACEMENT TEXTURE SPEC_INTENSITY SPEC_COLOR'.split()
	BAKE_BYTES = 0
	## can only be called from inside the ImageEditor redraw callback ##
	def bake_image( self, ob, type='AO', size=64, refresh=False, extra_objects=[] ):
		assert type in self.BAKE_MODES
		width = height = size
		name = ob.name
		path_dir = '/tmp/texture-cache'
		if not os.path.isdir( path_dir ): os.makedirs( path_dir )
		path = os.path.join(
			path_dir, 
			'%s.%s.%s' %(name,size,type),
		)

		if not refresh and os.path.isfile(path+'.png'):
			print('FAST CACHE RETURN')

		elif refresh or not os.path.isfile(path+'.png'):
			if not self._image_editor_handle:
				print('_'*80)
				print('ERROR: you must open a "UV/Image editor" to bake textures')
				print('_'*80)
				return bytes(1)

			print('---------- baking image ->', ob.name)

			bpy.ops.object.mode_set( mode='OBJECT' )

			restore_hide_select = ob.hide_select
			ob.hide_select = False
			restore_active = bpy.context.active_object
			restore = []
			for o in bpy.context.selected_objects:
				o.select = False
				restore.append( o )
			ob.select = True
			bpy.context.scene.objects.active = ob	# required

			if extra_objects:
				bpy.context.scene.render.use_bake_selected_to_active = True
				for o in extra_objects: o.select = True
				#self.context.scene.render.bake_distance = 0.01
			else:
				bpy.context.scene.render.use_bake_selected_to_active = False


			bpy.ops.object.mode_set( mode='EDIT' )

			bpy.ops.mesh.select_all( action='SELECT' )	# ensure all faces selected
			bpy.ops.image.new(
				name='_%s_(%s %sx%s)' %(ob.name,type,width,height), 
				width=int(width), height=int(height) 
			)
			bpy.ops.object.mode_set( mode='OBJECT' )	# must be in object mode for multires baking

			bpy.context.scene.render.bake_type = type
			bpy.context.scene.render.bake_margin = 4
			bpy.context.scene.render.use_bake_normalize = True
			#self.context.scene.render.use_bake_selected_to_active = False	# required
			bpy.context.scene.render.use_bake_lores_mesh = False		# should be True
			bpy.context.scene.render.use_bake_multires = False
			if type=='DISPLACEMENT':	# can also apply to NORMALS
				for mod in ob.modifiers:
					if mod.type == 'MULTIRES':
						bpy.context.scene.render.use_bake_multires = True

			time.sleep(0.25)				# SEGFAULT without this sleep
			bpy.context.scene.update()		# not required
			res = bpy.ops.object.bake_image()
			print('bpy.ops.object.bake_image', res)

			#img = bpy.data.images[-1]
			#img.file_format = 'jpg'
			#img.filepath_raw = '/tmp/%s.jpg' %ob.name
			#img.save()
			bpy.ops.image.save_as(
				filepath = path+'.png',
				check_existing=False,
			)

			for ob in restore: ob.select=True
			bpy.context.scene.objects.active = restore_active
			ob.hide_select = restore_hide_select

			## 128 color PNG can beat JPG by half ##
			if type == 'DISPLACEMENT':
				os.system( 'convert "%s.png" -quality 75 -gamma 0.36 "%s.jpg"' %(path,path) )
				os.system( 'convert "%s.png" -colors 128 -gamma 0.36 "%s.png"' %(path,path) )
			else:
				os.system( 'convert "%s.png" -quality 75 "%s.jpg"' %(path,path) )
				os.system( 'convert "%s.png" -colors 128 "%s.png"' %(path,path) )

		## blender saves png's with high compressision level
		## for simple textures, the PNG may infact be smaller than the jpeg
		## check which one is smaller, and send that one, 
		## Three.js ignores the file extension and loads the data even if a png is called a jpg.
		pngsize = os.stat( path+'.png' ).st_size
		jpgsize = os.stat( path+'.jpg' ).st_size
		if pngsize < jpgsize:
			print('sending png data - bytes:', pngsize)
			self.BAKE_BYTES += pngsize
			return open( path+'.png', 'rb' ).read()
		else:
			print('sending jpg data - bytes:', jpgsize)
			self.BAKE_BYTES += jpgsize
			return open( path+'.jpg', 'rb' ).read()





class BlenderHackWindows( BlenderHack ): pass	#TODO
class BlenderHackOSX( BlenderHack ): pass		# TODO

class BlenderHackLinux( BlenderHack ):
	'''
	this class allows you to use xembed to put blender inside a gtk widget,
	there are issues with drag and drop that make this unstable.
	'''

	def drop_on_view(self, wid, con, x, y, time): ## DEPRECATED - not using xembed for blender's windows anymore.
		print('DEPRECATED warning: drop_on_view')
		ob = self.context.active_object
		if type(DND.source_object) is bpy.types.Material:
			mat = DND.source_object
			print('[material dropped: %s]'%mat)
			index = 0
			for index in range( len(ob.data.materials) ):
				if ob.data.materials[ index ] == mat: break
			ob.active_material_index = index
			bpy.ops.object.material_slot_assign()
			## should be in edit mode, if not then what action? ##
		elif DND.source_object == 'WEBCAM':
			if '_webcam_' not in bpy.data.images:
				bpy.data.images.new( name='_webcam_', width=240, height=180 )
			slot = ob.data.materials[0].texture_slots[0]
			slot.texture.image = bpy.data.images['_webcam_']
		elif DND.source_object == 'KINECT':
			if '_kinect_' not in bpy.data.images:
				bpy.data.images.new( name='_kinect_', width=240, height=180 )
			slot = ob.data.materials[0].texture_slots[0]
			slot.texture.image = bpy.data.images['_kinect_']


	def create_embed_widget(self, on_dnd=None, on_resize=None, on_plug=None):
		'''
		Tricks to force our own drag'n'drop callbacks:
			1. wnck-helper shades and sets the window to set-keep-below,
			2. this function attaches an plug-added callback:
				. setting of the drag-drop callback before this would fail
				. in plug-added callback attach the user DND callback
			( just to be safe we set the DND callback on the EventBox container )
		'''
		sock = gtk.Socket()
		eb = gtk.EventBox()
		eb.set_border_width(4)

		if on_dnd and not on_plug:
			sock.connect('plug-added', self._create_embed_widget_helper, on_dnd)
			DND.make_destination(eb)
			eb.connect( 'drag-drop', on_dnd)
		elif on_plug and on_dnd:
			sock.connect(
				'plug-added', 
				self._create_embed_widget_helper2, 
				on_dnd, on_plug,
			)
			DND.make_destination(eb)
			eb.connect( 'drag-drop', on_dnd)

		elif on_dnd: assert 0	# TODO


		if on_resize:
			sock.connect('size-allocate', on_resize)	# REQUIRED by blender

		eb.add( sock )
		return sock, eb

	def _create_embed_widget_helper(self, sock, callback):
		print('[[ on plug dnd helper ]]')
		DND.make_destination(sock)
		sock.connect(
			'drag-drop', callback,
		)
	def _create_embed_widget_helper2(self, sock, on_dnd_callback, on_plug_callback):
		print('[[ on plug dnd helper2 ]]')
		on_plug_callback(sock)
		DND.make_destination(sock)
		sock.connect(
			'drag-drop', on_dnd_callback,
		)



	def create_blender_xembed_socket(self):
		sock = gtk.Socket()
		sock.connect('plug-added', self.on_plug_blender)
		sock.connect('size-allocate',self.on_resize_blender)	# REQUIRED
		eb = gtk.EventBox()
		DND.make_destination(eb)
		eb.connect(
			'drag-drop', self.drop_on_blender_container,
		)
		DND.make_destination(sock)
		sock.connect(
			'drag-drop', self.drop_on_blender_container,
		)
		eb.add( sock )
		return sock, eb

	def after_on_plug_blender(self): pass		# API overload me
	def on_plug_blender(self, xsock):
		print('[[ on plug blender ]]')
		self._blender_window_ready = True
		xsock.set_size_request(
			self._blender_min_width, 
			self._blender_min_height
		)
		gdkwin = xsock.get_plug_window()
		gdkwin.set_title( 'EMBED' )
		Blender.window_expand()
		self.after_on_plug_blender()

	def on_resize_blender(self,sock,rect):
		rect = gtk.cairo_rectangle_int()
		sock.get_allocation( rect )
		if self._blender_window_ready:
			self.blender_width = rect.width
			self.blender_height = rect.height
			Blender.window_resize(
				self.blender_width,
				self.blender_height
			)
			Blender.window_expand()


	def drop_on_chrome_container(self, wid, con, x, y, time):
		ob = self.context.active_object
		print('[[drop on chrome]]', ob)
		return self.drop_on_blender_container(wid, con, x, y, time)



	_xembed_sockets = {}
	def do_xembed(self, xsocket, window_name='Blender'):
		if window_name not in self._xembed_sockets:
			self._xembed_sockets[ window_name ] = {}	# xid : xsock
		# assert xsocket has a parent that is realized #
		xsocket.show()
		while gtk.gtk_events_pending(): gtk.gtk_main_iteration()
		ids = self.get_window_xid( window_name )
		ids.reverse()
		for xid in ids:
			if xid not in self._xembed_sockets[ window_name ]:
				self._xembed_sockets[ xid ] = xsocket
				print('xsocket.add_id',xid)
				xsocket.add_id( xid )
				print('OK', xsocket, type(xsocket))
				return xid
		## we must update gtk main again here,
		## because gtk update could be slaved to blender's redraw 
		while gtk.gtk_events_pending(): gtk.gtk_main_iteration()

	def on_plug_debug(self, xsocket):
		print('----------on plug debug', xsocket)
		gdkwin = xsocket.get_plug_window()
		width = gdkwin.get_width()
		height = gdkwin.get_height()
		gdkwin.show()
		print('gdkwin', width,height)


	def get_window_xid( self, name ):
		'''
		see wnck-helper.py for logic,
		if name in window-full-name, then its xid will be returned.
		'''
		SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
		wnck_helper = os.path.join(SCRIPT_DIR, 'wnck-helper.py')
		assert os.path.isfile( wnck_helper )
		p =os.popen('%s "%s" ' %(wnck_helper, name))
		data = p.read().strip()
		p.close()
		lines = data.splitlines()
		ids = []
		for line in lines:
			if line.startswith('XID='):
				print(line)
				ids.append(
					int( lines[-1].split('=')[-1] )
				)
		return ids

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


	def bind(self, tag, target=None, path=None, index=None, mode='=', min=.0, max=1.0, gain=1.0):
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
				gain = gain,
			)
		else:
			print('WARN: driver already exists', key, self)

		driver = self.drivers[ key ]
		DriverManager.append( driver )
		return driver


class Driver(object):
	INSTANCES = []
	MODES = ('+', '-', '=', icons.MULTIPLY, icons.POSITIVE_OFFSET, icons.NEGATIVE_OFFSET)
	@classmethod
	def get_drivers(self, bo, name):
		r = []
		for d in self.INSTANCES:
			if d.target == bo and d.target_path == name:
				r.append( d )
		return r
		
	def __init__(self, name='', target=None, target_path=None, target_index=None, source=None, source_index=None, source_attribute_name=None, mode='+', min=.0, max=420, gain=1.0):
		self.name = name

		if target_path and '.' in target_path:
			print('DEPRECATION WARNING - do not use "." in target_path')

		self.target = target		# if string assume blender object by name - DEPRECATE
		if type(target) is str:
			print('DEPRECATION WARNING - pass objects not strings', target)
		else:
			if target_path: attr = getattr(target, target_path)
			else: attr = target
			if target_index is not None: self.default = attr[ target_index ]
			else: self.default = attr

		self.target_path = target_path
		self.target_index = target_index
		self.source = source
		self.source_index = source_index
		self.source_attribute_name = source_attribute_name
		self.active = True
		self.gain = gain
		self.mode = mode
		self.min = min
		self.max = max
		self.delete = False	# TODO deprecate

		self.toggle_driver = None
		self.state = None

		Driver.INSTANCES.append(self)	# TODO use DriverManager


	def drop_active_driver(self, button, context, x, y, time, frame):
		output = DND.source_object
		self.toggle_driver = driver = output.bind( 'TOGGLE', target=self, path='active', mode='=' )

		frame.remove( button )
		frame.add( gtk.Label(icons.DRIVER) )
		frame.show_all()

	def get_widget(self, title=None, extra=None, expander=True):
		if title is None: title = self.name

		frame = gtk.Frame()
		b = gtk.CheckButton()
		b.set_tooltip_text('toggle driver')
		b.set_active(self.active)
		b.connect('toggled', lambda b,s: setattr(s,'active',b.get_active()), self)
		DND.make_destination( b )
		b.connect('drag-drop', self.drop_active_driver, frame)
		frame.add( b )

		if expander:
			ex = Expander( title, insert=frame )
			root = gtk.HBox(); ex.add( root )
		else:
			ex = gtk.Frame()
			root = gtk.HBox(); ex.add( root )
			root.pack_start(frame, expand=False)

		adjust = gtk.Adjustment( value=self.gain, lower=self.min, upper=self.max )
		adjust.connect('value-changed', lambda adj,s: setattr(s,'gain',adj.get_value()), self)
		scale = gtk.HScale( adjust )
		scale.set_value_pos(gtk.POS_RIGHT)
		scale.set_digits(2)
		root.pack_start( scale )

		scale.add_events(gtk.GDK_BUTTON_PRESS_MASK)
		scale.connect('button-press-event', self.on_click, ex)

		combo = gtk.ComboBoxText()
		if expander: ex.header.pack_start( combo, expand=False )
		else: root.pack_start( combo, expand=False )
		for i,mode in enumerate( Driver.MODES ):
			combo.append('id', mode)
			if mode == self.mode: gtk.combo_box_set_active( combo, i )
		combo.set_tooltip_text( 'driver mode' )
		combo.connect('changed',lambda c,s: setattr(s,'mode',c.get_active_text()), self )

		if expander: return ex.widget
		else: return ex

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
				elif self.mode == '-':
					vec[ self.target_index ] -= a
				elif self.mode == icons.MULTIPLY:
					vec[ self.target_index ] *= a
				elif self.mode == icons.POSITIVE_OFFSET:
					vec[ self.target_index ] = self.default + a
				elif self.mode == icons.NEGATIVE_OFFSET:
					vec[ self.target_index ] = self.default - a


			else:
				if self.mode == '+':
					value = getattr(sub,aname) + a
				elif self.mode == '=':
					value = a
				elif self.mode == '-':
					value = getattr(sub,aname) - a
				elif self.mode == icons.MULTIPLY:
					value = getattr(sub,aname) * a
				elif self.mode == icons.POSITIVE_OFFSET:
					value = self.default + a
				elif self.mode == icons.NEGATIVE_OFFSET:
					value = self.default - a

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
	if GTK3:
		target = gtk.target_entry_new( 'test',1,gtk.TARGET_SAME_APP )# GTK's confusing API
	else:
		target = None

	def _thread_hack(self):
		i = 0
		while self.dragging: #and i < 10000:
			if gtk.gtk_events_pending():
				gtk.gtk_main_iteration()
			time.sleep(0.01)
			i += 1
		print('EXIT THREAD HACK', i)

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

		start_new_thread(self._thread_hack)

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

	if GTK3:
		target = gtk.target_entry_new( 'file://',2,gtk.TARGET_OTHER_APP )
	else:
		target = None

	#('text/plain', gtk.TARGET_OTHER_APP, 0),	# gnome
	#('text/uri-list', gtk.TARGET_OTHER_APP, 1),	# XFCE
	#('TEXT', 0, 2),
	#('STRING', 0, 3),
XDND = ExternalDND()


############## Simple Driveable Slider ##############
class Slider(object):
	def __init__(self, object=None, name=None, title=None, target_index=None, value=0, min=0, max=1, border_width=2, driveable=True, no_show_all=False, tooltip=None, integer=False, callback=None, precision=2, force_title_above=False):
		self.min = min
		self.max = max


		if title is not None: self.title = title
		else: self.title = name.replace('_',' ')

		if len(self.title) < 20 and not force_title_above:
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
		else: scale.set_digits( precision )

		if callback: adjust.connect( 'value-changed', callback )
		elif object is not None:
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
			'SLIDER', 
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

	def connect( self, callback, *args ):
		if args:
			self.adjustment.connect( 'value-changed', callback, *args )
		else:
			self.adjustment.connect( 'value-changed', callback )


###########################################################

class ToggleButton(object):
	_type = 'toggle'
	def __init__(self, name=None, driveable=True, tooltip=None, frame=True):
		self.name = name

		if frame:
			self.widget = gtk.Frame()
			self.box = gtk.HBox(); self.widget.add( self.box )
		else:
			self.widget = self.box = gtk.HBox()

		if tooltip: self.widget.set_tooltip_text( tooltip )

		if self._type == 'toggle':
			self.button = gtk.ToggleButton( self.name )
		elif self._type == 'check':
			self.button = gtk.CheckButton( self.name )

		self.box.pack_start( self.button, expand=False )

		self.button.connect('button-release-event', self.on_click )

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

class ClutterEmbed(object):
	'''
	this can work with blender, but the clutter widgets flicker, even with forced redraw
	'''
	instances = []
	actors = []
	def __init__(self, width=320, height=240 ):
		self.instances.append( self )

		self.widget = gtk.EventBox()
		self.embed = embed = clutter.gtk_clutter_embed_new()
		self.widget.add( embed )
		embed.set_size_request(width, height)
		embed.connect('realize',self.realized)
		self.stage = None
		self.children = []

		#self.embed.set_double_buffered(True)	# looks worse

	def add( self, widget ):
		print('adding clutter widget',widget)
		# create actor as needed
		widget.show_all()	# need to show first
		self.children.append( widget )
		actor = clutter.gtk_clutter_actor_new_with_contents( widget )
		self.actors.append( actor )
		return actor


	def realized(self,widget):
		#for child in self.children: child.show_all()	# segfaults
		embed = self.embed
		#embed.realize()
		print('getting stage...')
		self.stage = clutter.gtk_clutter_embed_get_stage( embed )
		clutter.actor_show( self.stage )

		rect = clutter.rectangle_new()	#clutter.Rectangle()
		clr = clutter.color_new( 100,1,0,100 )
		clutter.rectangle_set_color(rect, clr)	#rect.set_color( clr )
		rect.set_size(100, 100)
		rect.set_anchor_point(50, 50)
		rect.set_position(150, 150)
		rect.set_rotation(clutter.CLUTTER_X_AXIS, 45.0, 0, 0, 0)
		clutter.container_add_actor( self.stage, rect )

		for actor in self.actors:
			clutter.container_add_actor( self.stage, actor )
			clutter.actor_show( actor )

	@classmethod
	def update(self):
		for a in self.instances:
			if a.stage:
				#clutter.clutter_redraw( a.stage )
				#print('force redraw..',a.stage)
				a.stage.queue_redraw()	#relayout()	# relayout is slow!

		for actor in self.actors:
			actor.queue_redraw()


class Expander( object ):
	'''
	Like gtk.Expander but can have extra buttons on header


	if 0:
		rect = clutter.rectangle_new()	#clutter.Rectangle()
		clr = clutter.color_new( 100,1,0,100 )
		clutter.rectangle_set_color(rect, clr)	#rect.set_color( clr )
		rect.set_size(100, 100)
		rect.set_anchor_point(50, 50)
		rect.set_position(150, 150)
		rect.set_rotation(clutter.CLUTTER_X_AXIS, 45.0, 0, 0, 0)
		clutter.container_add_actor( stage, rect )
	'''

	def __init__(self, name='', border_width=4, full_header_toggle=True, insert=None, append=None):
		self.name = name
		self.children = []
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

		if append:
			self.header.pack_start( append, expand=False )


	def toggle(self,b):
		if b.get_active():
			if self._full_header_toggle: b.set_label( '%s  %s' %(icons.EXPANDER_DOWN,self.name) )
			else: b.set_label( icons.EXPANDER_DOWN )
			for child in self.children:
				child.set_no_show_all(False)
				child.show_all()
				child.set_no_show_all(True)

			#self.actor.animate(
			#	clutter.CLUTTER_LINEAR, 800,
			#	scale_x=1.0, scale_y=1.0,
			#)


		else:
			if self._full_header_toggle: b.set_label( '%s  %s' %(icons.EXPANDER_UP,self.name) )
			else: b.set_label( icons.EXPANDER_UP )
			for child in self.children: child.hide()

			#self.actor.animate(
			#	clutter.CLUTTER_LINEAR, 500,
			#	scale_x=1.5, scale_y=0.5,
			#)


	def add( self, child): self.append( child, expand=False )
	def pack_start(self, child, expand=True ): self.append( child, expand )
	def append(self, child, expand=True):
		child.show_all()
		child.set_no_show_all(True)
		child.hide()
		self.children.append( child )
		self.root.pack_start( child, expand=expand )



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
	def __init__( self, ob, name, title=None, expanded=True, min=0.0, max=1.0 ):
		self.min = min
		self.max = max

		drivers = Driver.get_drivers(ob, name)		# classmethod
		vec = getattr(ob,name)

		if title: ex = gtk.Expander(title)
		else: ex = gtk.Expander(name)
		ex.set_expanded( expanded )
		self.widget = ex

		note = gtk.Notebook(); ex.add( note )
		#note.set_tab_pos( gtk.POS_RIGHT )
		note.set_size_request(240,80)

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
		# TODO check for "rotation_euler" and force rotation_mode to 'EULER' ?
		output = DND.source_object
		driver = output.bind( 'XXX', target=target, path=path, index=index, min=self.min, max=self.max )
		widget = driver.get_widget()
		page.pack_start( widget, expand=False )
		widget.show_all()


#########################################################

class PopupWindow(object):
	def show(self):
		self.window.show_all()
		if self._system_header_hack:
			self._system_header_hack.hide()

	'''disable set_keep_above for non-popup style window'''
	def __init__(self, title='', width=None, height=None, child=None, toolbar=None, skip_pager=False, deletable=False, on_close=None, set_keep_above=False, fullscreen=False):
		self.object = None
		if not toolbar: self.toolbar = toolbar = gtk.Frame(); toolbar.add( gtk.Label() )
		self.toolbar = toolbar

		self.window = win = gtk.Window()
		win.set_title( title )
		win.set_position( gtk.WIN_POS_MOUSE )
		if width and height:
			win.set_size_request( width, height )

		if set_keep_above: win.set_keep_above(True)
		if skip_pager: win.set_skip_pager_hint(True)
		#win.set_skip_taskbar_hint(True)
		#win.set_size_request( width, height )
		#win.set_opacity( 0.9 )

		## DEPRECATE POPUP WINDOW ##
		#win.set_decorated( False )
		#win.set_deletable( deletable )

		self.root = gtk.EventBox()
		win.add( self.root )

		vbox = gtk.VBox(); self.root.add( vbox )

		## need this for extra border when fullscreen ##
		self._system_header_hack = None
		if fullscreen:
			self._system_header_hack = hack = gtk.VBox()
			for i in range(2): hack.pack_start( gtk.Label() )
			hack.show_all()
			vbox.pack_start( self._system_header_hack, expand=False )
			self._system_header_hack.set_no_show_all(True)

		header = gtk.HBox()
		vbox.pack_start( header, expand=False )


		#b = gtk.ToggleButton('⟔'); b.set_border_width(0)
		#b.set_relief( gtk.RELIEF_NONE )
		#b.set_active(True)
		#b.connect('button-press-event', self.on_resize)
		#header.pack_start( b, expand=False )

		header.pack_start( toolbar )

		b = gtk.ToggleButton('∸'); b.set_border_width(1)
		if set_keep_above: b.set_active(True)
		b.connect('toggled', lambda b: win.set_keep_above(b.get_active()))
		header.pack_start( b, expand=False )


		#b = gtk.ToggleButton('🌁'); b.set_border_width(1)
		#b.set_active(True)
		#b.connect('toggled', self.toggle_transparent)
		#header.pack_start( b, expand=False )

		if fullscreen:
			b = gtk.ToggleButton( icons.FULLSCREEN ); b.set_relief( gtk.RELIEF_NONE )
			b.connect('toggled',self.toggle_fullscreen)
			header.pack_start( b, expand=False )



		if deletable and on_close:
			b = gtk.ToggleButton( icons.DELETE ); b.set_border_width(1)
			b.connect('clicked', on_close)
			header.pack_start( b, expand=False )


		self.root.add_events( gtk.GDK_BUTTON_PRESS_MASK )
		self.root.connect('button-press-event', self.on_press)


		if child:
			child.set_border_width(3)
			self.child = child
			vbox.pack_start( child )

	def toggle_transparent(self,button):
		if button.get_active(): self.window.set_opacity( 0.8 )
		else: self.window.set_opacity( 1.0 )


	def on_resize(self,widget, event):
		event = gtk.GdkEventButton( pointer=ctypes.c_void_p(event), cast=True )
		if event.button == 1:
			self.window.begin_resize_drag( 
				gtk.GDK_WINDOW_EDGE_NORTH_WEST, # edge
				event.button,
				int(event.x_root), 	# c_double
				int(event.y_root), 
				event.time
			)

	def on_press(self, widget, event):
		event = gtk.GdkEventButton( pointer=ctypes.c_void_p(event), cast=True )
		if event.button == 1:
			self.window.begin_move_drag( 
				event.button, 
				int(event.x_root), 	# c_double
				int(event.y_root), 
				event.time
			)

	def toggle_fullscreen(self,b):
		if b.get_active():
			if self._system_header_hack:
				self._system_header_hack.set_no_show_all(False)
				self._system_header_hack.show_all()	# fixes gnome task bar over
			self.window.set_keep_above(True)
			self.window.fullscreen()
		else:
			if self._system_header_hack:
				self._system_header_hack.hide()
			self.window.set_keep_above(False)
			self.window.unfullscreen()


######################################################################

def make_detachable( widget ):
	widget.drag_source_set(
		gtk.GDK_BUTTON1_MASK, 
		_detachable_target_, 1, 
		gtk.GDK_ACTION_COPY
	)
	widget.connect('drag-end', _on_detach)

def _on_detach( widget, gcontext ):
	print(widget, gcontext)
	parent = widget.get_parent()
	#parent.remove( widget )		# getting confused with "remove" function in gtk wrapper?
	gtk.container_remove( parent, widget )
	w = ToolWindow( child=widget )
	w.window.show_all()

class Detachable( object ):
	if GTK3:
		_detachable_target_ = gtk.target_entry_new( 'detachable',2,0)	#gtk.TARGET_OTHER_APP )	

	def make_detachable(self,widget, on_detach):
		## DEPRECATED - not safe even with thread hack TODO FIXME
		#self.widget.drag_source_set(
		#	gtk.GDK_BUTTON1_MASK, 
		#	self._detachable_target_, 1, 
		#	gtk.GDK_ACTION_COPY
		#)
		#self.widget.connect('drag-end', on_detach)
		pass
		

class DetachableExpander( Detachable ):

	def __init__(self, name, short_name=None, expanded=False):
		self.name = name
		self.short_name = short_name
		self.detached = False
		self.popup = None
		if short_name is not None:
			self.widget = gtk.Expander(short_name)
		else:
			self.widget = gtk.Expander(name)
		if expanded: self.widget.set_expanded(True)

		self.widget.connect('activate', self.on_expand)
		self.make_detachable( self.widget, self.on_detach )

	def on_expand(self,widget):
		if self.popup:
			if widget.get_expanded(): self.popup.window.resize( 80, 20 )
		elif self.short_name is not None:
			if widget.get_expanded(): widget.set_label(self.short_name)
			else: widget.set_label(self.name)


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
		self.widget.set_label( self.name )
		parent = widget.get_parent()
		gtk.container_remove( parent, widget )
		self.popup = PopupWindow( title=self.name, child=self.widget )
		self.widget.set_expanded(True)
		self.popup.window.show_all()



class FileEntry( object ):
	## for drag and drop ##
	def __init__(self, name, callback, *args):
		self.name = name
		self.callback = callback
		self.callback_args = args

		self.widget = bx = gtk.HBox()
		bx.pack_start( gtk.Label(name), expand=False )

		self.entry = e = gtk.Entry()
		e.connect('changed', self.changed)
		bx.pack_start( e, expand=True )

		b = gtk.Button( icons.REFRESH )
		bx.pack_start( b, expand=False )
		b.set_relief( gtk.RELIEF_NONE )

		b = gtk.Button( icons.DELETE )
		b.connect('clicked', self.delete)
		bx.pack_start( b, expand=False )
		b.set_relief( gtk.RELIEF_NONE )

	def changed( self, entry ):
		url = urllib.parse.unquote(entry.get_text()).strip()
		if url.startswith('file://'): url = url[ 7 : ]
		if os.path.isfile(url):
			gtk.editable_set_editable(entry,False)
			self.callback( url, *self.callback_args )

	def delete(self,button):
		self.entry.set_text('')
		gtk.editable_set_editable(self.entry,True)


############# Generic Game Device ###############

class GameDevice(object):
	def configure_device(self, axes=0, buttons=0, hats=0):
		self.num_axes = axes
		self.num_buttons = buttons
		self.num_hats = hats
		self.axes = [0.0] * axes
		self.buttons = [0] * buttons
		self.hats = [ False ] * hats
		self.widget = None

	def _get_header_widget(self): pass
	def _get_footer_widget(self): pass

	def get_widget(self, device_name='device name'):
		if not hasattr(self,'num_axes'):
			print('ERROR, device.configure_device( axes, buttons ) not called')
			assert False

		self.widget = root = gtk.VBox()
		root.set_border_width(2)

		header = self._get_header_widget()
		if header: root.pack_start( header, expand=False )

		split = gtk.HBox()
		root.pack_start( split )

		ex = gtk.Expander('Axes'); ex.set_expanded(True)
		split.pack_start( ex, expand=True )
		box = gtk.VBox(); ex.add( box )
		self.axes_gtk = []
		for i in range(self.num_axes):
			row = gtk.HBox(); row.set_border_width(4)
			box.pack_start( row, expand=False )

			a = gtk.EventBox()
			title = '%s%s.axis%s' %(device_name,self.index,i)
			#DND.make_source(a, self.callback, 'axes', i, title)
			output = DeviceOutput( title, source=self.axes, index=i )
			DND.make_source( a, output )

			a.add( gtk.Label(icons.DND) )
			row.pack_start( a, expand=False )

			adjust = gtk.Adjustment( value=.0, lower=-1, upper=1 )
			self.axes_gtk.append( adjust )
			scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
			scale.set_digits(2)
			row.pack_start( scale )

		############## buttons ##############
		ex = gtk.Expander('Buttons'); ex.set_expanded(True)
		split.pack_start( ex, expand=False )
		box = gtk.VBox(); ex.add( box )
		self.buttons_gtk = []

		row = gtk.HBox(); row.set_border_width(4)
		box.pack_start( row, expand=False )
		for i in range(self.num_buttons):
			if not i%4:
				row = gtk.HBox(); row.set_border_width(4)
				box.pack_start( row, expand=False )

			a = gtk.EventBox()
			title = 'gamepad%s.button%s' %(self.index,i)
			b = gtk.ToggleButton('%s'%i); self.buttons_gtk.append( b )
			#DND.make_source(b, self.callback, 'buttons', i, title)
			output = DeviceOutput( title, source=self.buttons, index=i )
			DND.make_source( b, output )
			a.add( b )
			row.pack_start( a, expand=True )

		footer = self._get_footer_widget()
		if footer: root.pack_start( footer, expand=False )


		return self.widget


class Toolbar(object):
	'''
	simple toolbar with a center modal area,
	optional left and right extra tools.
	'''
	def __init__(self, left_tools=[], right_tools=[], modal_frame=None, expand=False):
		self.widget = root = gtk.HBox()
		root.set_border_width(2)

		for a in left_tools:
			root.pack_start( a, expand=False )

		if expand: root.pack_start( gtk.Label() )
		self._frame = modal_frame or gtk.Frame()
		self._modal = gtk.Label()
		self._frame.add( self._modal )
		root.pack_start( self._frame )
		if expand: root.pack_start( gtk.Label() )

		for a in right_tools:
			root.pack_start( a, expand=False )

	def reset(self):
		self._frame.remove( self._modal )
		self._modal = eb = gtk.Frame()
		self._frame.add( self._modal )
		return self._modal


