# _*_ coding: utf-8 _*_
# Pyppet2
# Feb20, 2012
# by Brett Hart
# http://pyppet.blogspot.com
# License: BSD
VERSION = '1.9.4i'

import os, sys, time, subprocess, threading, math, ctypes
import wave
from random import *

## make sure we can import from same directory ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.append( SCRIPT_DIR )

from core import *		# core API
SimpleSlider = Slider

if sys.platform.startswith('win'):
	#dll = ctypes.CDLL('')	# this won't work on Windows
	#print(dll, dll._handle)	# _handle is a number address, changes each time

	#h=ctypes.windll.kernel32.GetModuleHandleW(None)
	h=ctypes.windll.kernel32.GetModuleHandleA(None)

	print(h)
	#from ctypes import wintypes
	#blender = ctypes.CDLL('blender.exe')
	#GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
	#GetCurrentProcess.restype = wintypes.HANDLE
	#phandle = GetCurrentProcess()
	#print(phandle)
	blender = ctypes.CDLL( '', handle=h )
	print(blender)
	func = blender.glPushMatrix
	print( func )
	func = blender.CTX_wm_window
	print( func )
	assert 0

	cygwin = ctypes.CDLL( 'cygwin1.dll' )
	print( cygwin )
	dlopen = cygwin.dlopen		# dlopen defined in dlfcn.h
	dlopen.argtypes = (ctypes.c_char_p, ctypes.c_int)
	dlopen.restype = ctypes.c_void_p
	#err:ntdll:RtlpWaitForCriticalSection section 0x610d1ef8 "?" wait timed out in thread 0018, blocked by 0000, retrying (60 sec)
	handle = dlopen( ctypes.c_char_p(b''), 2 )		# blocks
	print(handle)
	assert 0

from openGL import *
import SDL as sdl
import fluidsynth as fluid
import openal as al
import fftw
#import cv
#import highgui as gui

import Webcam
import Kinect
import Wiimote
import Blender
import Physics

import icons

import bpy, mathutils
from bpy.props import *

gtk.init()
sdl.Init( sdl.SDL_INIT_JOYSTICK )

ENGINE = Physics.ENGINE		# physics engine singleton


################# Server ################
import wsgiref
import wsgiref.simple_server
import io, socket, select, pickle, urllib
import urllib.request
import urllib.parse

import websocket
import json

##################### PyRNA ###################
bpy.types.Object.webgl_stream_mesh = BoolProperty( name='stream mesh to webGL client', default=False )

bpy.types.Object.UID = IntProperty(
    name="unique ID", description="unique ID for webGL client", 
    default=0, min=0, max=2**14)

def get_object_by_UID( uid ):
	if type(uid) is str: uid = int( uid.replace('_','') )
	for ob in bpy.data.objects:
		if ob.UID == uid: return ob
	print('UID not found', uid)
	assert 0

def UID( ob ):
	'''
	sets and returns simple unique ID for object.
	note: when merging data, need to check all ID's are unique
	'''
	if ob.UID == 0: ob.UID = max( [o.UID for o in bpy.data.objects] ) + 1
	return ob.UID

def ensure_unique_ids():
	pass	# TODO

#######################################################################
def rgb2gdk( r, g, b ): return gtk.GdkColor(0,int(r*65535),int(g*65535),int(b*65535))
def gdk2rgb( c ): return (c.red/65536.0, c.green/65536.0, c.blue/65536.0)

BLENDER_GREY = 114.0 / 255.0
BG_COLOR = rgb2gdk( BLENDER_GREY, BLENDER_GREY, BLENDER_GREY )
#BG_COLOR = rgb2gdk( 0.94, 0.94, 0.96 )
BG_COLOR_DARK = rgb2gdk( 0.5, 0.5, 0.5 )
DRIVER_COLOR = gtk.GdkRGBA(0.2,0.4,0.0,1.0)



################# from bpyengine #######################
STREAM_BUFFER_SIZE = 2048

def _create_stream_proto():
	proto = {}
	tags = 'ID NAME POSITION ROTATION SCALE DATA SELECTED TYPE MESH LAMP CAMERA SPEAKER ANIMATIONS DISTANCE ENERGY VOLUME MUTE LOD'.split()
	for i,tag in enumerate( tags ): proto[ tag ] = chr(i)		# up to 256
	return proto
STREAM_PROTO = _create_stream_proto()
globals().update( STREAM_PROTO )


def get_object_url(ob):
	if not ob.remote_path: url = 'http://%s/objects/%s' %(ob.remote_server,ob.name)
	elif ob.remote_path.startswith('/'): url = 'http://%s%s' %(ob.remote_server, ob.remote_path)
	else: url = 'http://%s/%s' %(ob.remote_server, ob.remote_path)
	return url
################# end from bpyengine ###################


def save_selection():
	r = {}
	for ob in Pyppet.context.scene.objects: r[ ob.name ] = ob.select
	return r

def restore_selection( state ):
	for name in state:
		Pyppet.context.scene.objects[ name ].select = state[name]


def dump_collada_pure_base_mesh( name, center=False ):	# NOT USED
	state = save_selection()
	for ob in Pyppet.context.scene.objects: ob.select = False
	ob = bpy.data.objects[ name ]

	parent = ob.parent
	ob.parent = None	# stupid collada exporter!
	ob.select = True

	materials = []
	for i,mat in enumerate(ob.data.materials):
		materials.append( mat )
		ob.data.materials[ i ] = None

	hack = bpy.data.materials.new(name='tmp')
	hack.diffuse_color = [0,0,0]

	mods = []
	for mod in ob.modifiers:
		if mod.type == 'MULTIRES':
			hack.diffuse_color.r = 1.0	# ugly way to hide HINTS in the collada
		if mod.type in ('ARMATURE', 'MULTIRES', 'SUBSURF') and mod.show_viewport:
			mod.show_viewport = False
			mods.append( mod )

	if ob.data.materials: ob.data.materials[0] = hack
	else: ob.data.materials.append( hack )

	#arm = ob.find_armature()		# armatures not working in Three.js ?
	#if arm: arm.select = True

	loc = ob.location
	if center: ob.location = (0,0,0)

	#bpy.ops.wm.collada_export( filepath='/tmp/dump.dae', check_existing=False, selected=True )
	url = '/tmp/%s.dae' %name
	S = Blender.Scene( Pyppet.context.scene )
	S.collada_export( url, True )	# using ctypes collada_export avoids polling issue

	if center: ob.location = loc

	for i,mat in enumerate(materials): ob.data.materials[i]=mat
	for mod in mods: mod.show_viewport = True
	ob.parent = parent

	restore_selection( state )
	return open(url,'rb').read()


############ seems a bit funny that this works ############
SWAP_MESH = mathutils.Matrix.Rotation(math.pi/2, 4, 'X')
SWAP_OBJECT = mathutils.Matrix.Rotation(-math.pi/2, 4, 'X')
#######################################################

def dump_collada( ob, center=False ):
	name = ob.name
	state = save_selection()
	for o in Pyppet.context.scene.objects: o.select = False

	hack = bpy.data.materials.new(name='tmp')
	hack.diffuse_color = [0,0,0]

	mods = []
	for mod in ob.modifiers:
		if mod.type == 'MULTIRES':
			hack.diffuse_color.r = 1.0	# ugly way to hide HINTS in the collada
		if mod.type in ('ARMATURE', 'MULTIRES', 'SUBSURF') and mod.show_viewport:
			mod.show_viewport = False
			mods.append( mod )

	############## collaspe modifiers into mesh data #############
	data = ob.to_mesh(Pyppet.context.scene, True, "PREVIEW")
	for mod in mods: mod.show_viewport = True  # restore modifiers

	data.transform( SWAP_MESH )	# flip YZ for Three.js
	data.calc_normals()

	############## clear materials and assign hack material #######
	for i,mat in enumerate(data.materials): data.materials[ i ] = None
	if data.materials: data.materials[0] = hack
	else: data.materials.append( hack )

	############## create temp object for export ############
	uid = UID( ob )
	O = bpy.data.objects.new(name='__%s__'%uid, object_data=data)
	Pyppet.context.scene.objects.link( O )
	O.matrix_world = ob.matrix_world.copy()
	O.select = True

	############## dump collada ###########
	url = '/tmp/%s.dae' %name
	S = Blender.Scene( Pyppet.context.scene )
	S.collada_export( url, True )	# using ctypes collada_export avoids polling issue

	############## clean up ###########
	Pyppet.context.scene.objects.unlink(O)
	O.user_clear()
	O.select=False
	bpy.data.objects.remove(O)

	restore_selection( state )
	return open(url,'rb').read()

#####################################


class FX(object):
	def __init__( self, name, enabled, **kw ):
		self.name = name
		self.enabled = enabled
		self.uniforms = list(kw.keys())
		for name in kw:
			setattr(self, name, kw[name])

	def get_uniforms(self):
		r = {}
		for name in self.uniforms: r[name]=getattr(self,name)
		return r

	def get_widget(self):
		root = gtk.VBox()
		#b = gtk.CheckButton(self.name)
		#root.pack_start( b, expand=False )
		#b.set_active(self.enabled)
		#b.connect('toggled', lambda b: setattr(self,'enabled',b.get_active()) )

		b = CheckButton(self.name)
		b.connect( self, path='enabled' )
		root.pack_start( b.widget, expand=False )


		for name in self.uniforms:
			slider = SimpleSlider( self, name=name, title='', max=10.0, driveable=True )
			root.pack_start( slider.widget, expand=False )

		return root

class WebGL(object):
	def __init__(self):
		self.effects = []
		self.effects.append( FX('fxaa', True) )
		#self.effects.append( FX('ssao', False) )
		self.effects.append( FX('dots', False, scale=1.8) )
		self.effects.append( FX('vignette', True, darkness=1.0) )
		self.effects.append( FX('bloom', True, opacity=0.333) )
		self.effects.append( FX('glowing_dots', False, scale=0.23) )
		self.effects.append( FX('blur_horizontal', True, r=0.5) )
		self.effects.append( FX('blur_vertical', True, r=0.5) )
		self.effects.append( FX('noise', False, nIntensity=0.01, sIntensity=0.5) )
		self.effects.append( FX('film', False, nIntensity=10.0, sIntensity=0.1) )

	def get_fx_widget(self):
		root = gtk.VBox()
		root.set_border_width(3)
		for fx in self.effects: root.pack_start( fx.get_widget(), expand=False )
		return root

#####################
class WebSocketServer( websocket.WebSocketServer ):
	buffer_size = 8096
	client = None
	webGL = WebGL()

	def start(self):
		print('--starting websocket server thread--')
		self.active = True
		threading._start_new_thread(
			self.loop, ()
		)

	def loop(self):
		lsock = self.socket(self.listen_host, self.listen_port)
		while self.active:
			time.sleep(0.1)
			try:
				self.poll()
				ready = select.select([lsock], [], [], 1)[0]
				if lsock in ready: startsock, address = lsock.accept()
				else: continue
			except Exception: continue
			## keep outside of try for debugging ##
			self.top_new_client(startsock, address)	# calls new_client()

	def new_client(self): print('new client', self.client)

	_bps_start = None
	_bps = 0
	flipMat = mathutils.Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))

	def update( self, context ):
		if not self.client: return
		msg = { 
			'meshes':{}, 
			'lights':{}, 
			'FX':{},
			'camera': {
				'rand':Pyppet.camera_randomize,
				'focus':Pyppet.camera_focus,
				'aperture':Pyppet.camera_aperture,
				'maxblur':Pyppet.camera_maxblur,
			},
		}

		for fx in  self.webGL.effects:
			msg['FX'][fx.name]= ( fx.enabled, fx.get_uniforms() )

		streaming_meshes = []
		for ob in context.scene.objects:
			if ob.type not in ('MESH','LAMP'): continue
			if ob.type=='MESH' and not ob.data.uv_textures: continue	# UV's required to generate tangents

			loc, rot, scl = (SWAP_OBJECT*ob.matrix_world).decompose()
			loc = loc.to_tuple()
			scl = scl.to_tuple()
			rot = (rot.w, rot.x, rot.y, rot.z)
			pak = { 'pos':loc, 'rot':rot, 'scl':scl }

			if ob.type == 'LAMP':
				msg[ 'lights' ][ '__%s__'%UID(ob) ] = pak
				pak['energy'] = ob.data.energy
				pak['color'] = [ round(a,3) for a in ob.data.color ]
				pak['dist'] = ob.data.distance

			elif ob.type == 'MESH':
				msg[ 'meshes' ][ '__%s__'%UID(ob) ] = pak
				specular = None
				if ob.data.materials:
					mat = ob.data.materials[0]
					specular = mat.specular_hardness
				pak['color'] = [ round(x,3) for x in ob.color ]
				pak['spec'] = specular

				disp = 1.0
				pak['disp_bias'] = 0.0
				for mod in ob.modifiers:
					if mod.type=='DISPLACE':
						pak['disp_bias'] = mod.mid_level - 0.5
						disp = mod.strength
						break
				pak['disp'] = disp

				if ob == context.active_object: pak[ 'selected' ] = True
				if ob.webgl_stream_mesh or ob == context.active_object:
					streaming_meshes.append( ob )


		for ob in streaming_meshes:
			pak = msg[ 'meshes' ][ '__%s__'%ob.UID ]

			mods = []
			for mod in ob.modifiers:
				if mod.type in ('SUBSURF','MULTIRES') and mod.show_viewport:
					mods.append( mod )
			for mod in mods: mod.show_viewport = False
			data = ob.to_mesh( context.scene, True, "PREVIEW")
			for mod in mods: mod.show_viewport = True

			data.transform( SWAP_MESH )
			N = len( data.vertices )
			verts = [ 0.0 for i in range(N*3) ]
			data.vertices.foreach_get( 'co', verts )
			bpy.data.meshes.remove( data )
			verts = [ round(a,3) for a in verts ]	# optimize!

			subsurf = 0
			for mod in ob.modifiers:
				if mod.type == 'SUBSURF':
					subsurf += mod.levels		# mod.render_levels

			pak[ 'verts' ] = verts
			pak[ 'subsurf' ] = subsurf



		## dump to json ##
		data = json.dumps( msg )
		#print(data)
		rawbytes = data.encode('utf-8')
		cqueue = [ rawbytes ]

		self._bps += len( rawbytes )
		now = time.time()
		if self._bps_start is None or now-self._bps_start > 1.0:
			#print('kilobytes per second', self._bps/1024)
			self._bps_start = now
			self._bps = 0
			## monkey uncompressed head about 520KB per second ##
			## monkey head with optimize round(4) is 380KB per second ##
			## monkey head with optimize round(3) is 350KB per second ##



		## send the data ##
		rlist = [self.client]
		wlist = [self.client]

		ins, outs, excepts = select.select(rlist, wlist, [], 1)
		if excepts: raise Exception("Socket exception")

		if self.client in outs:
			# Send queued target data to the client
			try:
				pending = self.send_frames(cqueue)
				if pending: print('failed to send', pending)
			except:
				self.client = None

		elif not outs:
			print('client not ready to read....')

		if self.client in ins:
			# Receive client data, decode it, and send it back
			frames, closed = self.recv_frames()
			print('got from client', frames)
			if closed:
				print('CLOSING CLIENT')
				try:
					self.send_close()
					raise self.EClose(closed)
				except: pass
				self.client = None



#####################
class WebServer( object ):
	CLIENT_SCRIPT = open( os.path.join(SCRIPT_DIR,'client.js'), 'rb' ).read().decode('utf-8')

	def close(self): self.httpd.close()

	def init_webserver(self, port=8080, timeout=0.01):
		self.hires_progressive_textures = False
		self.httpd_port = port
		self.httpd = wsgiref.simple_server.make_server( self.host, self.httpd_port, self.httpd_reply )
		self.httpd.timeout = timeout
		self.THREE = None
		path = os.path.join(SCRIPT_DIR, 'javascripts/Three.js')
		if os.path.isfile( path ): self.THREE = open( path, 'rb' ).read()
		else: print('missing ./javascripts/Three.js')

	def get_header(self, title='Pyppet WebGL', webgl=False):
		h = [
			'<!DOCTYPE html><html lang="en">',
			'<head><title>%s</title>' %title,
			'<meta charset="utf-8">',
			'<meta name="viewport" content="width=device-width, user-scalable=yes, minimum-scale=1.0, maximum-scale=1.0">',
		]

		h.append( '<script src="/javascripts/websockify/util.js"></script>' )
		h.append( '<script src="/javascripts/websockify/webutil.js"></script>' )
		h.append( '<script src="/javascripts/websockify/base64.js"></script>' )
		h.append( '<script src="/javascripts/websockify/websock.js"></script> ' )

		h.append( '<style>' )
		h.append( 'body{margin:auto; background-color: #888; padding-top: 2px; font-family:sans; color: #666; font-size: 0.8em}' )
		h.append( '#container{ margin:auto; padding: 4px; background-color: #fff; }' )
		h.append( '</style>' )

		h.append( '</head><body>' )

		if webgl and self.THREE:
			h.append( '<script type="text/javascript" src="/javascripts/Three.js"></script>' )

			h.append( '<script type="text/javascript" src="/javascripts/modifiers/SubdivisionModifier.js"></script>' )

			h.append( '<script type="text/javascript" src="/javascripts/ShaderExtras.js"></script>' )
			for tag in 'EffectComposer RenderPass BloomPass ShaderPass MaskPass SavePass FilmPass DotScreenPass'.split():
				h.append( '<script type="text/javascript" src="/javascripts/postprocessing/%s.js"></script>' %tag )



			######################### Pyppet WebGL Client ##############################
			self.CLIENT_SCRIPT = open( os.path.join(SCRIPT_DIR,'client.js'), 'rb' ).read().decode('utf-8')
			h.append( '<script type="text/javascript">' )
			h.append( 'var HOST = "%s";' %socket.gethostbyname(socket.gethostname()) )
			if self.hires_progressive_textures:
				h.append( 'var MAX_PROGRESSIVE_TEXTURE = 2048;' )
				h.append( 'var MAX_PROGRESSIVE_NORMALS = 1024;' )
				h.append( 'var MAX_PROGRESSIVE_DISPLACEMENT = 512;' )
				h.append( 'var MAX_PROGRESSIVE_DEFAULT = 256;' )
			else:
				h.append( 'var MAX_PROGRESSIVE_TEXTURE = 256;' )
				h.append( 'var MAX_PROGRESSIVE_NORMALS = 128;' )
				h.append( 'var MAX_PROGRESSIVE_DISPLACEMENT = 128;' )
				h.append( 'var MAX_PROGRESSIVE_DEFAULT = 128;' )


			h.append( self.CLIENT_SCRIPT )
			h.append( '</script>' )

		return '\n'.join( h )

	def httpd_reply( self, env, start_response ):	# main entry point for http server
		agent = env['HTTP_USER_AGENT']		# browser type
		if agent == 'Python-urllib/3.2': return self.httpd_reply_peer( env, start_response )
		else: return self.httpd_reply_browser( env, start_response )

	def httpd_reply_browser(self, env, start_response ):
		path = env['PATH_INFO']
		host = env['HTTP_HOST']
		client = env['REMOTE_ADDR']
		arg = env['QUERY_STRING']

		relpath = os.path.join( SCRIPT_DIR, path[1:] )

		if path=='/favicon.ico':
			start_response('200 OK', [('Content-Length','0')])
			return []
		elif path == '/':
			if self.THREE:
				f = io.StringIO()
				start_response('200 OK', [('Content-Type','text/html; charset=utf-8')])
				f.write( self.get_header(webgl=True) )
				return [f.getvalue().encode('utf-8')]

			else:
				print('ERROR: Three.js is missing!')

		elif path=='/index':
			f = io.StringIO()

			start_response('200 OK', [('Content-Type','text/html; charset=utf-8')])
			f.write( self.get_header() )

			if self.clients:
				f.write('<h2>Streaming Clients</h2><ul>')
				for a in self.clients: f.write('<li><a href="http://%s">%s</a></li>' %(a,a))
				f.write('</ul>')
			#if self.servers:
			#	f.write('<h2>Streaming Servers</h2><ul>')
			#	for a in self.servers: f.write('<li>%s</li>' %a)
			#	f.write('</ul>')

			f.write('<hr/>')
			a = sort_objects_by_type( Pyppet.context.scene.objects )
			for type in a:
				if not a[type]: continue
				f.write('<h3>%s</h3>'%type)
				f.write('<ul>')
				for ob in a[type]:
					if ob.use_remote:
						f.write('<li><a href="/objects/%s"><i>%s</i></a></li>' %(ob.name,ob.name))
					else:
						f.write('<li><a href="/objects/%s">%s</a></li>' %(ob.name,ob.name))
				f.write('</ul>')

			return [f.getvalue().encode('utf-8')]


		elif path.startswith('/objects/'):
			url = path[ 9 : ]
			name = path.split('/')[-1]
			if name.endswith('.dae'):
				start_response('200 OK', [('Content-Type','text/xml; charset=utf-8')])
				uid = name[ : -4 ]
				ob = get_object_by_UID( uid )
				if arg == 'center':
					return [ dump_collada(ob,center=True) ]
				else:
					return [ dump_collada(ob) ]

			elif os.path.isfile( url ):
				data = open( url, 'rb' ).read()
				start_response('200 OK', [('Content-Length',str(len(data)))])
				return [ data ]

			else:
				print('WARNING: unknown request', path)


		elif path.startswith('/javascripts/'):
			start_response('200 OK', [('Content-Type','text/javascript; charset=utf-8')])
			data = open( relpath, 'rb' ).read()
			return [ data ]

		elif path.startswith('/bake/'):
			print( 'PATH', path, arg)
			uid = path.split('/')[-1][ :-4 ]	# strip ".jpg"
			ob = get_object_by_UID( uid )
			data = Pyppet.bake_image( ob, *arg.split('|') )
			start_response('200 OK', [('Content-Length',str(len(data)))])
			return [ data ]


		elif path.startswith('/textures/'):
			data = open( relpath, 'rb' ).read()
			start_response('200 OK', [('Content-Length',str(len(data)))])
			return [ data ]

		else:
			print( 'SERVER ERROR: invalid path', path )




class Server( WebServer ):
	def __init__(self, host='localhost'):
		self.host = host
		self.init_webserver()
		self.clients = {}

	def enable_streaming( self, client ):
		n = len(self.clients)
		port = self.httpd_port + 100 + n
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # UDP
		sock.connect( (self.host,port) )		# connect means server mode
		self.clients[ client ] = {
			'objects':{}, 
			'socket': sock,
			'port': port,
		}


	def httpd_reply_peer(self, env, start_response ):
		path = env['PATH_INFO']
		print('peer requesting...', path)
		host = env['HTTP_HOST']
		client = env['REMOTE_ADDR']
		start_response('200 OK', [('Content-Type','text/html; charset=utf-8')])
		arg = env['QUERY_STRING']

		if path.startswith('/objects/'):
			name = path.split('/')[-1]
			if arg == 'streaming-on':
				if client not in self.clients: self.enable_streaming( client )
				self.clients[ client ]['objects'][ name ] = True
				a = '%s:%s' %(self.host, self.clients[client]['port'])
				return [ a.encode('utf-8') ]
			elif arg == 'streaming-off':
				self.clients[ client ]['objects'][ name ] = False
				return [ b'ok' ]
			else:
				return [ dump_collada(name) ]
		else: assert 0


	def pickle( self, o ):
		b = pickle.dumps( o, protocol=2 ) #protocol2 is python2 compatible
		#print( 'streaming bytes', len(b) )
		n = len( b ); d = STREAM_BUFFER_SIZE - n -4
		if n > STREAM_BUFFER_SIZE:
			print( 'ERROR: STREAM OVERFLOW:', n )
			return
		padding = b'#' * d
		if n < 10: header = '000%s' %n
		elif n < 100: header = '00%s' %n
		elif n < 1000: header = '0%s' %n
		else: header = '%s' %n
		header = bytes( header, 'utf-8' )
		assert len(header) == 4
		w = header + b + padding
		assert len(w) == STREAM_BUFFER_SIZE
		return w


	def pack( self, objects ):
		# 153 bytes per object + n bytes for animation names and weights
		i = 0; msg = []
		for ob in objects:
			if ob.type not in ('MESH','LAMP','SPEAKER'): continue
			loc, rot, scl = ob.matrix_world.decompose()
			loc = loc.to_tuple()
			x,y,z = rot.to_euler(); rot = (x,y,z)
			scl = scl.to_tuple()

			d = {
				NAME : ob.name,
				POSITION : loc,
				ROTATION : rot,
				SCALE : scl,
				TYPE : STREAM_PROTO[ob.type]
			}
			msg.append( d )

			if ob.type == 'MESH': pass
			elif ob.type == 'LAMP':
				d[ ENERGY ] = ob.data.energy
				d[ DISTANCE ] = ob.data.distance
			elif ob.type == 'SPEAKER':
				d[ VOLUME ] = ob.data.volume
				d[ MUTE ] = ob.data.muted

			if i >= 10: break	# max is 13 objects to stay under 2048 bytes
		return msg


	def update(self, context):
		## first do http ##
		self.httpd.handle_request()
		self.write_streams()

	def write_streams(self):	# to clients (peers)
		for client in self.clients:
			sock = self.clients[client]['socket']
			poll = select.select( [], [sock], [], 0.01 )
			if not poll[1]: continue
			obs = [ bpy.data.objects[n] for n in self.clients[client]['objects'] ]
			bin = self.pickle( self.pack(obs) )
			try: sock.sendall( bin )
			except:
				print('SERVER: send data error')





class Client( object ):
	SERVERS = {}
	def __init__(self):
		self.servers = Client.SERVERS

	def update(self, context):	# from servers (peers)
		for host in self.servers:
			sock = self.servers[host]['socket']
			poll = select.select( [ sock ], [], [], 0.01 )
			if not poll[0]: continue

			data = sock.recv( STREAM_BUFFER_SIZE )
			assert len(data) == STREAM_BUFFER_SIZE
			if not data:
				print( 'server crashed?' )
				continue

			header = data[ : 4]
			s = data[ 4 : int(header)+4 ]
			objects = pickle.loads( s )
			self.clientside_sync( objects )


	def clientside_sync( self, objects ):
		for pak in objects:
			name = pak[ NAME ]
			ob = bpy.data.objects[ name ]
			ob.location = pak[ POSITION ]
			ob.rotation_euler = pak[ ROTATION ]
			ob.scale = pak[ SCALE ]

			if ob.type=='LAMP':
				ob.data.energy = pak[ ENERGY ]
				ob.data.distance = pak[ DISTANCE ]

	@classmethod
	def enable_streaming_clientside( self, host ):
		print('enabling streaming clientside', host)
		name,port = host.split(':')
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.bind( (name, int(port)) )	# bind is connect as client
		self.SERVERS[ host ] = {
			'socket':sock,
			'objects':{},
		}

	@classmethod
	def toggle_remote_sync(self, ob, con):
		url = get_object_url( ob )
		if ob.use_remote_sync:
			ob.lock_location = [True]*3
			ob.lock_scale = [True]*3
			ob.lock_rotation = [True]*3
			url += '?streaming-on'
			f = urllib.request.urlopen( url )
			host = f.read().decode()
			if host not in self.SERVERS: self.enable_streaming_clientside( host )
			name,port = host.split(':')
			self.SERVERS[ host ]['objects'][ob.name] = True
		else:
			ob.lock_location = [False]*3
			ob.lock_scale = [False]*3
			ob.lock_rotation = [False]*3
			url += '?streaming-off'
			f = urllib.request.urlopen( url )
			data = f.read()


bpy.types.Object.use_remote_sync = BoolProperty(
	name='enable live connect', 
	description='enables automatic sync', 
	default=False,
	update=lambda a,b: Client.toggle_remote_sync(a,b)
)

bpy.types.Object.use_remote = BoolProperty( name='enable remote object', description='enables remote object', default=False)

bpy.types.Object.remote_path = StringProperty( name='remote path', description='remote path (optional)', maxlen=128, default='' )

bpy.types.Object.remote_server = StringProperty( name='remote server', description='remote server', maxlen=64, default='localhost:8080' )

bpy.types.Object.remote_format = EnumProperty(
    items=[
            ('blend', 'blend', 'BLENDER'),
            ('collada', 'collada', 'COLLADA'),
    ],
    name='remote file format', 
    description='remote file format', 
    default='collada'
)

bpy.types.Object.remote_merge_type = EnumProperty(
    items=[
            ('object', 'object', 'OBJECT'),
            ('group', 'group', 'GROUP'),
    ],
    name='remote merge type', 
    description='remote merge type', 
    default='object'
)




##############################
class AudioThread(object):
	lock = threading._allocate_lock()		# not required

	def __init__(self):
		self.active = False
		self.output = al.OpenDevice()
		self.context = al.CreateContext( self.output )
		al.MakeContextCurrent( self.context )
		self.microphone = Microphone( analysis=True, streaming=False )
		self.synth = SynthMachine()
		self.synth.setup()

	def update(self):		# called from main #
		if self.active: self.microphone.sync()

	def loop(self):
		while self.active:
			self.microphone.update()
			self.synth.update()
			time.sleep(0.05)
		print('..audio thread finished..')

	def start(self):
		self.active = True
		threading._start_new_thread(self.loop, ())
		#threading._start_new_thread(Speaker.thread, ())


	def exit(self):
		print('audio thread exit')
		self.active = False
		self.synth.active = False
		self.microphone.close()

		#ctx=al.GetCurrentContext()
		#dev = al.GetContextsDevice(ctx)
		al.DestroyContext( self.context )
		if self.output: al.CloseDevice( self.output )



##############################
class Speaker(object):
	#Speakers = []
	#@classmethod
	#def thread(self):
	#	while True:
	#		AudioThread.lock.acquire()
	#		for speaker in self.Speakers:
	#			speaker.update()
	#		AudioThread.lock.release()
	#		time.sleep(0.1)

	def __init__(self, frequency=22050, stereo=False, streaming=False):
		#Speaker.Speakers.append( self )
		if stereo: self.format=al.AL_FORMAT_STEREO16
		else: self.format=al.AL_FORMAT_MONO16
		self.frequency = frequency
		self.streaming = streaming
		self.buffersize = 1024
		self.playing = False

		array = (ctypes.c_uint * 1)()
		al.GenSources( 1, array )
		assert al.GetError() == al.AL_NO_ERROR
		self.id = array[0]

		self.output_buffer_index = 0
		self.output_buffer_ids = None
		self.num_output_buffers = 16
		self.trash = []
		self.generate_buffers()

		self.gain = 1.0
		self.pitch = 1.0

	def cache_samples(self, samples):
		assert self.streaming == False
		self.generate_buffers()
		bid = self.output_buffer_ids[0]
		n = len(samples)
		data = (ctypes.c_byte*n)( *samples )
		ptr = ctypes.pointer( data )
		al.BufferData(
			bid,
			self.format, 
			ptr, 
			n, # size in bytes
			self.frequency,
		)
		al.Sourcei( self.id, al.AL_BUFFER, bid )


	def get_widget(self):
		root = gtk.HBox()
		bx = gtk.VBox(); root.pack_start( bx )
		slider = SimpleSlider( self, name='gain', driveable=True )
		bx.pack_start( slider.widget, expand=False )
		slider = SimpleSlider( self, name='pitch', driveable=True )
		bx.pack_start( slider.widget, expand=False )
		return root



	def generate_buffers(self):
		self.output_buffer_ids = (ctypes.c_uint * self.num_output_buffers)()
		al.GenBuffers( self.num_output_buffers, ctypes.pointer(self.output_buffer_ids) )
		assert al.GetError() == al.NO_ERROR


	def play(self, loop=False):
		self.playing = True
		al.SourcePlay( self.id )
		assert al.GetError() == al.NO_ERROR
		if loop: al.Sourcei( self.id, al.LOOPING, al.TRUE )

	def stop(self):
		al.SourceStop( self.id )
		assert al.GetError() == al.NO_ERROR


	def stream( self, array ):
		self.output_buffer_index += 1
		if self.output_buffer_index == self.num_output_buffers:
			self.output_buffer_index = 0
			self.generate_buffers()
		bid = self.output_buffer_ids[ self.output_buffer_index ]

		pointer = ctypes.pointer( array )
		bytes = len(array) * 2	# assume 16bit audio

		al.BufferData(
			bid,
			self.format, 
			pointer, 
			bytes,
			self.frequency,
		)
		assert al.GetError() == al.NO_ERROR

		al.SourceQueueBuffers( self.id, 1, ctypes.pointer(ctypes.c_uint(bid)) )
		assert al.GetError() == al.NO_ERROR

		self.trash.insert( 0, bid )

		ret = ctypes.pointer( ctypes.c_int(0) )
		al.GetSourcei( self.id, al.SOURCE_STATE, ret )
		if ret.contents.value != al.PLAYING:
			#AudioThread.lock.acquire()
			#print('RESTARTING PLAYBACK')
			self.play()
			#AudioThread.lock.release()

		self.update()

	def update(self):
		if not self.playing: return

		seconds = ctypes.pointer( ctypes.c_float(0.0) )
		al.GetSourcef( self.id, al.SEC_OFFSET, seconds )
		self.seconds = seconds.contents.value

		info = {}
		ret = ctypes.pointer( ctypes.c_int(0) )
		for tag in 'BYTE_OFFSET SOURCE_TYPE LOOPING BUFFER SOURCE_STATE BUFFERS_QUEUED BUFFERS_PROCESSED'.split():
			param = getattr(al, tag)
			al.GetSourcei( self.id, param, ret )
			info[tag] = ret.contents.value


		if self.streaming:
			#print( 'buffers processed', info['BUFFERS_PROCESSED'] )
			#print( 'buffers queued', info['BUFFERS_QUEUED'] )
			n = info['BUFFERS_PROCESSED']
			if n >= 1:
				#AudioThread.lock.acquire()
				ptr = (ctypes.c_uint * n)( *[self.trash.pop() for i in range(n)] )
				al.SourceUnqueueBuffers( self.id, n, ptr )
				assert al.GetError() == al.NO_ERROR
				al.DeleteBuffers( n, ptr )
				assert al.GetError() == al.NO_ERROR



############### Fluid Synth ############
class SynthChannel(object):
	def __init__(self, synth=None, index=0, sound_font=None, bank=0, patch=0 ):
		print('new synth channel', index, sound_font, bank, patch)
		self.synth = synth
		self.index = index
		self.sound_font = sound_font
		self.bank = bank
		self.patch = patch

		self.keys = [ 0.0 for i in range(128) ]				# driveable: 0.0-1.0
		self.previous_state = [ 0 for i in range(128) ]
		self.update_program()

	def update_program(self):
		self.synth.select_program( self.sound_font, self.index, self.bank, self.patch )

	def update(self):
		#if self.state == self.previous_state: return
		for i, value in enumerate(self.keys):
			v = int( value*127 )
			if v != self.previous_state[i]:
				self.previous_state[i] = v
				print('updating key state', i, v)
				if v: self.synth.note_on( self.index, i, v )
				else: self.synth.note_off( self.index, i )


	def next_patch( self ):
		self.patch += 1
		if self.patch > 127: self.patch = 127
		self.update_program()

	def previous_patch( self ):
		self.patch -= 1
		if self.patch < 0: self.patch = 0
		self.update_program()

	def cb_adjust_patch(self, adj):
		self.patch = int( adj.get_value() )
		self.update_program()

	def get_widget(self):
		root = gtk.HBox()

		frame = gtk.Frame('patch')
		root.pack_start( frame, expand=False )
		b = gtk.SpinButton(); frame.add( b )
		adj = b.get_adjustment()
		adj.configure( 
			value=self.patch, 
			lower=0, 
			upper=127, 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		adj.connect('value-changed', self.cb_adjust_patch)

		root.pack_start( gtk.Label() )

		keyboard = gtk.VBox(); keyboard.set_border_width(4)
		root.pack_start( keyboard, expand=False )
		row = gtk.HBox()
		keyboard.pack_start( row, expand=False )
		for i in range(20, 100):
			if i == 60:
				row = gtk.HBox()
				keyboard.pack_start( row, expand=False )
			b = ToggleButton('')
			b.connect( self, path='keys', index=i, cast=float )
			row.pack_start( b.widget, expand=False )

		#root.pack_start( gtk.Label() )

		root.pack_start( self.synth.speaker.get_widget(), expand=True )

		return root

	def toggle_key( self, button, index ):
		if button.get_active(): self.keys[ index ] = 1.0
		else: self.keys[ index ] = 0.0


class Synth( object ):
	Vibrato = 1
	Volume = 7
	Pan = 10
	Expression = 11
	Sustain = 64
	Reverb = 91
	Chorus = 93

	def __init__(self, gain=0.5, frequency=22050):
		self.gain = gain
		self.frequency = frequency
		self.settings = fluid.new_fluid_settings()
		fluid.settings_setnum( self.settings, 'synth.gain', gain )
		fluid.settings_setnum( self.settings, 'synth.sample-rate', frequency )
		self.sound_fonts = {}
		self.synth = fluid.new_fluid_synth( self.settings )

		self.samples = 1024
		self.buffer = (ctypes.c_int16 * self.samples)()
		self.buffer_ptr = ctypes.pointer( self.buffer )


	def get_stereo_samples( self ):
		fluid.synth_write_s16( 
			self.synth,
			self.samples,
			self.buffer_ptr, 0, 1,
			self.buffer_ptr, 1, 1,
		)
		return self.buffer

	def get_mono_samples( self ):
		fluid.synth_write_s16( 
			self.synth,
			self.samples,
			self.buffer_ptr, 0, 1,
			self.buffer_ptr, 0, 1,
		)
		return self.buffer


	def open_sound_font(self, url, update_midi_preset=0):
		id = fluid.synth_sfload( self.synth, url, update_midi_preset)
		assert id != -1
		self.sound_fonts[ os.path.split(url)[-1] ] = id
		return id

	def select_program( self, id, channel=0, bank=0, preset=0 ):
		fluid.synth_program_select( self.synth, channel, id, bank, preset )

	def note_on( self, chan, key, vel=127 ):
		if vel > 127: vel = 127
		elif vel < 0: vel = 0
		fluid.synth_noteon( self.synth, chan, key, vel )

	def note_off( self, chan, key ):
		fluid.synth_noteoff( self.synth, chan, key )

	def pitch_bend(self, chan, value):
		assert value >= -1.0 and value <= 1.0
		fluid.synth_pitch_bend( self.synth, chan, int(value*8192))

	def control_change( self, chan, ctrl, value ):
		"""Send control change value
		The controls that are recognized are dependent on the
		SoundFont.  Values are always 0 to 127.  Typical controls
		include:
		1 : vibrato
		7 : volume
		10 : pan (left to right)
		11 : expression (soft to loud)
		64 : sustain
		91 : reverb
		93 : chorus
		""" 
		fluid.synth_cc(self.synth, chan, ctrl, value)

	def change_program( self, chan, prog ):
		fluid.synth_program_change(self.synth, chan, prog )

	def select_bank( self, chan, bank ):
		fluid.synth_bank_select( self.synth, chan, bank )

	def select_sound_font( self, chan, name ):
		id = self.sound_fonts[ name ]
		fluid.synth_sfont_select( self.synth, chan, id )

	def reset(self):
		fluid.synth_program_reset( self.synth )

######################
class SynthMachine( Synth ):
	def setup(self):
		self.active = True
		url = os.path.join( SCRIPT_DIR, 'SoundFonts/Vintage Dreams Waves v2.sf2' )
		self.sound_font = self.open_sound_font( url )
		self.speaker = Speaker( frequency=self.frequency, streaming=True )
		self.channels = []
		for i in range(4):
			s = SynthChannel(synth=self, index=i, sound_font=self.sound_font, patch=i)
			self.channels.append( s )

	def update(self):
		if not self.active: return
		for chan in self.channels: chan.update()
		buff = self.get_mono_samples()
		speaker = self.speaker
		speaker.stream( buff )
		if not speaker.playing:
			speaker.play()





###########################################

class Audio(object):
	def __init__(self, analysis=False, streaming=True):
		self.active = True

		self.analysis = analysis
		self.streaming = streaming
		self.speakers = []
		self.buffersize = 1024
		self.input = None
		self.input_buffer = (ctypes.c_int16 * self.buffersize)()
		#self.input_buffer_ptr = ctypes.pointer( self.input_buffer )
		self.fftw_buffer_type = ( ctypes.c_double * 2 * self.buffersize )

		self.band_chunk = 32
		n = int( (self.buffersize / 2) / self.band_chunk )

		self.raw_bands = [ .0 for i in range(n) ]		# drivers fails if pointer is lost
		self.norm_bands = [ .0 for i in range(n) ]
		self.bands = [ .0 for i in range(n) ]

		self.beats_buffer_samples = 128
		self.beats_buffer = [ [0.0]*self.beats_buffer_samples for i in range(n) ]
		self.beats = [ False for i in range(n) ]
		self.beats_buttons = []
		self.beats_threshold = 2.0

		#self.max_raw = 0.1
		self.normalize = 1.0

		self.raw_adjustments = [ gtk.Adjustment( value=0, lower=0, upper=1 ) for i in range(n) ]
		self.norm_adjustments = [ gtk.Adjustment( value=0, lower=0, upper=1 ) for i in range(n) ]
		self.adjustments = [ gtk.Adjustment( value=0, lower=0, upper=1 ) for i in range(n) ]

		self.index = 0

	def get_analysis_widget(self):
		root = gtk.VBox()
		root.set_border_width(2)

		slider = SimpleSlider( self, name='normalize', value=self.normalize, min=0.5, max=5 )
		root.pack_start( slider.widget, expand=False )

		slider = SimpleSlider( self, name='beats_threshold', value=self.beats_threshold, min=0.5, max=5 )
		root.pack_start( slider.widget, expand=False )

		ex = gtk.Expander('raw bands')
		root.pack_start( ex, expand=False )
		box = gtk.VBox()
		sw = gtk.ScrolledWindow()
		sw.add_with_viewport( box )
		ex.add( sw )
		sw.set_size_request( 240,280 )

		for i, adjust in enumerate(self.raw_adjustments):
			row = gtk.HBox(); row.set_border_width(4)
			box.pack_start( row, expand=False )

			a = gtk.EventBox()
			title = '%s%s.band%s' %('raw',self.index,i)
			output = DeviceOutput( title, source=self.raw_bands, index=i )
			DND.make_source( a, output )

			a.add( gtk.Label(icons.DND) )
			row.pack_start( a, expand=False )

			scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
			scale.set_digits(3)
			row.pack_start( scale )

			a = gtk.EventBox()
			title = 'beat%s.button%s' %(self.index,i)
			b = gtk.ToggleButton('%s'%i)
			self.beats_buttons.append( b )
			output = DeviceOutput( title, source=self.beats, index=i )
			DND.make_source( b, output )
			a.add( b )
			row.pack_start( a, expand=False )


		ex = gtk.Expander('normalized bands')
		root.pack_start( ex, expand=False )
		box = gtk.VBox()
		sw = gtk.ScrolledWindow()
		sw.add_with_viewport( box )
		ex.add( sw )
		sw.set_size_request( 240,280 )

		for i, adjust in enumerate(self.norm_adjustments):
			row = gtk.HBox(); row.set_border_width(4)
			box.pack_start( row, expand=False )

			a = gtk.EventBox()
			title = '%s%s.band%s' %('norm',self.index,i)
			output = DeviceOutput( title, source=self.norm_bands, index=i )
			DND.make_source( a, output )

			a.add( gtk.Label(icons.DND) )
			row.pack_start( a, expand=False )

			scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
			scale.set_digits(3)
			row.pack_start( scale )

		return root

	def update(self):	# called from thread
		#for speaker in self.speakers: speaker.update()

		if self.analysis:
			complex = ctypes.c_double*2
			inbuff = self.fftw_buffer_type( *[complex(v,.0) for v in self.input_buffer] )
			outbuff = self.fftw_buffer_type()
			plan = fftw.plan_dft_1d( self.buffersize, inbuff, outbuff, fftw.FORWARD, fftw.ESTIMATE )
			fftw.execute( plan )

			real   = outbuff[ 0 ][0]
			imag = outbuff[ 0 ][1]
			self.power = math.sqrt( (real**2)+(imag**2) )

			raw = []
			bar = []
			for i in range( int(self.buffersize/2) ):
				real   = outbuff[ i+1 ][0]
				imag = outbuff[ i+1 ][1]
				power = math.sqrt( (real**2)+(imag**2) )
				bar.append( power )
				if len(bar) == self.band_chunk:
					raw.append( sum(bar) / float(self.band_chunk) )
					bar = []


			#h = max(raw)
			#if h > self.max_raw: self.max_raw = h; print('new max raw', h)
			#mult = 1.0 / self.max_raw
			#if self.max_raw > 1.0: self.max_raw *= 0.99	# TODO better normalizer
			mult = 1.0 / (self.normalize * 100000)		# values range from 200,000 to 2M

			for i,power in enumerate( raw ):
				power *= mult
				self.raw_bands[ i ] = power
				self.beats_buffer[ i ].insert( 0, power )
				self.beats_buffer[ i ].pop()
				avg = sum( self.beats_buffer[i] ) / float( self.beats_buffer_samples )
				#print('pow',power,'avg',avg)
				if power > avg * self.beats_threshold:
					self.beats[ i ] = True
				else:
					self.beats[ i ] = False

			high = max( self.raw_bands )
			mult = 1.0
			if high: mult /= high
			#self.norm_bands = [ power*mult for power in plot ]	# breaks drivers
			for i,power in enumerate(self.raw_bands):
				self.norm_bands[ i ] = power * mult



	def sync(self):	# called from main - (gtk not thread safe)
		if not self.active: return

		for i,power in enumerate( self.raw_bands ):
			self.raw_adjustments[ i ].set_value( power )
		for i,power in enumerate( self.norm_bands ):
			self.norm_adjustments[ i ].set_value( power )
		for i,beat in enumerate( self.beats ):
			self.beats_buttons[ i ].set_active( beat )


class Microphone( Audio ):
	def update(self):	# called from thread
		if not self.input: return
		ready = ctypes.pointer(ctypes.c_int())
		al.alcGetIntegerv( self.input, al.ALC_CAPTURE_SAMPLES, 1, ready )
		#print( ready.contents.value )
		if ready.contents.value >= self.buffersize:
			al.CaptureSamples(
				self.input,
				ctypes.pointer(self.input_buffer),
				self.buffersize
			)
			if self.streaming:
				for speaker in self.speakers:
					speaker.stream( self.input_buffer )
					if not speaker.playing:
						speaker.play()
		Audio.update( self )

	def start_capture( self, frequency=22050 ):
		print('starting capture...')
		self.active = True
		self.frequency = frequency
		self.format=al.AL_FORMAT_MONO16
		self.input = al.CaptureOpenDevice( None, self.frequency, self.format, self.buffersize*2 )
		assert al.GetError() == al.AL_NO_ERROR
		al.CaptureStart( self.input )
		assert al.GetError() == al.AL_NO_ERROR
		if not self.speakers:
			s = Speaker( frequency=self.frequency, streaming=True )
			self.speakers.append( s )

	def stop_capture( self ):
		al.CaptureStop( self.input )
		self.input = None
		self.active = False

	def close(self):
		self.active = False
		if self.input:
			al.CaptureStop( self.input )
			al.CloseDevice( self.input )
			self.input = None


	def toggle_capture(self,button):
		if button.get_active(): self.start_capture()
		else: self.stop_capture()

	def get_widget(self):
		frame = gtk.Frame()
		root = gtk.HBox(); frame.add( root )

		b = gtk.ToggleButton( 'microphone' ); b.set_relief( gtk.RELIEF_NONE )
		b.set_tooltip_text( 'toggle microphone input' )
		b.connect('toggled', self.toggle_capture)
		root.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.FFT ); b.set_relief( gtk.RELIEF_NONE )
		b.set_tooltip_text( 'toggle spectral analysis' )
		b.set_active( self.analysis )
		b.connect('toggled', lambda b,s: setattr(s,'analysis',b.get_active()), self)
		root.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.SPEAKER ); b.set_relief( gtk.RELIEF_NONE )
		b.set_tooltip_text( 'toggle speaker output' )
		b.set_active( self.streaming )
		b.connect('toggled', lambda b,s: setattr(s,'streaming',b.get_active()), self)
		root.pack_start( b, expand=False )

		return frame



##############################
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



class Popup( ToolWindow ):
	def __init__(self):
		self.modal = gtk.Frame()
		ToolWindow.__init__(self, x=200, y=140, width=320, height=220, child=self.modal)
		win = self.window
		win.connect('destroy', self.hide )
		win.set_deletable(False)


	def hide(self,win):
		print('HIDE')
		win.hide()



	def refresh(self): self.object = None	# force reload



	def update(self, context):
		if context.active_object and context.active_object.name != self.object:
			print('UPDATING POPUP...')
			ob = context.active_object

			self.object = ob.name
			self.window.set_title( ob.name )
			self.window.remove( self.modal )
			#self.modal.destroy()

			self.modal = note = gtk.Notebook()
			self.window.add( self.modal )
			note.set_tab_pos( gtk.POS_LEFT )

			########## moved to left tools #########

			self.modal.show_all()


	def cb_drop_joint(self, wid, context, x, y, time, page):
		wrap = DND.source_object
		widget = wrap.attach( self.object )
		if widget:
			page.pack_start( widget, expand=False )
			widget.show_all()



	def toggle_popup( self, button ):
		if button.get_active(): self.window.show_all()
		else: self.window.hide()


#####################################################

class Target(object):
	'''
	target to object,
	driven by axis or button
		if by axis:
			button is optional
			drop secondary axis controls extra local force axis
		if by button - force is constant

	on contact, if over thresh:
		"hold" - drop button
		"sound" - drop audio

	can boolean mod be used to inflict damage?
		on contact, if over thresh:
			create cutting object at place of impact,
			parent cutting object to target (or bone in armature)
			create boolean mod on target, set cutting

	'''
	def __init__(self,ob, weight=0.0, x=1.0, y=1.0, z=1.0):
		self.name = ob.name				# could change target on the fly by scripting
		if ob.type=='ARMATURE': pass		# could target nearest rule
		self.weight = weight
		self.driver = None
		self.xmult = x
		self.ymult = y
		self.zmult = z

	def get_widget(self):
		ex = gtk.Expander( 'Target: %s' %self.name )
		DND.make_destination( ex )
		ex.connect( 'drag-drop', self.cb_drop_target_driver )
		if self.driver:
			widget = self.driver.get_widget( expander=False )
			self.modal = widget
			ex.add( widget )
		else:
			slider = SimpleSlider( self, name='weight', value=self.weight, min=.0, max=100 )
			self.modal = slider.widget
			ex.add( slider.widget )

		return ex

	def cb_drop_target_driver(self, ex, context, x, y, time):
		ex.set_expanded(True)
		ex.remove( self.modal )

		output = DND.source_object
		self.driver = driver = output.bind( 'TARGET', target=self, path='weight', mode='=' )
		widget = driver.get_widget( expander=False )
		ex.add( widget )
		widget.show_all()

	def update(self, projectiles):
		target = bpy.data.objects[ self.name ]
		vec = target.matrix_world.to_translation()
		m = self.weight
		for p in projectiles:
			x,y,z = vec - p.matrix_world.to_translation()	# if not normalized reaches target and stays there, but too much force when far
			#x,y,z = (vec - p.matrix_world.to_translation()).normalize() # if normalized overshoots target
			w = ENGINE.get_wrapper(p)
			w.body.AddForce( 
				x*m*self.xmult, 
				y*m*self.ymult, 
				z*m*self.zmult, 
			)


class Bone(object):
	'''
	contains at least two physics bodies: shaft and tail
	head is optional
	'''
	def get_location(self):
		return self.shaft.matrix_world.to_translation()
	def hide(self):
		for ob in (self.head, self.shaft, self.tail):
			if ob: ob.hide = True
	def show(self):
		for ob in (self.head, self.shaft, self.tail):
			if ob: ob.hide = False
	def get_objects(self):
		r = []
		for ob in (self.head, self.shaft, self.tail):
			if ob: r.append( ob )
		return r
	def get_wrapper_objects(self):
		r = []
		for ob in (self.head, self.shaft, self.tail):
			if ob: r.append( ENGINE.get_wrapper(ob) )
		return r

	def add_force( self, x,y,z ):
		for ob in self.get_objects():
			w = ENGINE.get_wrapper( ob )
			w.body.AddForce( x,y,z )
	def add_local_force( self, x,y,z ):
		for ob in self.get_objects():
			w = ENGINE.get_wrapper( ob )
			w.body.AddRelForce( x,y,z )
	def add_local_torque( self, x,y,z ):
		for ob in self.get_objects():
			w = ENGINE.get_wrapper( ob )
			w.body.AddRelTorque( x,y,z )

	def get_velocity_local( self ):
		w = ENGINE.get_wrapper( self.shaft )
		return w.get_linear_vel()
	def get_angular_velocity_local( self ):	# TODO what space is this?
		w = ENGINE.get_wrapper( self.shaft )
		return w.get_angular_vel()


	def __init__(self, arm, name, stretch=False):
		self.armature = arm
		self.name = name
		self.head = None
		self.shaft = None
		self.tail = None
		self.stretch = stretch
		self.breakable_joints = []

		ebone = arm.data.bones[ name ]
		pbone = arm.pose.bones[ name ]
		if pbone.parent:
			self.parent_name = pbone.parent.name
		else:
			self.parent_name = None


		if not ebone.parent or not ebone.use_connect:
			self.head = bpy.data.objects.new(name='HEAD.'+name,object_data=None)
			Pyppet.context.scene.objects.link( self.head )
			self.head.matrix_world = pbone.matrix.copy()
			#head.empty_draw_type = 'SPHERE'
			self.head.empty_draw_size = ebone.head_radius * 2.0


		################ body #################
		self.shaft = bpy.data.objects.new( name=name, object_data=None )
		self.shaft.empty_draw_type = 'CUBE'
		self.shaft.hide_select = True
		Pyppet.context.scene.objects.link(self.shaft)
		m = pbone.matrix.copy()
		delta = pbone.tail - pbone.head
		delta *= 0.5
		length = delta.length
		x,y,z = pbone.head + delta	# the midpoint
		m[3][0] = x
		m[3][1] = y
		m[3][2] = z
		self.rest_height = z				# used by biped solver
		avg = (ebone.head_radius + ebone.tail_radius) / 2.0
		self.shaft.matrix_world = m
		self.shaft.scale = (avg, length*0.6, avg)	# set scale in local space
		Pyppet.context.scene.update()			# syncs .matrix_world with local-space set scale
		self.shaft.ode_use_collision = True		# needs matrix_world to be in sync before this is set

		################ pole-target (up-vector) ##############
		self.pole = bpy.data.objects.new( name='POLE.'+name, object_data=None )
		#self.pole.empty_draw_type = 'CUBE'
		#self.pole.hide_select = True
		Pyppet.context.scene.objects.link(self.pole)
		self.pole.location.z = -10.0
		self.pole.parent = self.shaft


		################# tail ###############
		self.tail = bpy.data.objects.new(name='TAIL.'+name,object_data=None)
		#self.tail.show_x_ray = True
		Pyppet.context.scene.objects.link( self.tail )
		self.tail.empty_draw_type = 'SPHERE'
		self.tail.empty_draw_size = ebone.tail_radius * 1.75
		m = pbone.matrix.copy()
		x,y,z = pbone.tail
		m[3][0] = x
		m[3][1] = y
		m[3][2] = z
		self.tail.matrix_world = m

		#### make ODE bodies ####
		if self.head: self.head.ode_use_body = True
		if self.shaft: self.shaft.ode_use_body = True
		if self.tail: self.tail.ode_use_body = True



		## bind tail to body ##
		parent = ENGINE.get_wrapper( self.shaft )
		child = ENGINE.get_wrapper( self.tail )
		joint = child.new_joint(
			parent, 
			name='FIXED2TAIL.'+parent.name,
			type='fixed'
		)
		#self.primary_joints[ ebone.name ] = {'body':joint}


		if stretch:
			cns = pbone.constraints.new('STRETCH_TO')
			cns.target = self.tail
			#cns.bulge = 1.5

		else:
			self.ik = cns = pbone.constraints.new('IK')
			cns.target = self.tail
			cns.chain_count = 1
			#cns.use_stretch = stretch
			#cns.pole_target = self.pole		# creates invalid state - blender bug?

		if 0:
			#cns = pbone.constraints.new('LOCKED_TRACK')
			#cns.target = self.pole
			#cns.track_axis = 'TRACK_Z'
			#cns.lock_axis = 'LOCK_Y'
			cns = pbone.constraints.new('TRACK_TO')
			cns.target = self.pole
			cns.track_axis = 'TRACK_Y'
			cns.up_axis = 'UP_Z'


		if self.head:
			cns = pbone.constraints.new('COPY_LOCATION')
			cns.target = self.head

			## bind body to head ##
			parent = ENGINE.get_wrapper( self.head )
			child = ENGINE.get_wrapper( self.shaft )
			joint = child.new_joint(
				parent, 
				name='ROOT.'+parent.name,
				type='ball'
			)
			#self.primary_joints[ ebone.name ]['head'] = joint

		if self.armature.parent:
			for ob in self.get_objects():
				if not ob.parent:
					ob.parent = self.armature.parent


	def set_parent( self, parent ):
		parent = ENGINE.get_wrapper( parent.tail )

		## bind body to tail of parent ##
		child = ENGINE.get_wrapper( self.shaft )
		subjoint = child.new_joint( parent, name='FIXED2PT.'+parent.name, type='fixed' )

		if self.head:	# if head, bind head to tail of parent #
			child = ENGINE.get_wrapper( self.head )
			joint = child.new_joint( parent, name='H2PT.'+parent.name, type='fixed' )
			self.breakable_joints.append( joint )
			joint.slaves.append( subjoint )


	def set_weakness( self, break_thresh, damage_thresh ):
		if break_thresh:
			for joint in self.breakable_joints:
				joint.breaking_threshold = break_thresh
				joint.damage_threshold = damage_thresh


class AbstractArmature(object):
	def reset(self): pass	# for overloading
	def get_widget_label(self): return gtk.Label( self.ICON )	# can be overloaded, label may need to be a drop target

	def __init__(self,name):
		self.name = name
		self.rig = {}
		self.active_pose_bone = None
		self.targets = {}		# bone name : [ Targets ]
		self.created = False
		self._targets_widget = None

	def get_create_widget(self):
		root = gtk.VBox()
		row = gtk.HBox(); root.pack_start( row, expand=False )

		stretch  = gtk.CheckButton('stretch-to constraints')
		breakable = gtk.CheckButton('breakable joints')
		break_thresh = SimpleSlider( name='breaking threshold', value=200, min=0.01, max=420 )
		damage_thresh = SimpleSlider( name='damage threshold', value=150, min=0.01, max=420 )

		b = gtk.Button('create')
		row.pack_start( b, expand=False )
		b.connect(
			'clicked',
			lambda button, _self, s, b, bt, dt: _self.create( s.get_active(), b.get_active(), bt.get_value(), dt.get_value() ), 
			self,
			stretch, breakable, 
			break_thresh.adjustment,
			damage_thresh.adjustment,
		)

		root.pack_start( stretch, expand=False )
		root.pack_start( breakable, expand=False )
		root.pack_start( break_thresh.widget, expand=False )
		root.pack_start( damage_thresh.widget, expand=False )
		return root


	def create( self, stretch=False, breakable=False, break_thresh=None, damage_thresh=None):
		self.created = True
		arm = bpy.data.objects[ self.name ]
		arm.pyppet_model = self.__class__.__name__		# pyRNA
		Pyppet.AddEntity( self )
		Pyppet.popup.refresh()

		#self.primary_joints = {}
		#self.breakable_joints = []
		self.initial_break_thresh = break_thresh
		self.initial_damage_thresh = damage_thresh

		## TODO armature offset
		parent_matrix = arm.matrix_world.copy()
		imatrix = parent_matrix.inverted()

		if breakable:
			print('making breakable',arm)
			bpy.context.scene.objects.active = arm        # arm needs to be in edit mode to get to .edit_bones
			bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
			bpy.ops.object.mode_set(mode='EDIT', toggle=False)
			for bone in arm.data.edit_bones:
				bone.use_connect = False
				#bone.parent = None
			bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

		if stretch:
			for bone in arm.data.bones:
				bone.use_inherit_rotation = False
				bone.use_inherit_scale = False


		for name in arm.pose.bones.keys():
			self.rig[ name ] = Bone(arm,name, stretch=stretch)


		## bind body to tail of parent ##
		for name in self.rig:
			child = self.rig[name]

			child.ik.pole_target = child.pole	# blender bug?
			child.ik.pole_angle = math.radians( -90 )

			if child.parent_name:
				parent = self.rig[ child.parent_name ]
				child.set_parent( parent )

		## update weakness ##
		if break_thresh:
			for b in self.rig.values():
				b.set_weakness( break_thresh, damage_thresh )

		self.setup()

	def setup(self): pass	# override


	def update(self, context ):
		for bname in self.targets:
			for target in self.targets[bname]:
				#target.driver.update()	# DriverManager.update takes care of this
				target.update( self.rig[ bname ].get_objects() )
		for B in self.rig.values():
			for joint in B.breakable_joints:
				if joint.broken: continue
				stress = joint.get_stress()
				if stress > joint.breaking_threshold:
					joint.break_joint()
					print('-----breaking joint stress', stress)
				if stress > joint.damage_threshold:
					joint.damage(0.5)
					print('-----damage joint stress', stress)

	def create_target( self, name, ob, weight=1.0, x=1.0, y=1.0, z=1.0 ):
		target = Target( ob, weight=weight, x=x, y=y, z=z )
		if name not in self.targets: self.targets[ name ] = []
		self.targets[ name ].append( target )
		return target

	def cb_drop_target(self, wid, context, x, y, time):
		if not self.active_pose_bone: return

		wrap = DND.source_object
		target = Target( wrap )
		if self.active_pose_bone not in self.targets: self.targets[ self.active_pose_bone ] = []
		self.targets[ self.active_pose_bone ].append( target )

		widget = target.get_widget()
		self._modal.pack_start( widget, expand=False )
		widget.show_all()


	def get_targets_widget(self, label):
		self._targets_widget = gtk.Frame('selected bone')
		self._modal = gtk.Label('targets')
		self._targets_widget.add( self._modal )
		DND.make_destination( label )
		label.connect( 'drag-drop', self.cb_drop_target )
		return self._targets_widget

	def update_targets_widget(self, bone):
		if not self._targets_widget: return
		self._targets_widget.set_label( bone.name )
		self._targets_widget.remove( self._modal )
		self._modal = root = gtk.VBox()
		self._targets_widget.add( root )
		root.set_border_width(6)
		if bone.name in self.targets:
			for target in self.targets[ bone.name ]:
				root.pack_start( target.get_widget(), expand=False )
		root.show_all()



	def update_ui( self, context ):
		if not context.active_pose_bone and self.active_pose_bone:
			self.active_pose_bone = None
			for B in self.rig.values(): B.show()

		elif context.active_pose_bone and context.active_pose_bone.name != self.active_pose_bone:
			bone = context.active_pose_bone
			self.active_pose_bone = bone.name	# get bone name, not bone instance

			for B in self.rig.values(): B.hide()
			self.rig[ bone.name ].show()

			self.update_targets_widget( bone )

	def heal_broken_joints(self,b):
		for B in self.rig.values():
			for joint in B.breakable_joints:
				if joint.broken: joint.restore()
	def get_widget(self):
		root = gtk.HBox()
		b = gtk.Button('heal joints')
		b.connect('clicked', self.heal_broken_joints)
		root.pack_start( b, expand=False )
		b = gtk.Button('reset transform')
		b.connect('clicked', self.save_transform)
		root.pack_start( b, expand=False )
		return root

	def save_transform(self, button):
		for B in self.rig.values():
			for w in B.get_wrapper_objects():
				w.save_transform()

class Rope( AbstractArmature ):
	ICON = icons.ROPE
	def GetRopeWidget(self):
		return self.get_widget()



class Ragdoll( AbstractArmature ):
	ICON = icons.RAGDOLL
	def GetRagdollWidget(self):
		if not self.created:
			return self.get_create_widget()
		else:
			return self.get_widget()




class Biped( AbstractArmature ):
	ICON = icons.BIPED
	def GetBipedWidget(self):
		if not self.created:
			return self.get_create_widget()


		sw = gtk.ScrolledWindow()
		sw.set_policy(True,True)
		root = gtk.VBox(); root.set_border_width( 6 )
		sw.add_with_viewport( root )

		widget = self.get_widget()
		root.pack_start( widget, expand=False )

		slider = SimpleSlider( self, name='primary_heading', min=-180, max=180, driveable=True )
		root.pack_start( slider.widget, expand=False )

		#slider = SimpleSlider( self, name='stance', min=-1, max=1, driveable=True )
		#root.pack_start( slider.widget, expand=False )

		slider = SimpleSlider( self, name='standing_height_threshold', min=.0, max=1.0 )
		root.pack_start( slider.widget, expand=False )

		ex = gtk.Expander( 'Standing' )
		root.pack_start( ex, expand=False )
		box = gtk.VBox(); ex.add( box )
		for tag in 'when_standing_foot_target_goal_weight when_standing_head_lift when_standing_foot_step_far_lift when_standing_foot_step_near_pull'.split():
			slider = SimpleSlider( self, name=tag, min=0, max=200 )
			box.pack_start( slider.widget, expand=False )

		ex = gtk.Expander( 'Falling' )
		root.pack_start( ex, expand=False )
		box = gtk.VBox(); ex.add( box )
		for tag in 'when_falling_and_hands_down_lift_head_by_tilt_factor when_falling_pull_hands_down_by_tilt_factor when_falling_head_curl when_falling_hand_target_goal_weight'.split():
			if tag=='when_falling_hand_target_goal_weight':
				slider = SimpleSlider( self, name=tag, min=0, max=200 )
			else:
				slider = SimpleSlider( self, name=tag, min=0, max=50 )
			box.pack_start( slider.widget, expand=False )

		return sw


	def reset(self):
		self.left_foot_loc = None
		self.right_foot_loc = None


	def setup(self):
		print('making biped...')

		self.solver_objects = []
		self.smooth_motion_rate = 0.0
		self.prev_heading = .0
		self.primary_heading = 0.0
		self.stance = 0.1

		self.head = None
		self.chest = None
		self.pelvis = None
		self.left_foot = self.right_foot = None
		self.left_toe = self.right_toe = None
		self.left_hand = self.right_hand = None
		self.foot_solver_targets = []
		self.hand_solver_targets = []
		self.left_foot_loc = None
		self.right_foot_loc = None

		############################## solver basic options ##############################
		self.standing_height_threshold = 0.75
		self.when_standing_foot_target_goal_weight = 100.0
		self.when_standing_head_lift = 100.0				# magic - only when foot touches ground lift head
		self.when_standing_foot_step_far_lift = 10			# if foot is far from target lift it up
		self.when_standing_foot_step_near_pull = 10		# if foot is near from target pull it down

		self.when_falling_and_hands_down_lift_head_by_tilt_factor = 4.0
		self.when_falling_pull_hands_down_by_tilt_factor = 10.0
		self.when_falling_head_curl = 10.0
		self.when_falling_hand_target_goal_weight = 100.0
		################################################################################

		for name in self.rig:
			if 'pelvis' in name or 'hip' in name or 'root' in name:
				self.pelvis = self.rig[ name ]

			elif 'head' in name or 'skull' in name:
				self.head = self.rig[ name ]

			elif 'foot' in name:
				B = self.rig[ name ]
				x,y,z = B.get_location()
				if x > 0: self.left_foot = B
				elif x < 0: self.right_foot = B

			elif 'toe' in name:
				B = self.rig[ name ]
				x,y,z = B.get_location()
				if x > 0: self.left_toe = B
				elif x < 0: self.right_toe = B

			elif 'hand' in name:
				B = self.rig[ name ]
				x,y,z = B.get_location()
				if x > 0: self.left_hand = B
				elif x < 0: self.right_hand = B

			elif 'chest' in name:
				self.chest = self.rig[ name ]

			else: continue

			self.solver_objects.append( self.rig[name] )

		assert self.head and self.chest and self.pelvis

		for o in self.solver_objects:
			o.biped_solver = {}


		ob = bpy.data.objects.new(name='PELVIS-SHADOW',object_data=None)
		self.pelvis.shadow = ob
		Pyppet.context.scene.objects.link( ob )
		ob.empty_draw_type = 'SINGLE_ARROW'
		ob.empty_draw_size = 2.0

		cns = ob.constraints.new('TRACK_TO')		# points on the Y
		cns.target = self.head.shaft
		cns.track_axis = 'TRACK_Z'
		cns.up_axis = 'UP_Y'
		cns.use_target_z = True

		## foot and hand solvers ##
		self.helper_setup_foot( self.left_foot, self.left_toe )
		self.helper_setup_foot( self.right_foot, self.right_toe, flip=True )

		self.helper_setup_hand( self.left_hand, self.left_foot )
		self.helper_setup_hand( self.right_hand, self.right_foot )


	def helper_setup_hand( self, hand, foot ):
		ob = bpy.data.objects.new(
			name='HAND-TARGET.%s'%hand.name,
			object_data=None
		)
		hand.biped_solver['swing-target'] = ob
		ob.empty_draw_type = 'CUBE'
		ob.empty_draw_size = 0.1
		Pyppet.context.scene.objects.link( ob )
		ob.parent = foot.biped_solver['target-parent']
		target = self.create_target( hand.name, ob, weight=30, z=-0.1 )
		self.hand_solver_targets.append( target )


	def helper_setup_foot( self, foot, toe=None, flip=False ):
		ob = bpy.data.objects.new(
			name='RING.%s'%foot.name,
			object_data=None
		)
		foot.shadow_parent = ob
		foot.biped_solver[ 'target-parent' ] = ob
		Pyppet.context.scene.objects.link( ob )
		cns = ob.constraints.new('TRACK_TO')		# points on the Y

		cns.target = self.pelvis.shadow

		if flip: cns.track_axis = 'TRACK_NEGATIVE_Z'
		else: cns.track_axis = 'TRACK_Z'
		cns.up_axis = 'UP_Y'
		cns.use_target_z = True


		ob = bpy.data.objects.new(
			name='FOOT-TARGET.%s'%foot.name,
			object_data=None
		)
		foot.shadow = ob
		foot.biped_solver[ 'target' ] = ob

		ob.empty_draw_type = 'SINGLE_ARROW'
		Pyppet.context.scene.objects.link( ob )
		ob.parent = foot.shadow_parent

		target = self.create_target( foot.name, ob, weight=30, z=.0 )
		self.foot_solver_targets.append( target )	# standing or falling modifies all foot targets
		foot.biped_solver[ 'TARGET' ] = target

		target = self.create_target( foot.name, self.pelvis.shaft, weight=0, z=.0 )	# pull feet to hip when fallen
		foot.biped_solver[ 'TARGET:pelvis' ] = target


		if toe:
			target = self.create_target( toe.name, ob, weight=30, z=.0 )
			self.foot_solver_targets.append( target )
			toe.biped_solver['TARGET'] = target


	def update(self, context):
		AbstractArmature.update(self,context)

		step_left = step_right = False

		if not self.left_foot_loc:
			self.left_foot_loc = self.left_foot.shadow_parent.location
			step_left = True
		if not self.right_foot_loc:
			self.right_foot_loc = self.right_foot.shadow_parent.location
			step_right = True

		x,y,z = self.chest.get_velocity_local()

		sideways = None
		sideways_rate = abs( x )
		if x < -2: sideways = 'RIGHT'
		elif x > 2: sideways = 'LEFT'

		moving = None
		#motion_rate = abs( y )
		delta = y - self.smooth_motion_rate
		self.smooth_motion_rate += delta*0.1
		motion_rate = abs( self.smooth_motion_rate )
		print('mrate', motion_rate)
		if self.smooth_motion_rate < -0.2: moving = 'FORWARD'
		elif self.smooth_motion_rate > 0.2: moving = 'BACKWARD'

		loc,rot,scl = self.pelvis.shadow.matrix_world.decompose()
		euler = rot.to_euler()
		tilt = sum( [abs(math.degrees(euler.x)), abs(math.degrees(euler.y))] ) / 2.0		# 0-45


		x,y,z = self.pelvis.get_location()
		current_pelvis_height = z
		falling = current_pelvis_height < self.pelvis.rest_height * (1.0-self.standing_height_threshold)

		hx,hy,hz = self.head.get_location()
		#x = (x+hx)/2.0
		#y = (y+hy)/2.0
		dx = hx - x
		dy = hy - y
		if moving == 'FORWARD':
			x += dx * 1.1
			y += dy * 1.1
		elif moving == 'BACKWARD':
			x += dx * 0.1
			y += dy * 0.1

		ob = self.pelvis.shadow
		ob.location = (x,y,-0.5)
		loc,rot,scale = ob.matrix_world.decompose()
		euler = rot.to_euler()

		heading = math.degrees( euler.z )
		spin = self.prev_heading - heading
		self.prev_heading = heading
		turning = None
		turning_rate =  abs(spin) #/ 360.0
		if abs(spin) < 300:	# ignore euler flip
			if spin < -1.0: turning = 'LEFT'
			elif spin > 1.0: turning = 'RIGHT'


		if turning == 'LEFT':
			if moving == 'BACKWARD':
				self.left_foot.shadow.location.x = -(motion_rate * 0.25)
				self.right_foot.shadow.location.x = -0.5

			elif moving == 'FORWARD':
				self.left_foot.shadow.location.x = 0.1
				self.right_foot.shadow.location.x = 0.2
				if motion_rate > 2:
					if random() > 0.8:
						step_right = True
						self.left_foot.shadow.location.x = -(motion_rate * 0.25)
					self.right_foot.shadow.location.x = motion_rate * 0.25

			if not step_right and random() > 0.2:
				if random() > 0.1: step_left = True
				else: step_right = True

		elif turning == 'RIGHT':
			if moving == 'BACKWARD':
				self.right_foot.shadow.location.x = -(motion_rate * 0.25)
				self.left_foot.shadow.location.x = -0.5

			elif moving == 'FORWARD':
				self.right_foot.shadow.location.x = 0.1
				self.left_foot.shadow.location.x = 0.2
				if motion_rate > 2:
					if random() > 0.8:
						step_left = True
						self.right_foot.shadow.location.x = -(motion_rate * 0.25)
					self.left_foot.shadow.location.x = motion_rate * 0.25

			if not step_left and random() > 0.2:
				if random() > 0.1: step_right = True
				else: step_left = True


		hand_swing_targets = []
		v = self.left_hand.biped_solver['swing-target'].location
		hand_swing_targets.append( v )
		v.x = -( self.left_foot.biped_solver['target'].location.x )

		v = self.right_hand.biped_solver['swing-target'].location
		hand_swing_targets.append( v )
		v.x = -( self.right_foot.biped_solver['target'].location.x )

		v = self.left_foot.biped_solver['target'].location
		if v.x < 0:		# if foot moving backward only pull on heel/foot
			self.left_toe.biped_solver['TARGET'].weight = 0.0
		elif v.x > 0:	# if foot moving forward only pull on toe
			self.left_foot.biped_solver['TARGET'].weight = 0.0

		v = self.right_foot.biped_solver['target'].location
		if v.x < 0:		# if foot moving backward only pull on heel/foot
			self.right_toe.biped_solver['TARGET'].weight = 0.0
		elif v.x > 0:	# if foot moving forward only pull on toe
			self.right_foot.biped_solver['TARGET'].weight = 0.0


		if moving == 'BACKWARD':	# hands forward if moving backwards
			for v in hand_swing_targets: v.x += 0.1

		if step_left:
			rad = euler.z - math.radians(90+self.primary_heading)
			cx = math.sin( -rad )
			cy = math.cos( -rad )
			v = self.left_foot.shadow_parent.location
			v.x = x+cx
			v.y = y+cy
			v.z = .0
			self.left_foot_loc = v
		if step_right:
			rad = euler.z + math.radians(90+self.primary_heading)
			cx = math.sin( -rad )
			cy = math.cos( -rad )
			v = self.right_foot.shadow_parent.location
			v.x = x+cx
			v.y = y+cy
			v.z = .0
			self.right_foot_loc = v


		#################### falling ####################
		if falling:

			if current_pelvis_height < 0.2:
				for foot in (self.left_foot, self.right_foot):
					target = foot.biped_solver[ 'TARGET:pelvis' ]
					if target.weight < 50: target.weight += 1.0

					foot.add_local_torque( -30, 0, 0 )

			else:
				for foot in (self.left_foot, self.right_foot):
					target = foot.biped_solver[ 'TARGET:pelvis' ]
					target.weight *= 0.9


			for target in self.foot_solver_targets:	# reduce foot step force
				target.weight *= 0.9

			#for target in self.hand_solver_targets:	# increase hand plant force
			#	if target.weight < self.when_falling_hand_target_goal_weight:
			#		target.weight += 1

			for hand in (self.left_hand, self.right_hand):
				self.head.add_local_torque( -self.when_falling_head_curl, 0, 0 )
				u = self.when_falling_pull_hands_down_by_tilt_factor * tilt
				hand.add_force( 0,0, -u )

				x,y,z = hand.get_location()
				if z < 0.1:
					self.head.add_force( 
						0,
						0, 
						tilt * self.when_falling_and_hands_down_lift_head_by_tilt_factor
					)
					hand.add_local_force( 0, -10, 0 )
				else:
					hand.add_local_force( 0, 3, 0 )

		else:	# standing

			for foot in (self.left_foot, self.right_foot):
				target = foot.biped_solver[ 'TARGET:pelvis' ]
				target.weight *= 0.9


			for target in self.foot_solver_targets:
				if target.weight < self.when_standing_foot_target_goal_weight:
					target.weight += 1

			#for target in self.hand_solver_targets:	# reduce hand plant force
			#	target.weight *= 0.9


			head_lift = self.when_standing_head_lift
			for toe in ( self.left_toe, self.right_toe ):
				x,y,z = toe.get_location()
				if z < 0.1:
					self.head.add_force( 0,0, head_lift*0.5 )

			## lift feet ##
			foot = self.left_foot
			v1 = foot.get_location().copy()
			if v1.z < 0.1: self.head.add_force( 0,0, head_lift*0.5 )

			v2 = self.left_foot_loc.copy()
			v1.z = .0; v2.z = .0
			dist = (v1 - v2).length
			if dist > 0.5:
				foot.add_force( 0, 0, self.when_standing_foot_step_far_lift)
			elif dist < 0.25:
				foot.add_force( 0, 0, -self.when_standing_foot_step_near_pull)

			foot = self.right_foot
			v1 = foot.get_location().copy()
			if v1.z < 0.1: self.head.add_force( 0,0, head_lift*0.5 )

			v2 = self.right_foot_loc.copy()
			v1.z = .0; v2.z = .0
			dist = (v1 - v2).length
			if dist > 0.5:
				foot.add_force( 0, 0, self.when_standing_foot_step_far_lift)
			elif dist < 0.25:
				foot.add_force( 0, 0, -self.when_standing_foot_step_near_pull)




##########################################################
bpy.types.Object.pyppet_model = bpy.props.StringProperty( name='pyppet model type', default='' )

class PyppetAPI( BlenderHackLinux ):
	'''
	Public API
	'''
	MODELS = ['Ragdoll', 'Biped', 'Rope']

	def GetRagdoll( self, arm ):
		if type(arm) is str: name = arm
		else: name = arm.name
		if name not in self.ragdolls: self.ragdolls[ name ] = Ragdoll( name )
		return self.ragdolls[ name ]

	def GetBiped( self, arm ):
		if type(arm) is str: name = arm
		else: name = arm.name
		if name not in self.bipeds: self.bipeds[ name ] = Biped( name )
		return self.bipeds[ name ]

	def GetRope( self, arm ):
		if type(arm) is str: name = arm
		else: name = arm.name
		if name not in self.ropes: self.ropes[ name ] = Rope( name )
		return self.ropes[ name ]

	def AddEntity( self, model ):
		self.entities[ model.name ] = model

	def reset_models(self):
		self.entities = {}
		self.ragdolls = {}
		self.bipeds = {}
		self.ropes = {}
	######################################
	def reset( self ):
		self.selected = None
		self.on_active_object_changed_callbacks = []
		self.reset_models()

	def register(self, func):
		self.on_active_object_changed_callbacks.append( func )


	def update_callbacks(self):
		if self.context.active_object and self.context.active_object.name != self.selected:
			self.selected = self.context.active_object.name
			ob = bpy.data.objects[ self.selected ]

			for func in self.on_active_object_changed_callbacks:
				func( ob )


	########### recording/baking ###########
	def start_record(self):
		self.recording = True
		self._rec_start_frame = self.context.scene.frame_current
		self._rec_start_time = time.time()
		self._rec_current_objects = []
		for ob in self.context.selected_objects:
			if ob.name in ENGINE.objects:
				print('record setup on object', ob.name)
				ob.animation_data_clear()
				self._rec_objects[ ob.name ] = buff = []
				w = ENGINE.objects[ ob.name ]
				w.reset_recording( buff )
				self._rec_current_objects.append( ob.name )

		self._rec_inactive_objects = []
		for name in self._rec_objects:
			if name not in self._rec_current_objects:
				self._rec_inactive_objects.append( name )

		if self.play_wave_on_record:
			self.start_wave()

	def end_record(self):
		self.recording = False
		if self.play_wave_on_record: self.stop_wave()
		for name in ENGINE.objects:
			w = ENGINE.objects[ name ]
			w.transform = None
			print('recbuffer:', name, len(w.recbuffer))



	def update_physics(self, now):
		ENGINE.sync( self.context, now, self.recording )
		models = self.entities.values()
		for mod in models:
			mod.update( self.context )


	def update_preview(self, now):
		print('updating preview',now)
		offset_cache = {}
		done = []

		for name in self._rec_objects:
			buff = self._rec_objects[name]
			print('updating %s: %s' %(name,len(buff)))
			for i,F in enumerate(buff):
				if F[0] < now: continue
				frame_time, pos, rot = F
				set_transform( 
					name, pos, rot, 
					set_body = (self.recording and name in self._rec_inactive_objects)
				)
				offset_cache[ name ] = i
				if i==len(buff)-1: done.append(True)
				else: done.append(False)
				break

		if all(done): self._rec_preview_button.set_active(False); return True
		else: return False

	def bake_animation(self,button):
		self.context.scene.frame_current = 1
		step = 1.0 / float(self.context.scene.render.fps)
		now = 0.0
		done = False
		while not done:
			self.context.scene.frame_current += 1
			done = self.update_preview( now )
			now += step
			bpy.ops.anim.keyframe_insert_menu( type='LocRot' )
		print('Finished baking animation')


def set_transform( name, pos, rot, set_body=False ):
	print('set-transform', name)
	ob = bpy.data.objects[name]
	q = mathutils.Quaternion()
	qw,qx,qy,qz = rot
	q.w = qw; q.x=qx; q.y=qy; q.z=qz
	m = q.to_matrix().to_4x4()
	x,y,z = pos
	m[0][3] = x; m[1][3] = y; m[2][3] = z
	x,y,z = ob.scale	# save scale
	ob.matrix_world = m
	ob.scale = (x,y,z)	# restore scale
	if set_body:
		w = ENGINE.objects[ name ]
		w.transform = (pos,rot)

######################################################

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



class PyppetUI( PyppetAPI ):
	def toggle_record( self, button ):
		if button.get_active(): self.start_record()
		else: self.end_record()
	def toggle_preview( self, button ):
		self.preview = button.get_active()
		if self.preview:
			self._rec_start_time = time.time()
			if self.play_wave_on_record: self.start_wave()
		else:
			if self.play_wave_on_record: self.stop_wave()


	def get_textures_widget(self):
		self._textures_widget_sw = sw = gtk.ScrolledWindow()
		self._textures_widget_container = frame = gtk.Frame()
		self._textures_widget_modal = root = gtk.VBox()
		sw.add_with_viewport( frame )
		sw.set_policy(True,False)
		frame.add( root )
		return sw

	def toggle_texture_slot(self,button, slot, opt, slider):
		setattr(slot, opt, button.get_active())
		if button.get_active(): slider.show()
		else: slider.hide()

	def load_texture(self,url, texture):
		print(url)
		if texture.type != 'IMAGE': texture.type = 'IMAGE'
		if not texture.image:
			texture.image = bpy.data.images.new(name=url.split('/')[-1], width=64, height=64)
			texture.image.source = 'FILE'
		texture.image.filepath = url
		#texture.image.reload()

	def update_footer(self, ob):
		if ob.type != 'MESH': return
		print('updating footer')
		self._textures_widget_container.remove( self._textures_widget_modal )
		self._textures_widget_modal = root = gtk.VBox()
		self._textures_widget_container.add( root )

		if not ob.data.materials: ob.data.materials.append( bpy.data.materials.new(name=ob.name) )
		mat = ob.data.materials[0]

		for i in range(4):
			row = gtk.HBox(); root.pack_start( row )
			row.set_border_width(3)
			row.pack_start( gtk.Label('%s: '%(i+1)), expand=False )

			if not mat.texture_slots[ i ]: mat.texture_slots.add(); mat.texture_slots[ i ].texture_coords = 'UV'
			slot = mat.texture_slots[ i ]
			if not slot.texture: slot.texture = bpy.data.textures.new(name='%s.TEX%s'%(ob.name,i), type='IMAGE')

			combo = gtk.ComboBoxText()
			row.pack_start( combo, expand=False )
			for i,type in enumerate( 'MIX ADD SUBTRACT OVERLAY MULTIPLY'.split() ):
				combo.append('id', type)
				if type == slot.blend_type: gtk.combo_box_set_active( combo, i )
			combo.set_tooltip_text( 'texture blend mode' )
			combo.connect('changed', lambda c,s: setattr(s,'blend_type',c.get_active_text()), slot)

			for name,uname,fname in [('color','use_map_color_diffuse','diffuse_color_factor'), ('normal','use_map_normal','normal_factor'), ('alpha','use_map_alpha','alpha_factor'), ('specular','use_map_specular','specular_factor')]:

				slider = SimpleSlider( slot, name=fname, title='', max=1.0, driveable=False, border_width=0, no_show_all=True )
				b = gtk.CheckButton( name )
				b.set_active( getattr(slot,uname) )
				b.connect('toggled', self.toggle_texture_slot, slot, uname, slider.widget)
				row.pack_start( b, expand=False )
				row.pack_start( slider.widget )
				if b.get_active(): slider.widget.show()
				else: slider.widget.hide()

			row.pack_start( gtk.Label() )
			e = FileEntry( '', self.load_texture, slot.texture )
			row.pack_start( e.widget, expand=False )

		root.show_all()

	def get_wave_widget(self):
		frame = gtk.Frame()
		root = gtk.VBox(); frame.add( root )

		e = FileEntry( 'wave file: ', self.open_wave )
		root.pack_start( e.widget )

		e.widget.pack_start( gtk.Label() )

		self._wave_file_length_label = a = gtk.Label()
		e.widget.pack_start( a, expand=False )

		widget = self.audio.microphone.get_widget()
		e.widget.pack_start( widget, expand=False )

		bx = gtk.HBox(); root.pack_start( bx )

		b = gtk.ToggleButton( icons.PLAY )
		b.connect('toggled', self.toggle_wave )
		bx.pack_start( b, expand=False )

		b = gtk.CheckButton('loop')
		#b.set_active( self.play_wave_on_record )
		#b.connect('toggled', lambda b: setattr(self,'play_wave_on_record',b.get_active()))
		bx.pack_start( b, expand=False )


		bx.pack_start( gtk.Label() )

		self._wave_time_label = a = gtk.Label()
		bx.pack_start( a, expand=False )

		bx.pack_start( gtk.Label() )

		b = gtk.CheckButton('auto-play on record')
		b.set_active( self.play_wave_on_record )
		b.connect('toggled', lambda b: setattr(self,'play_wave_on_record',b.get_active()))
		bx.pack_start( b, expand=False )

		return frame

	def toggle_wave(self,button):
		if button.get_active(): self.start_wave()
		else: self.stop_wave()

	def start_wave(self):
		self.wave_playing = True
		self.wave_speaker.play()

	def stop_wave(self):
		self.wave_playing = False
		self.wave_speaker.stop()

	def open_wave(self, url):
		if url.lower().endswith('.wav'):
			print('loading wave file', url)
			self.wave_url = url
			wf = wave.open( url, 'rb')
			fmt = wf.getsampwidth()
			assert fmt==2	# 16bits
			chans = wf.getnchannels()
			self.wave_frequency = wf.getframerate()
			## cache to list of chunks (bytes) ##
			frames = wf.getnframes()
			samples = wf.readframes(frames)
			wf.close()
			print('wave file loaded')
			txt = 'seconds: %s' %(frames / self.wave_frequency)
			self._wave_file_length_label.set_text( txt )

			self.wave_speaker = Speaker( 
				frequency=self.wave_frequency, 
				stereo = chans==2,
				streaming=False,
			)
			self.wave_speaker.cache_samples( samples )

	def get_recording_widget(self):
		frame = gtk.Frame()
		root = gtk.VBox(); frame.add( root )

		bx = gtk.HBox(); root.pack_start( bx )
		b = gtk.ToggleButton( 'record %s' %icons.RECORD )
		b.set_tooltip_text('record selected objects')
		b.connect('toggled', self.toggle_record )
		bx.pack_start( b, expand=False )

		self._rec_preview_button = b = gtk.ToggleButton( 'preview %s' %icons.PLAY )
		b.connect('toggled', self.toggle_preview)
		bx.pack_start( b, expand=False )

		b = gtk.Button( 'bake %s' %icons.WRITE )
		b.set_tooltip_text('bake selected objects animation to curves')
		b.connect('clicked', self.bake_animation)
		bx.pack_start( b, expand=False )

		bx.pack_start( gtk.Label() )
		self._rec_current_time_label = gtk.Label('-')
		bx.pack_start( self._rec_current_time_label, expand=False )
		bx.pack_start( gtk.Label() )

		frame2 = gtk.Frame()
		bx.pack_start( frame2, expand=False )
		box = gtk.HBox(); box.set_border_width(4)
		frame2.add( box )
		box.pack_start( gtk.Label('physics'), expand=False )
		s = gtk.Switch()
		s.connect('button-press-event', self.cb_toggle_physics )
		s.set_tooltip_text( 'toggle physics' )
		box.pack_start( s, expand=False )
		b = gtk.ToggleButton( icons.PLAY_PHYSICS ); b.set_relief( gtk.RELIEF_NONE )
		b.connect('toggled', lambda b: ENGINE.toggle_pause(b.get_active()))
		box.pack_start( b, expand=False )

		root.pack_start( self.get_playback_widget() )

		return frame

	def get_playback_widget(self):
		frame = gtk.Frame()
		root = gtk.HBox(); frame.add( root )

		b = gtk.ToggleButton( icons.PLAY )
		b.connect('toggled', lambda b: bpy.ops.screen.animation_play() )
		root.pack_start( b, expand=False )

		b = gtk.SpinButton()
		self._current_frame_adjustment = adj = b.get_adjustment()
		adj.configure( 
			value=self.context.scene.frame_current, 
			lower=self.context.scene.frame_start, 
			upper=self.context.scene.frame_end, 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		adj.connect('value-changed', lambda a,s: setattr(s.context.scene, 'frame_current',int(a.get_value())), self)
		scale = gtk.HScale( adj )
		root.pack_start( scale )
		scale.set_value_pos(gtk.POS_LEFT)
		scale.set_digits(0)
		root.pack_start( b, expand=False )

		b = gtk.SpinButton()
		root.pack_start( b, expand=False )
		self._start_frame_adjustment = adj = b.get_adjustment()
		adj.configure( 
			value=self.context.scene.frame_start, 
			lower=0, 
			upper=2**16, 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		adj.connect('value-changed', self.adjust_playback_range)

		b = gtk.SpinButton()
		root.pack_start( b, expand=False )
		self._end_frame_adjustment = adj = b.get_adjustment()
		adj.configure( 
			value=self.context.scene.frame_end, 
			lower=0, 
			upper=2**16, 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		adj.connect('value-changed', self.adjust_playback_range)

		return frame

	def adjust_playback_range(self, adj):
		self._current_frame_adjustment.configure( 
			value=self.context.scene.frame_current, 
			lower=self._start_frame_adjustment.get_value(), 
			upper=self._end_frame_adjustment.get_value(), 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		self.context.scene.frame_start = self._start_frame_adjustment.get_value()
		self.context.scene.frame_end = self._end_frame_adjustment.get_value()

	def create_header_ui(self, root):
		self.header = gtk.HBox()
		self.header.set_border_width(2)
		root.pack_start(self.header, expand=False)

		frame = gtk.Frame(); self.header.pack_start( frame, expand=False )
		box = gtk.HBox(); box.set_border_width(4)
		frame.add( box )

		self.popup = Popup()
		b = gtk.ToggleButton( icons.POPUP ); b.set_relief( gtk.RELIEF_NONE )
		b.connect('toggled',self.popup.toggle_popup)
		box.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.OVERLAY ); b.set_relief( gtk.RELIEF_NONE )
		b.connect('toggled',self.toggle_overlay)
		box.pack_start( b, expand=False )

		self.header.pack_start( gtk.Label() )

		self._frame = gtk.Frame()
		self._modal = gtk.Label()
		self._frame.add( self._modal )
		self.header.pack_start( self._frame )

		self.header.pack_start( gtk.Label() )


		b = gtk.ToggleButton( icons.LEFT_UI ); b.set_relief( gtk.RELIEF_NONE )
		b.set_active(True)
		b.connect('toggled',self.toggle_left_tools)
		self.header.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.BOTTOM_UI ); b.set_relief( gtk.RELIEF_NONE )
		b.set_active(True)
		b.connect('toggled',self.toggle_footer)
		self.header.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.RIGHT_UI ); b.set_relief( gtk.RELIEF_NONE )
		b.set_active(True)
		b.connect('toggled',self.toggle_right_tools)
		self.header.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.FULLSCREEN ); b.set_relief( gtk.RELIEF_NONE )
		b.connect('toggled',self.toggle_fullscreen)
		self.header.pack_start( b, expand=False )


	def toggle_fullscreen(self,b):
		if b.get_active():
			self.window.set_keep_above(True)
			self.window.fullscreen()
		else:
			self.window.set_keep_above(False)
			self.window.unfullscreen()

	def toggle_overlay(self,b):
		if b.get_active(): self.window.set_opacity( 0.8 )
		else: self.window.set_opacity( 1.0 )

	def toggle_left_tools(self,b):
		if b.get_active(): self._left_tools.show()
		else: self._left_tools.hide()

	def toggle_right_tools(self,b):
		if b.get_active(): self.toolsUI.widget.show()
		else: self.toolsUI.widget.hide()

	def toggle_footer(self,b):
		if b.get_active(): self.footer.show()
		else: self.footer.hide()


	def drop_on_blender_container(self, wid, con, x, y, time):
		ob = self.context.active_object

		if type(DND.source_object) is bpy.types.Material:
			print('material dropped')
			mat = DND.source_object
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

	def create_left_tools( self, parent ):
		self._left_tools = gtk.VBox()
		self._left_tools.set_border_width( 2 )
		parent.pack_start( self._left_tools, expand=False )

		ex = gtk.Expander( 'webgl')
		self._left_tools.pack_start( ex, expand=False )
		note = gtk.Notebook(); ex.add( note )

		widget = self.websocket_server.webGL.get_fx_widget()
		note.append_page( widget, gtk.Label( icons.FX_LAYERS ) )
		page = gtk.VBox()
		b = CheckButton( 'randomize', tooltip='toggle randomize camera' )
		b.connect( self, path='camera_randomize' )
		page.pack_start( b.widget, expand=False )
		for name in 'camera_focus camera_aperture camera_maxblur'.split():
			page.pack_start( gtk.Label(name.split('_')[-1]), expand=False )
			if name == 'camera_aperture':
				slider = SimpleSlider( self, name=name, title='', max=0.2, driveable=True )
			else:
				slider = SimpleSlider( self, name=name, title='', max=3.0, driveable=True )
			page.pack_start( slider.widget, expand=False )
		note.append_page(page, gtk.Label( icons.CAMERA) )

		self.outlinerUI = OutlinerUI()
		note.append_page( self.outlinerUI.widget, gtk.Label(icons.OUTLINER) )

		#################### drivers ###################
		self._left_tools_modals = {}

		ex = gtk.Expander( 'drivers')
		self._left_tools.pack_start( ex, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'drivers' ] = (ex,note)
		Pyppet.register( self.update_drivers_widget )

		ex = gtk.Expander( 'forces')
		self._left_tools.pack_start( ex, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'forces' ] = (ex,note)
		Pyppet.register( self.update_forces_widget )

		ex = gtk.Expander( 'joints')
		self._left_tools.pack_start( ex, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'joints' ] = (ex,note)
		Pyppet.register( self.update_joints_widget )

		ex = gtk.Expander( 'solver')
		self._left_tools.pack_start( ex, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'solver' ] = (ex,note)
		Pyppet.register( self.update_solver_widget )


	def update_drivers_widget( self, ob ):
		EX,note = self._left_tools_modals[ 'drivers' ]
		EX.remove( note )
		note = gtk.Notebook(); EX.add( note )
		self._left_tools_modals[ 'drivers' ] = (EX,note)

		############# direct transform ##############
		root = gtk.VBox(); root.set_border_width( 2 )
		note.append_page( root, gtk.Label(icons.TRANSFORM) )
		nice = {'location':'Location', 'scale':'Scale', 'rotation_euler':'Rotation' }
		tags='location scale rotation_euler'.split()
		for i,tag in enumerate(tags):
			root.pack_start(
				NotebookVectorWidget(ob,tag, title=nice[tag], expanded=i is 0).widget, 
				expand=False
			)

		############# physics driver forces ##############
		root = gtk.VBox(); root.set_border_width( 2 )
		note.append_page( root, gtk.Label(icons.FORCES+'Global') )
		nice = {
			'ode_global_force':'Global Force',
			'ode_global_torque':'Global Torque',
		}
		tags='ode_global_force ode_global_torque'.split()
		for i,tag in enumerate(tags):
			root.pack_start(
				NotebookVectorWidget(ob,tag, title=nice[tag], expanded=i is 0).widget, 
				expand=False
			)

		root = gtk.VBox(); root.set_border_width( 2 )
		note.append_page( root, gtk.Label(icons.FORCES+'Local') )
		nice = {
			'ode_local_force':'Local Force',
			'ode_local_torque':'Local Torque',
		}
		tags='ode_local_force ode_local_torque'.split()
		for i,tag in enumerate(tags):
			root.pack_start(
				NotebookVectorWidget(ob,tag, title=nice[tag], expanded=i is 0).widget, 
				expand=False
			)


		EX.show_all()

	def update_forces_widget( self, ob ):
		EX,note = self._left_tools_modals[ 'forces' ]
		EX.remove( note )
		note = gtk.Notebook(); EX.add( note )
		self._left_tools_modals[ 'forces' ] = (EX,note)

		root = gtk.VBox(); root.set_border_width( 2 )
		note.append_page( root, gtk.Label( icons.CONSTANT_FORCES+'Global' ) )
		nice = {
			'ode_constant_global_force':'Constant Global Force', 
			'ode_constant_global_torque':'Constant Global Torque', 
		}
		tags='ode_constant_global_force ode_constant_global_torque'.split()
		for i,tag in enumerate(tags):
			frame = gtk.Frame( nice[tag] )
			root.pack_start( frame, expand=False )
			bx = gtk.VBox(); frame.add( bx )
			for i in range(3):
				slider = SimpleSlider(
					ob, tag, title='xyz'[i], 
					target_index=i, driveable=True,
					min=-500, max=500,
				)
				bx.pack_start( slider.widget, expand=False )

		root = gtk.VBox(); root.set_border_width( 2 )
		note.append_page( root, gtk.Label( icons.CONSTANT_FORCES+'Local' ) )
		nice = {
			'ode_constant_local_force':'Constant Local Force',
			'ode_constant_local_torque':'Constant Local Torque',
		}
		tags='ode_constant_local_force ode_constant_local_torque'.split()
		for i,tag in enumerate(tags):
			frame = gtk.Frame( nice[tag] )
			root.pack_start( frame, expand=False )
			bx = gtk.VBox(); frame.add( bx )
			for i in range(3):
				slider = SimpleSlider(
					ob, tag, title='xyz'[i], 
					target_index=i, driveable=True,
					min=-500, max=500,
				)
				bx.pack_start( slider.widget, expand=False )


		EX.show_all()

	def update_joints_widget( self, ob ):
		EX,note = self._left_tools_modals[ 'joints' ]
		EX.remove( note )
		note = gtk.Notebook(); EX.add( note )
		self._left_tools_modals[ 'joints' ] = (EX,note)

		sw = gtk.ScrolledWindow()
		label = gtk.Label( icons.JOINT )
		note.append_page( sw, label )
		sw.set_policy(True,True)
		root = gtk.VBox(); root.set_border_width( 6 )
		sw.add_with_viewport( root )
		DND.make_destination( label )
		#label.connect( 'drag-drop', self.cb_drop_joint, root )


		EX.show_all()

	def update_solver_widget( self, ob ):
		EX,note = self._left_tools_modals[ 'solver' ]
		EX.remove( note )
		note = gtk.Notebook(); EX.add( note )
		self._left_tools_modals[ 'solver' ] = (EX,note)

		########### physics joints: MODELS: Ragdoll, Biped, Rope ############
		if ob.type=='ARMATURE':
			if ob.pyppet_model:
				print('pyppet-model:', ob.pyppet_model)
				model = getattr(Pyppet, 'Get%s' %ob.pyppet_model)( ob.name )
				label = model.get_widget_label()
				widget = getattr(model, 'Get%sWidget' %ob.pyppet_model)()
				note.append_page( widget, label )

				sw = gtk.ScrolledWindow()
				label = gtk.Label( icons.TARGET )
				note.append_page( sw, label )
				sw.set_policy(True,True)
				root = gtk.VBox(); root.set_border_width( 6 )
				sw.add_with_viewport( root )
				root.pack_start( model.get_targets_widget(label) )


			else:
				for mname in Pyppet.MODELS:
					model = getattr(Pyppet, 'Get%s' %mname)( ob.name )
					label = model.get_widget_label()
					widget = getattr(model, 'Get%sWidget' %mname)()
					note.append_page( widget, label )


		EX.show_all()


	def deprecate():
			if ob.type=='MESH':
				sw = gtk.ScrolledWindow()
				note.append_page( sw, gtk.Label( icons.MATERIAL ) )
				sw.set_policy(True,True)
				root = gtk.VBox(); root.set_border_width( 6 )
				sw.add_with_viewport( root )

				for m in ob.data.materials:
					ex = gtk.Expander( m.name ); ex.set_expanded(True)
					root.pack_start( ex )
					bx = gtk.VBox(); ex.add( bx )

					for tag in 'diffuse_intensity specular_intensity ambient emit alpha'.split():
						slider = SimpleSlider( m, name=tag, driveable=True )
						bx.pack_start( slider.widget, expand=False )

					bx.pack_start(
						self.vector_widget(m,'diffuse_color', title='diffuse color' ), 
						expand=True
					)


			elif ob.type=='LAMP':
				sw = gtk.ScrolledWindow()
				note.append_page( sw, gtk.Label( icons.LIGHT ) )
				sw.set_policy(True,True)
				root = gtk.VBox(); root.set_border_width( 6 )
				sw.add_with_viewport( root )

				for tag in 'energy'.split():
					slider = SimpleSlider( ob.data, name=tag, driveable=True )
					root.pack_start( slider.widget, expand=False )

				root.pack_start(
					self.vector_widget(ob.data,'color' ), 
					expand=True
				)







			else:


				########### physics config ############
				sw = gtk.ScrolledWindow()
				note.append_page( sw, gtk.Label( icons.GRAVITY ) )
				sw.set_policy(True,True)
				root = gtk.VBox(); root.set_border_width( 6 )
				sw.add_with_viewport( root )

				b = gtk.CheckButton('%s body active' %icons.BODY )
				root.pack_start( b, expand=False )
				b.set_active( ob.ode_use_body )
				b.connect('toggled', lambda b,o: setattr(o,'ode_use_body',b.get_active()), ob)

				b = gtk.CheckButton('%s enable collision' %icons.COLLISION)
				root.pack_start( b, expand=False )
				b.set_active( ob.ode_use_collision )
				b.connect('toggled', lambda b,o: setattr(o,'ode_use_collision',b.get_active()), ob)

				b = gtk.CheckButton('%s enable gravity' %icons.GRAVITY)
				root.pack_start( b, expand=False )
				b.set_active( ob.ode_use_gravity )
				b.connect('toggled', lambda b,o: setattr(o,'ode_use_gravity',b.get_active()), ob)



				root.pack_start( gtk.Label() )

				s = Slider(
					ob, name='ode_mass', title='mass', 
					min=0.001, max=10.0,
				)
				root.pack_start(s.widget, expand=False)

				s = Slider(
					ob, name='ode_linear_damping', title='linear damping',
					min=0.0, max=1.0,
				)
				root.pack_start(s.widget, expand=False)

				s = Slider(
					ob, name='ode_angular_damping', title='angular damping',
					min=0.0, max=1.0,
				)
				root.pack_start(s.widget, expand=False)

				s = Slider(
					ob, name='ode_force_driver_rate', 
					title='%s driver rate' %icons.FORCES, 
					min=0.0, max=1.0,
				)
				root.pack_start(s.widget, expand=False)





	def create_ui(self, context):
		self._blender_min_width = 640
		self._blender_min_height = 480

		self.window = win = gtk.Window()
		win.modify_bg( gtk.STATE_NORMAL, BG_COLOR )
		win.set_title( 'Pyppet '+VERSION )
		self.root = root = gtk.VBox()
		win.add( root )

		split = gtk.HBox()
		root.pack_start( split )

		############ LEFT TOOLS ###########
		self.create_left_tools( split )

		###############################
		Vsplit = gtk.VBox()
		split.pack_start( Vsplit, expand=True )

		self.create_header_ui( Vsplit )

		Hsplit = gtk.HBox()
		Vsplit.pack_start( Hsplit )
		subV = gtk.VPaned()
		Hsplit.pack_start( subV )


		note = gtk.Notebook()
		subV.add1( note )

		################# blender containers #################
		self.blender_container = eb = gtk.EventBox()
		note.append_page( self.blender_container, gtk.Label('default view') )
		self.blender_container2 = eb = gtk.EventBox()
		note.append_page( eb, gtk.Label('UV editor') )
		################# setup destination DND ###############
		DND.make_destination( self.blender_container )
		self.blender_container.connect('drag-drop', self.drop_on_blender_container)
		DND.make_destination( self.blender_container2 )
		self.blender_container2.connect('drag-drop', self.drop_on_blender_container)
		################# setup source DND ###################
		DND.make_source( self.blender_container, 'BLENDER_CONTAINER' )
		DND.make_source( self.blender_container2, 'BLENDER_CONTAINER' )
		################# source DND is not working! - TODO research how to make it work ############
		xsocket = self.create_blender_xembed_socket()
		self.blender_container.add( xsocket )


		################ gnome nautilus - NOT WORKING? ####################
		#self._nautilus_container = gtk.EventBox()
		#self._nautilus_xsocket = gtk.Socket()
		#self._nautilus_container.add( self._nautilus_xsocket )
		#note.append_page( self._nautilus_container, gtk.Label('file browser') )

		################ The Gimp ##############
		if 0:
			self._gimp_page = gtk.HBox()
			note.append_page( self._gimp_page, gtk.Label('gimp') )
			self._gimp_toolbox_xsocket = gtk.Socket()
			self._gimp_toolbox_xsocket.connect('plug-added', self.on_plug_debug)
			self._gimp_image_xsocket = gtk.Socket()
			self._gimp_layers_xsocket = gtk.Socket()
			eb = gtk.EventBox()
			eb.add( self._gimp_toolbox_xsocket )
			self._gimp_page.pack_start( eb, expand=False )
			self._gimp_page.pack_start( self._gimp_image_xsocket, expand=True )
			self._gimp_page.pack_start( self._gimp_layers_xsocket, expand=False )



		################# google chrome ######################
		self._chrome_xsocket = gtk.Socket()
		subV.add2( self._chrome_xsocket )



		############### ToolsUI ################
		self.toolsUI = ToolsUI( self.lock, context )
		self.toolsUI.widget.set_border_width(2)
		Hsplit.pack_start( self.toolsUI.widget, expand=False )

		############### FOOTER #################
		self.footer = note = gtk.Notebook()
		note.set_tab_pos( gtk.POS_BOTTOM )
		Vsplit.pack_start( self.footer, expand=False )

		page = gtk.Frame()
		note.append_page( page, gtk.Label(icons.RECORD) )
		page.add( self.get_recording_widget() )

		page = gtk.Frame()
		note.append_page( page, gtk.Label(icons.SINE_WAVE) )
		page.add( self.get_wave_widget() )

		page = gtk.Frame()
		note.append_page( page, gtk.Label(icons.TEXTURE) )
		page.add( self.get_textures_widget() )


		page = gtk.Frame()
		note.append_page( page, gtk.Label(icons.KEYBOARD) )
		w = self.audio.synth.channels[0].get_widget()
		page.add( w )

		win.connect('destroy', self.exit )
		win.show_all()

		self.do_xembed( xsocket, 'Blender' )		# this must come last
		self.do_xembed( self._chrome_xsocket, "New Tab - Google Chrome")
		#self.do_xembed( self._nautilus_xsocket, "Home")
		if 0:
			self.do_xembed( self._gimp_toolbox_xsocket, "Toolbox")
			self.do_xembed( self._gimp_image_xsocket, "GNU Image Manipulation Program")
			self.do_xembed( self._gimp_layers_xsocket, "Layers, Channels, Paths, Undo - Brushes, Patterns, Gradients")



	def update_header(self,ob):
		self._frame.remove( self._modal )
		self._modal = eb = gtk.EventBox()
		self._frame.add( self._modal )
		root = gtk.HBox()
		eb.add( root )
		DND.make_source( eb, ob )
		root.pack_start( gtk.Label(ob.name), expand=False )

		if ob.type == 'ARMATURE':
			b = gtk.ToggleButton( icons.MODE ); b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('toggle pose mode')
			root.pack_start( b, expand=False )
			b.set_active( self.context.mode=='POSE' )
			b.connect('toggled', self.toggle_pose_mode)

			if ob.name not in self.entities:
				biped = self.GetBiped( ob )
				b = gtk.Button( icons.BIPED ); b.set_relief( gtk.RELIEF_NONE )
				root.pack_start( b, expand=False )
				b.connect('clicked', lambda b,bi: [b.hide(), bi.create()], biped)

		elif ob.type=='LAMP':
			r,g,b = ob.data.color
			gcolor = rgb2gdk(r,g,b)
			b = gtk.ColorButton( gcolor )
			b.set_relief( gtk.RELIEF_NONE )
			root.pack_start( b, expand=False )
			b.connect('color-set', self.color_set, gcolor, ob.data )
			slider = SimpleSlider( ob.data, name='energy', title='', max=5.0, driveable=True, border_width=0 )
			root.pack_start( slider.widget )

		else:
			root.set_border_width(3)

			root.pack_start( gtk.Label('    '), expand=False )

			g = gtk.ToggleButton( icons.GRAVITY ); g.set_relief( gtk.RELIEF_NONE )
			g.set_no_show_all(True)
			if ob.ode_use_body: g.show()
			else: g.hide()

			b = gtk.ToggleButton( icons.BODY ); b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('toggle body physics')
			root.pack_start( b, expand=False )
			b.set_active( ob.ode_use_body )
			b.connect('toggled', self.toggle_body, g)

			g.set_tooltip_text('toggle gravity')
			root.pack_start( g, expand=False )
			g.set_active( ob.ode_use_gravity )
			g.connect('toggled', self.toggle_gravity)

			root.pack_start( gtk.Label('    '), expand=False )


			combo = gtk.ComboBoxText()
			Fslider = SimpleSlider( ob, name='ode_friction', title='', max=2.0, driveable=True, border_width=0, no_show_all=True, tooltip='friction' )
			Bslider = SimpleSlider( ob, name='ode_bounce', title='', max=1.0, driveable=True, border_width=0, no_show_all=True, tooltip='bounce' )

			b = gtk.ToggleButton( icons.COLLISION ); b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('toggle collision')
			root.pack_start( b, expand=False )
			b.set_active( ob.ode_use_collision )
			b.connect('toggled', self.toggle_collision, combo, Fslider.widget, Bslider.widget)

			root.pack_start( combo, expand=False )
			for i,type in enumerate( 'BOX SPHERE CAPSULE CYLINDER'.split() ):
				combo.append('id', type)
				if type == ob.game.collision_bounds_type:
					gtk.combo_box_set_active( combo, i )
			combo.set_tooltip_text( 'collision type' )
			combo.connect('changed',self.change_collision_type, ob )

			root.pack_start( Fslider.widget )
			root.pack_start( Bslider.widget )


			if ob.ode_use_collision:
				combo.show()
				Fslider.widget.show()
				Bslider.widget.show()

			else:
				combo.hide()
				Fslider.widget.hide()
				Bslider.widget.hide()

			combo.set_no_show_all(True)

			root.pack_start( gtk.Label() )
			###################################################
			b = gtk.ToggleButton( icons.WIREFRAME )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show wireframe')
			b.set_active(ob.show_wire)
			b.connect('toggled', lambda b,o: setattr(o,'show_wire',b.get_active()), ob)
			root.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.NAME )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show name')
			b.set_active(ob.show_name)
			b.connect('toggled', lambda b,o: setattr(o,'show_name',b.get_active()), ob)
			root.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.AXIS )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show axis')
			b.set_active(ob.show_axis)
			b.connect('toggled', lambda b,o: setattr(o,'show_axis',b.get_active()), ob)
			root.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.XRAY )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show xray')
			b.set_active(ob.show_x_ray)
			b.connect('toggled', lambda b,o: setattr(o,'show_x_ray',b.get_active()), ob)
			root.pack_start( b, expand=False )

			combo = gtk.ComboBoxText()
			root.pack_start( combo, expand=False )
			for i,type in enumerate( ['TEXTURED', 'SOLID', 'WIRE', 'BOUNDS'] ):
				combo.append('id', type)
				if type == ob.draw_type: gtk.combo_box_set_active( combo, i )
			combo.set_tooltip_text( 'view draw type' )
			combo.connect('changed', lambda c,o: setattr(o,'draw_type',c.get_active_text()), ob)

			r,g,b,a = ob.color	# ( mesh: float-array not color-object )
			gcolor = rgb2gdk(r,g,b)
			b = gtk.ColorButton(gcolor)
			#b.set_tooltip_text('webGL shader tint')	# GTK wrapper bug - TODO fix me
			b.set_relief( gtk.RELIEF_NONE )
			root.pack_start( b, expand=False )
			b.connect('color-set', self.color_set, gcolor, ob )

			b = gtk.ToggleButton( icons.STREAMING )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('stream mesh to webGL client')
			b.set_active(ob.webgl_stream_mesh)
			b.connect('toggled', lambda b,o: setattr(o,'webgl_stream_mesh',b.get_active()), ob)
			root.pack_start( b, expand=False )


		self._modal.show_all()

	def color_set( self, button, color, ob ):
		button.get_color( color )
		r,g,b = gdk2rgb( color )
		ob.color[0] = r
		ob.color[1] = g
		ob.color[2] = b

	def toggle_pose_mode(self,button):
		if button.get_active():
			bpy.ops.object.mode_set( mode='POSE' )
		else:
			bpy.ops.object.mode_set( mode='OBJECT' )

	def toggle_gravity(self, b):
		for ob in self.context.selected_objects: ob.ode_use_gravity = b.get_active()
	def toggle_collision(self, b, combo, fslider, bslider):
		for ob in self.context.selected_objects: ob.ode_use_collision = b.get_active()
		if b.get_active():
			combo.show()
			fslider.show()
			bslider.show()
		else:
			combo.hide()
			fslider.hide()
			bslider.hide()

	def toggle_body(self, b, gravity_button):
		for ob in self.context.selected_objects: ob.ode_use_body = b.get_active()
		if b.get_active(): gravity_button.show()
		else: gravity_button.hide()

	def change_collision_type(self,combo, ob):
		type = combo.get_active_text()
		ob.game.collision_bounds_type = type
		w = ENGINE.get_wrapper(ob)
		w.reset_collision_type()


##########################################################
class App( PyppetUI ):

	def after_on_plug_blender(self):
		# change 3 views up, get the UV editor, duplicate window, change back #
		for i in range(3): bpy.ops.screen.screen_set( delta=1 )
		bpy.ops.wm.window_duplicate()
		for i in range(3): bpy.ops.screen.screen_set( delta=-1 )

		self._blender_xsocket2 = xsock = gtk.Socket()
		self.blender_container2.add( xsock )
		xsock.connect('size-allocate',self.on_resize_blender)	# required
		#xsock.connect('plug-added', self.on_plug_blender2)	# not required?
		xsock.show()

		self.do_wnck_hack()
		self.do_xembed( xsock, 'Blender' )
		#self.window.maximize()
		Blender.window_expand()

	def on_plug_blender2(self, args):
		self._blender_xsocket2.set_size_request(
			self._blender_min_width, 
			self._blender_min_height
		)


	def exit(self, arg):
		self.audio.exit()
		self.active = False
		self.websocket_server.active = False
		sdl.Quit()
		print('clean exit')

	def cb_toggle_physics(self,button,event):
		if button.get_active(): self.toggle_physics(False)	# reversed
		else: self.toggle_physics(True)

	def toggle_physics(self,switch):
		if switch:
			ENGINE.start()
		else:
			ENGINE.stop()
			for e in self.entities.values(): e.reset()


	def __init__(self):
		assert self.setup_blender_hack( bpy.context )		# moved to BlenderHack in core.py

		self.reset()		# PyppetAPI Public
		self.register( self.update_header ) # listen to active object change
		self.register( self.update_footer )

		self.play_wave_on_record = True
		self.wave_playing = False

		self._rec_start_time = time.time()
		self._rec_objects = {}	# recording buffers
		self.preview = False
		self.recording = False
		self.active = True

		#self.lock = threading._allocate_lock()

		self.server = Server()
		self.client = Client()
		self.websocket_server = WebSocketServer( listen_port=8081 )
		self.websocket_server.start()

		self.audio = AudioThread()
		self.audio.start()

		self.camera_randomize = False
		self.camera_focus = 1.5
		self.camera_aperture = 0.15
		self.camera_maxblur = 1.0

		#self.setup_blender_hack()	# moved to BlenderHack in core.py


		#self.baker_active = False
		#self.baker_region = None
		#self.baker_queue = []
		#self.setup_image_editor_callback( None )
		#self.blender_window_ready = False
		self.progressive_baking = True




	####################################################

	def mainloop(self):
		while self.active:

			#if self.baker_active: self.baker_region.tag_redraw()
			self.update_blender_and_gtk()

			win = Blender.Window( self.context.window )
			# grabcursor on click and drag (view3d only)
			#print(win, win.winid, win.grabcursor, win.windowstate, win.modalcursor)
			self.context.blender_has_cursor = bool( win.grabcursor )

			DriverManager.update()
			self.audio.update()		# updates gtk widgets

			if self.context.scene.frame_current != int(self._current_frame_adjustment.get_value()):
				self._current_frame_adjustment.set_value( self.context.scene.frame_current )

			self.update_callbacks()	# updates UI on active object changed
			self.toolsUI.iterate( self.context )
			self.outlinerUI.iterate( self.context )
			self.popup.update( self.context )

			models = self.entities.values()
			for mod in models: mod.update_ui( self.context )

			now = time.time() - self._rec_start_time
			if self.wave_playing:
				self.wave_speaker.update()
				#print('wave time', self.wave_speaker.seconds)
				self._wave_time_label.set_text(
					'seconds: %s' %round(self.wave_speaker.seconds,2)
				)
				## use wave time if play on record is true ##
				if self.play_wave_on_record: now = self.wave_speaker.seconds

			if self.recording or self.preview:
				self._rec_current_time_label.set_text( 'seconds: %s' %round(now,2) )
			if self.preview: self.update_preview( now )
			if ENGINE.active and not ENGINE.paused: self.update_physics( now )


			if not self._image_editor_handle:
				# ImageEditor redraw callback will update http-server,
				# if ImageEditor is now shown, still need to update the server.
				self.server.update( self.context )

			self.client.update( self.context )
			self.websocket_server.update( self.context )


######## Pyppet Singleton #########
Pyppet = App()

#bpy.types.Scene.use_gtk = bpy.props.BoolProperty(
#	name='enable gtk', 
#	description='toggle GTK3',
#	default=False,
#	update=lambda a,b: Pyppet.toggle_gtk(a,b)
#)

#################################


########## Cache for OutlinerUI and Joint functions ##########
class ObjectWrapper( object ):
	def __init__(self, ob):
		self.name = ob.name
		self.type = ob.type
		self.parents = {}
		self.children = {}

	def attach(self, child):
		'''
		. from Gtk-Outliner drag parent to active-object,
		. active-object becomes child using ODE joint
		. pivot is relative to parent.
		'''

		parent = bpy.data.objects[ self.name ]
		child = bpy.data.objects[ child ]

		cns = child.constraints.new('RIGID_BODY_JOINT')		# cheating
		cns.show_expanded = False
		cns.target = parent			# draws dotted connecting line in blender (not safe outside of bpy.context)
		cns.child = None			# child is None

		if parent.name not in ENGINE.bodies:
			parent.ode_use_body = True
		if child.name not in ENGINE.bodies:
			child.ode_use_body = True

		cw = ENGINE.get_wrapper(child)
		pw = ENGINE.get_wrapper(parent)
		joint = cw.new_joint( pw, name=parent.name )

		self.children[ child.name ] = joint		# TODO support multiple joints per child

		return self.get_joint_widget( child.name )


	############### joint widget ###########
	def get_joint_widget( self, child_name ):
		joint = self.children[ child_name ]

		ex = gtk.Expander( 'joint: ' + self.name ); ex.set_expanded(True)
		root = gtk.VBox(); ex.add( root )
		row = gtk.HBox(); root.pack_start( row, expand=False )

		b = gtk.CheckButton(); b.set_active(True)
		b.connect('toggled', lambda b,j: j.toggle(b.get_active()), joint)
		row.pack_start( b, expand=False )

		combo = gtk.ComboBoxText()
		row.pack_start( combo )
		for i,type in enumerate( Physics.JOINT_TYPES ):
			combo.append('id', type)
			if type == 'fixed':
				gtk.combo_box_set_active( combo, i )
		combo.set_tooltip_text( Physics.Joint.Tooltips['fixed'] )
		combo.connect('changed',self.change_joint_type, child_name )

		b = gtk.Button( icons.DELETE )
		b.set_tooltip_text( 'delete joint' )
		#b.connect('clicked', self.cb_delete, ex)
		row.pack_start( b, expand=False )

		#################################################
		###################### joint params ##############
		slider = SimpleSlider( name='ERP', value=joint.get_param('ERP') )
		root.pack_start( slider.widget, expand=False )
		slider.adjustment.connect(
			'value-changed', lambda adj, j: j.set_param('ERP',adj.get_value()),
			joint
		)
		slider = SimpleSlider( name='CFM', value=joint.get_param('CFM') )
		root.pack_start( slider.widget, expand=False )
		slider.adjustment.connect(
			'value-changed', lambda adj, j: j.set_param('CFM',adj.get_value()),
			joint
		)

		return ex

	def change_joint_type(self,combo, child):
		child = bpy.data.objects[ child ]
		type = combo.get_active_text()
		w = ENGINE.get_wrapper(child)
		w.change_joint_type( self.name, type )
		combo.set_tooltip_text( Physics.Joint.Tooltips[type] )


class OutlinerUI( object ):
	def __init__(self):
		self.objects = {}	# name : ObjectWrapper
		self.meshes = {}

		self.widget = sw = gtk.ScrolledWindow()
		self.lister = box = gtk.VBox()
		box.set_border_width(6)
		sw.add_with_viewport( box )
		sw.set_policy(True,False)


	def iterate(self, context):
		objects = context.scene.objects
		if len(objects) != len(self.objects): self.update_outliner(context)

	def update_outliner(self,context):
		names = context.scene.objects.keys()
		update = []
		for name in names:
			if name not in self.objects: update.append( name )
		remove = []
		for name in self.objects:
			if name not in names: remove.append( name )

		update.sort()
		for name in update:
			ob = context.scene.objects[ name ]

			wrap = ObjectWrapper( ob )
			self.objects[ name ] = wrap

			wrap.gtk_outliner_container = eb = gtk.EventBox()
			root = gtk.HBox(); eb.add( root )
			self.lister.pack_start(eb, expand=False)
			#DND.make_source( eb, self.callback, name )

			b = gtk.Button(name)
			DND.make_source( b, wrap )		#self.callback, name )
			b.connect('clicked', lambda b,o: setattr(o,'select',True), ob)
			b.set_relief( gtk.RELIEF_NONE )
			root.pack_start( b, expand=False )

			root.pack_start( gtk.Label() )	# spacer

			b = gtk.ToggleButton( icons.VISIBLE ); root.pack_start( b, expand=False )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_active(ob.hide)
			b.set_tooltip_text('toggle visible')
			b.connect( 'toggled', lambda b,o: setattr(o,'hide',b.get_active()), ob)

			b = gtk.ToggleButton( icons.RESTRICT_SELECTION)
			root.pack_start( b, expand=False )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_active(ob.hide_select)
			b.set_tooltip_text('restrict selection')
			b.connect( 'toggled', lambda b,o: setattr(o,'hide_select',b.get_active()), ob)

			eb.show_all()


class MaterialsUI(object):
	## ob.material_slots	(missing .new or .add)
	### slot.link = 'DATA'
	### slot.material
	#ob.active_material_index = index	# works
	#ob.active_material = mat	# assigns material to active slot
	#bpy.ops.object.material_slot_assign()

	def __init__(self):
		self.widget = gtk.Frame()
		self.root = gtk.VBox()
		self.widget.add( self.root )
		Pyppet.register( self.on_active_object_changed )


	def on_active_object_changed(self, ob, expand_material=None):
		if ob.type != 'MESH': return

		self.widget.remove( self.root )
		self.root = root = gtk.VBox()
		self.widget.add( self.root )
		root.set_border_width(2)
		exs = []
		for mat in ob.data.materials:
			ex = gtk.Expander( mat.name ); exs.append( ex )
			eb = gtk.EventBox()	# expander background is colorized
			root.pack_start( eb, expand=False )
			eb.add( ex )

			subeb = gtk.EventBox()	# not colorized
			bx = gtk.VBox(); subeb.add( bx )
			ex.add( subeb )
			#if mat == ob.active_material: ex.set_expanded(True)
			if mat.name == expand_material: ex.set_expanded(True)

			DND.make_source( ex, mat )

			color = rgb2gdk(*mat.diffuse_color)
			eb.modify_bg( gtk.STATE_NORMAL, color )

			#row = gtk.HBox(); bx.pack_start( row, expand=False )
			#row.pack_start( gtk.Label() )
			#b = gtk.ColorButton( color )
			#b.connect('color-set', self.color_set, color, mat, 'diffuse_color', eb)
			#row.pack_start( b, expand=False )
			#color = rgb2gdk(*mat.specular_color)
			#b = gtk.ColorButton( color )
			#b.connect('color-set', self.color_set, color, mat, 'specular_color', eb)
			#row.pack_start( b, expand=False )
			#row.pack_start( gtk.Label() )


			hsv = gtk.HSV()
			hsv.set_color( *gtk.rgb2hsv(*mat.diffuse_color) )
			hsv.connect('changed', self.color_changed, mat, 'diffuse_color', eb)
			bx.pack_start( hsv, expand=False )

			#hsv = gtk.HSV()		# some bug with GTK, two HSV's can not be used in tabs???
			#hsv.set_color( *gtk.rgb2hsv(*mat.specular_color) )
			#hsv.connect('changed', self.color_changed, mat, 'specular_color', eb)
			#note.append_page( hsv, gtk.Label('spec') )


			subex = gtk.Expander( icons.SETTINGS )
			subex.set_border_width(2)
			bx.pack_start( subex, expand=False )
			bxx = gtk.VBox(); subex.add( bxx )

			slider = SimpleSlider( mat, name='diffuse_intensity', title='', max=1.0, driveable=True, tooltip='diffuse' )
			bxx.pack_start( slider.widget, expand=False )

			slider = SimpleSlider( mat, name='specular_intensity', title='', max=1.0, driveable=True, tooltip='specular' )
			bxx.pack_start( slider.widget, expand=False )

			slider = SimpleSlider( mat, name='specular_hardness', title='', max=500, driveable=True, tooltip='hardness' )
			bxx.pack_start( slider.widget, expand=False )

			slider = SimpleSlider( mat, name='emit', title='', max=1.0, driveable=True, tooltip='emission' )	# max is 2.0
			bxx.pack_start( slider.widget, expand=False )

			slider = SimpleSlider( mat, name='ambient', title='', max=1.0, driveable=True, tooltip='ambient' )
			bxx.pack_start( slider.widget, expand=False )

		if len(exs)==1: exs[0].set_expanded(True)

		root.pack_start( gtk.Label() )
		b = gtk.Button('new material')
		b.connect('clicked', self.add_material, ob)
		root.pack_start( b, expand=False )

		self.root.show_all()

	def add_material(self,button, ob):
		bpy.ops.object.material_slot_add()
		index = len(ob.data.materials)-1
		mat = bpy.data.materials.new( name='%s.MAT%s' %(ob.name,index) )
		ob.data.materials[ index ] = mat
		self.on_active_object_changed( ob, expand_material=mat.name )

	def color_set( self, button, color, mat, attr, eventbox ):
		button.get_color( color )
		r,g,b = gdk2rgb( color )
		vec = getattr(mat,attr)
		vec[0] = r
		vec[1] = g
		vec[2] = b
		if attr == 'diffuse_color': eventbox.modify_bg( gtk.STATE_NORMAL, color )

	def color_changed( self, hsv, mat, attr, eventbox ):
		r,g,b = get_hsv_color_as_rgb( hsv )
		vec = getattr(mat,attr)
		vec[0] = r
		vec[1] = g
		vec[2] = b
		if attr == 'diffuse_color':
			color = rgb2gdk(r,g,b)
			eventbox.modify_bg( gtk.STATE_NORMAL, color )



class ToolsUI( object ):
	COLOR = gtk.GdkRGBA(0.96,.95,.95, 0.85)
	def new_page( self, title ):
		#sw = gtk.ScrolledWindow()
		#self.notebook.append_page( sw, gtk.Label(title) )
		#eb = gtk.EventBox()
		#eb.override_background_color( gtk.STATE_NORMAL, self.COLOR )
		#box = gtk.VBox(); eb.add( box )
		#sw.add_with_viewport( eb )
		box = gtk.VBox()
		self.notebook.append_page( box, gtk.Label(title) )
		return box

	def __init__(self, lock, context):
		self.lock = lock
		self.widget = root = gtk.VBox()
		self.widget.set_size_request( 140, 460 )

		ex = gtk.Expander( icons.DEVICES )
		root.pack_start( ex, expand=False )

		self.notebook = gtk.Notebook()
		#self.notebook.set_tab_pos( gtk.POS_RIGHT )
		self.notebook.set_size_request( 260,450 )
		ex.add( self.notebook )

		box = self.new_page( icons.WEBCAM )	# webcam
		widget = Webcam.Widget( box )
		self.webcam = widget.webcam
		DND.make_source( widget.dnd_container, 'WEBCAM' )	# make drag source
		self.webcam.start_thread( self.lock )

		box = self.new_page( icons.KINECT )		# kinect
		widget = Kinect.Widget( box )
		self.kinect = widget.kinect
		DND.make_source( widget.dnd_container, 'KINECT' )	# make drag source
		widget.start_threads( self.lock )

		box = self.new_page( icons.GAMEPAD )	# gamepad
		self.gamepads_widget = GamepadsWidget( box )

		box = self.new_page( icons.WIIMOTE )	# wiimote
		self.wiimotes_widget = WiimotesWidget( box )

		box = self.new_page( icons.MICROPHONE )	# microphone
		widget = Pyppet.audio.microphone.get_analysis_widget()
		box.pack_start( widget )

		ex = gtk.Expander( icons.PHYSICS )
		root.pack_start( ex, expand=False )
		box = gtk.VBox()
		ex.add( box )
		self.engine = Physics.ENGINE
		self.physics_widget = PhysicsWidget( box, context )

		self._modifiers_pinned = False
		self._modifiers_expander = ex = gtk.Expander( icons.MODIFIERS )
		root.pack_start( ex, expand=False )
		self._modifiers_modal = gtk.EventBox()
		self._modifiers_expander.add( self._modifiers_modal )
		Pyppet.register( self.update_modifiers )

		self._cns_pinned = False
		self._cns_expander = ex = gtk.Expander( icons.CONSTRAINTS )
		root.pack_start( ex, expand=False )
		self._cns_modal = gtk.EventBox()
		self._cns_expander.add( self._cns_modal )
		Pyppet.register( self.update_constraints )


		ex = gtk.Expander( icons.MATERIALS )
		root.pack_start( ex, expand=True )
		self.materials_UI = MaterialsUI()
		ex.add( self.materials_UI.widget )


	def update_constraints(self, ob, force_update=False):
		if self._cns_pinned and not force_update: return

		self._cns_expander.remove( self._cns_modal )
		self._cns_modal = root = gtk.VBox()
		self._cns_expander.add( self._cns_modal )

		frame = gtk.Frame()
		root.pack_start( frame, expand=False )
		row = gtk.HBox()
		row.set_border_width(4)
		frame.add( row )

		b = gtk.ToggleButton( icons.SOUTH_WEST_ARROW )
		b.set_relief( gtk.RELIEF_NONE ); b.set_tooltip_text( 'pin to active' )
		b.set_active( self._cns_pinned )
		b.connect('toggled', lambda b,s: setattr(s,'_cns_pinned',b.get_active()), self)
		row.pack_start( b, expand=False )

		combo = gtk.ComboBoxText()
		row.pack_start( combo )
		for i,type in enumerate( CONSTRAINT_TYPES ): combo.append('id', type)
		gtk.combo_box_set_active( combo, 0 )

		b = gtk.Button('+')
		b.connect('clicked', self.add_constraint, combo, ob)
		row.pack_start( b, expand=False )

		stacker = VStacker()
		stacker.widget.modify_bg( gtk.STATE_NORMAL, BG_COLOR )
		stacker.set_callback( self.reorder_constraint, ob )
		root.pack_start( stacker.widget )
		for cns in ob.constraints:
			e = Expander( cns.name, insert=gtk.Label(icons.DND) )
			R = RNAWidget( cns )
			e.add( R.widget )
			stacker.append( e.widget )

			b = gtk.ToggleButton( icons.VISIBLE )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('toggle constraint')
			b.set_active( not cns.mute )
			b.connect('toggled', lambda b,c: setattr(c,'mute',not b.get_active()), cns)
			e.header.pack_start( b, expand=False )


		self._cns_expander.show_all()


	def update_modifiers(self, ob, force_update=False):
		if self._modifiers_pinned and not force_update: return

		self._modifiers_expander.remove( self._modifiers_modal )
		self._modifiers_modal = root = gtk.VBox()
		self._modifiers_expander.add( self._modifiers_modal )

		frame = gtk.Frame()
		root.pack_start( frame, expand=False )
		row = gtk.HBox()
		row.set_border_width(4)
		frame.add( row )

		b = gtk.ToggleButton( icons.SOUTH_WEST_ARROW )
		b.set_relief( gtk.RELIEF_NONE ); b.set_tooltip_text( 'pin to active' )
		b.set_active( self._modifiers_pinned )
		b.connect('toggled', lambda b,s: setattr(s,'_modifiers_pinned',b.get_active()), self)
		row.pack_start( b, expand=False )

		combo = gtk.ComboBoxText()
		row.pack_start( combo )
		for i,type in enumerate( MODIFIER_TYPES ): combo.append('id', type)
		gtk.combo_box_set_active( combo, 0 )

		b = gtk.Button('+')
		b.connect('clicked', self.add_modifier, combo, ob)
		row.pack_start( b, expand=False )

		stacker = VStacker()
		stacker.widget.modify_bg( gtk.STATE_NORMAL, BG_COLOR )
		stacker.set_callback( self.reorder_modifier, ob )
		root.pack_start( stacker.widget )
		for mod in ob.modifiers:
			e = Expander( mod.name, insert=gtk.Label(icons.DND) )
			R = RNAWidget( mod )
			e.add( R.widget )
			stacker.append( e.widget )

			b = gtk.ToggleButton( icons.VISIBLE_RENDER )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show in render')
			b.set_active( mod.show_render )
			b.connect('toggled', lambda b,m: setattr(m,'show_render',b.get_active()), mod)
			e.header.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.VISIBLE )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show in viewport')
			b.set_active( mod.show_viewport )
			b.connect('toggled', lambda b,m: setattr(m,'show_viewport',b.get_active()), mod)
			e.header.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.VISIBLE_EDITMODE )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show in edit-mode')
			b.set_active( mod.show_in_editmode )
			b.connect('toggled', lambda b,m: setattr(m,'show_in_editmode',b.get_active()), mod)
			e.header.pack_start( b, expand=False )

		self._modifiers_expander.show_all()

	def add_modifier(self,b, combo, ob):
		mtype = combo.get_active_text()
		mod = ob.modifiers.new( name=mtype.lower(), type=mtype )
		self.update_modifiers( ob, force_update=True )

	def add_constraint(self,b, combo, ob):
		mtype = combo.get_active_text()
		cns = ob.constraints.new( type=mtype )
		cns.name = mtype.lower()
		self.update_constraints( ob, force_update=True )

	def reorder_constraint( self, oldindex, newindex, ob ):
		'''
		ob.constraint is missing .insert method!
		workaround use bpy.ops.constraint.move_{up/down}
		TODO need to force ob to be active object
		'''
		name = ob.constraints[ oldindex ].name
		delta = oldindex - newindex
		for i in range( abs(delta) ):
			if delta < 0:
				bpy.ops.constraint.move_down( constraint=name, owner='OBJECT' )
			else:
				bpy.ops.constraint.move_up( constraint=name, owner='OBJECT' )

	def reorder_modifier( self, oldindex, newindex, ob ):
		'''
		ob.modifiers is missing .insert method!
		workaround use bpy.ops.object.modifier_move_{up/down}
		TODO need to force ob to be active object
		'''
		name = ob.modifiers[ oldindex ].name
		delta = oldindex - newindex
		for i in range( abs(delta) ):
			if delta < 0:
				bpy.ops.object.modifier_move_down( modifier=name )
			else:
				bpy.ops.object.modifier_move_up( modifier=name )




	def iterate(self, context):
		self.physics_widget.update_ui( context )
		self.gamepads_widget.update()
		self.wiimotes_widget.update()
		#self.engine.sync( context )

		if '_webcam_' in bpy.data.images:
			img = bpy.data.images['_webcam_']
			if img.bindcode:
				ptr = self.webcam.preview_image.imageData
				self.upload_texture_data( img, ptr )

		if '_kinect_' in bpy.data.images:
			img = bpy.data.images['_kinect_']
			if img.bindcode and self.kinect.PREVIEW_IMAGE:
				ptr = self.kinect.PREVIEW_IMAGE.imageData
				self.upload_texture_data( img, ptr )


	def upload_texture_data( self, img, ptr, width=240, height=180 ):
		## fast update raw image data into texture using image.bindcode
		## the openGL module must not load an external libGL.so/dll
		## BGL is not used here because raw pointers are not supported (bgl.Buffer is expected)

		bind = img.bindcode
		glBindTexture(GL_TEXTURE_2D, bind)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
		glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
		glTexImage2D(
			GL_TEXTURE_2D,		# target
			0, 						# level
			GL_RGB, 				# internal format
			width, 					# width
			height, 				# height
			0, 						# border
			GL_RGB, 				# format
			GL_UNSIGNED_BYTE, 	# type
			ptr						# pixels
		)




################################################
class PhysicsWidget(object):

	def __init__(self, parent, context):
		self.widget = note = gtk.Notebook()
		parent.add( self.widget )

		scn = context.scene

		page = gtk.VBox(); page.set_border_width( 3 )
		note.append_page( page, gtk.Label('settings') )

		s = SimpleSlider(scn.game_settings, name='fps', title='FPS', max=120, tooltip='frames per second', driveable=True)
		page.pack_start(s.widget, expand=False)

		s = SimpleSlider(scn.world, name='ode_ERP', title='ERP', min=0.0001, max=1.0, tooltip='joint error reduction', driveable=True)
		page.pack_start(s.widget, expand=False)

		s = SimpleSlider(scn.world, name='ode_CFM', title='CFM', max=5, tooltip='joint constant mixing force', driveable=True)
		page.pack_start(s.widget, expand=False)

		page = gtk.VBox(); page.set_border_width( 3 )
		note.append_page( page, gtk.Label('damping') )

		s = SimpleSlider(scn.world, name='ode_linear_damping', title='linear', max=2, tooltip='linear damping', driveable=True)
		page.pack_start(s.widget, expand=False)

		s = SimpleSlider(scn.world, name='ode_angular_damping', title='angular', max=2, tooltip='angular damping', driveable=True)
		page.pack_start(s.widget, expand=False)


		page = gtk.VBox(); page.set_border_width( 3 )
		note.append_page( page, gtk.Label('gravity') )

		for i in range(3):
			s = Slider(
				context.scene.world, 
				name='ode_gravity', 
				title='xyz'[i],
				target_index=i,
				min=-20, max=20,
			)
			page.pack_start( s.widget, expand=False )

	def update_ui(self,context):
		#if context.active_object and context.active_object.name != self.selected:
		pass

########################## game pad #######################
class GamepadsWidget(object):
	def update(self):
		sdl.JoystickUpdate()
		for pad in self.gamepads: pad.update()
	def __init__(self, parent, context=None):
		self.gamepads = []
		root = gtk.VBox(); root.set_border_width( 2 )
		parent.add( root )
		note = gtk.Notebook(); root.pack_start( note, expand=True )
		note.set_tab_pos( gtk.POS_BOTTOM )
		for i in range( Gamepad.NUM_DEVICES ):
			pad = Gamepad(i); self.gamepads.append( pad )
			note.append_page( pad.widget, gtk.Label('%s'%i) )


############# Generic Game Device ###############

class GameDevice(object):

	def make_widget(self, device_name):
		self.widget = root = gtk.VBox()
		root.set_border_width(2)

		ex = gtk.Expander('Axes'); ex.set_expanded(True)
		root.pack_start( ex, expand=False )
		box = gtk.VBox(); ex.add( box )
		self.axes_gtk = []
		for i in range(self.naxes):
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
		root.pack_start( ex, expand=False )
		box = gtk.VBox(); ex.add( box )
		self.buttons_gtk = []

		row = gtk.HBox(); row.set_border_width(4)
		box.pack_start( row, expand=False )
		for i in range(self.nbuttons):
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



class Gamepad( GameDevice ):
	NUM_DEVICES = sdl.NumJoysticks()
	#assert NUM_DEVICES
	def update(self):
		for i in range( self.naxes ):
			value = self.dev.GetAxis(i) / 32767.0		# -32768 to 32767
			self.axes[i] = value
			self.axes_gtk[i].set_value(value)
		for i in range( self.nbuttons ):
			value = bool( self.dev.GetButton(i) )
			self.buttons[i] = value
			self.buttons_gtk[i].set_active( value )
		for i in range( self.nhats ):
			self.hats[i] = self.dev.GetHat(i)

		#self.update_drivers()

	def __init__(self,index=0):
		self.index = index
		self.dev = sdl.JoystickOpen(index)
		self.naxes = self.dev.NumAxes()
		self.nbuttons = self.dev.NumButtons()
		self.nhats = self.dev.NumHats()
		self.axes = [ 0.0 ] * self.naxes
		self.buttons = [ False ] * self.nbuttons
		self.hats = [ 0 ] * self.nhats

		self.logic = {}
		self.drivers = []

		self.make_widget('gamepad')




#################### wiimote #################
class WiimoteWrapper( GameDevice ):
	def __init__(self,dev):
		self.dev = dev
		self.index = dev.index
		self.naxes = 3
		self.nbuttons = len(self.dev.buttons)
		self.axes = [ 0.0 ] * self.naxes
		self.buttons = [ False ] * self.nbuttons
		### no hats on wii ##
		self.nhats = 0
		self.hats = [ 0 ] * self.nhats

		self.logic = {}
		self.drivers = []

		self.make_widget('wiimote')

	def update(self):
		for i in range( self.naxes ):
			value = self.dev.force[i] / 255.0
			value -= 0.5
			self.axes[i] = value
			self.axes_gtk[i].set_value(value)
		#for i in range( self.nbuttons ):
		#	value = self.dev.buttons
		#	self.buttons[i] = value
		#	self.buttons_gtk[i].set_active( value )

		#self.update_drivers()


class WiimotesWidget(object):
	def update(self):
		if self.active:
			self.manager.iterate()
			for w in self.wiimotes: w.update()

	def __init__(self, parent, context=None):
		self.active = False
		self.manager = Wiimote.Manager()
		self.wiimotes = [ WiimoteWrapper(dev) for dev in self.manager.wiimotes ]

		self.root = root = gtk.VBox(); root.set_border_width( 2 )
		parent.add( root )
		self.connect_button = b = gtk.Button('connect wiimotes')
		b.connect('clicked', self.connect_wiimotes)
		root.pack_start( b, expand=False )

	def connect_wiimotes(self,b):
		found = self.manager.connect()
		if found:
			self.connect_button.hide()
			self.active = True
			note = gtk.Notebook(); self.root.pack_start( note, expand=True )
			note.set_tab_pos( gtk.POS_BOTTOM )
			for i in range( found ):
				#pad = Gamepad(i); self.gamepads.append( pad )
				a = self.wiimotes[i]
				note.append_page( a.widget, gtk.Label('%s'%i) )
				#w=gtk.Label('yes!')
				#note.append_page( w, gtk.Label('%s'%i) )

			note.show_all()



#####################################
if __name__ == '__main__':
	Pyppet.do_wnck_hack()
	Pyppet.create_ui( bpy.context )	# bpy.context still valid before mainloop
	## run pyppet ##
	Pyppet.mainloop()



