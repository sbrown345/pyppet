# _*_ coding: utf-8 _*_
# Pyppet2
# Jan24, 2012
# by Brett Hart
# http://pyppet.blogspot.com
# License: BSD
VERSION = '1.9.3f'

import os, sys, time, subprocess, threading, math, ctypes
from random import *

## make sure we can import from same directory ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.append( SCRIPT_DIR )



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
import gtk3 as gtk
import SDL as sdl
import fluidsynth as fluid
import openal as al
import fftw

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

import websocket
import json

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


def sort_objects_by_type( objects, types=['MESH','ARMATURE','CAMERA','LAMP','EMPTY','CURVE'] ):
	r = {}
	for type in types: r[type]=[]
	for ob in objects:
		if ob.type in r: r[ob.type].append( ob )
	return r

def save_selection():
	r = {}
	for ob in Pyppet.context.scene.objects: r[ ob.name ] = ob.select
	return r
def restore_selection( state ):
	for name in state:
		Pyppet.context.scene.objects[ name ].select = state[name]

def dump_collada( name, center=False ):
	state = save_selection()
	for ob in Pyppet.context.scene.objects: ob.select = False

	ob = bpy.data.objects[ name ]
	ob.select = True

	#arm = ob.find_armature()		# armatures not working in Three.js ?
	#if arm: arm.select = True

	loc = ob.location
	if center: ob.location = (0,0,0)
	#bpy.ops.wm.collada_export( filepath='/tmp/dump.dae', check_existing=False, selected=True )
	S = Blender.Scene( Pyppet.context.scene )
	#print(S, dir(S))
	S.collada_export( '/tmp/dump.dae', True )
	if center: ob.location = loc
	restore_selection( state )
	return open('/tmp/dump.dae','rb').read()


#####################
class WebSocketServer( websocket.WebSocketServer ):
	buffer_size = 8096
	client = None

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
			self.top_new_client(startsock, address)	# calls new_client()

	def new_client(self): print('new client', self.client)

	_bps_start = None
	_bps = 0
	def update( self, context ):
		if not self.client or not context.active_object: return
		if context.active_object.type != 'MESH': return

		ob = context.active_object

		color = None
		specular = None
		if ob.data.materials:
			mat = ob.data.materials[0]
			r,g,b = mat.diffuse_color
			color = (r,g,b)
			specular = mat.specular_hardness

		loc, rot, scl = ob.matrix_world.decompose()
		loc = loc.to_tuple()
		x,y,z = rot.to_euler(); rot = (x,y,z)
		scl = scl.to_tuple()

		mods = []
		for mod in ob.modifiers:
			if mod.type in ('SUBSURF',) and mod.show_viewport:
				mods.append( mod )
		for mod in mods: mod.show_viewport = False
		data = ob.to_mesh( context.scene, True, "PREVIEW")
		for mod in mods: mod.show_viewport = True

		N = len( ob.data.vertices )
		if N != len( data.vertices ):
			print('vertex count error - some modifier changed vertex count',ob)
			return

		verts = [ 0.0 for i in range(N*3) ]
		data.vertices.foreach_get( 'co', verts )
		bpy.data.meshes.remove( data )

		## optimize ##
		verts = [ round(a,3) for a in verts ]

		subsurf = 0
		for mod in ob.modifiers:
			if mod.type == 'SUBSURF':
				subsurf = mod.levels		# mod.render_levels
				break

		data = json.dumps(
			{
				'name': ob.name,
				'pos': loc,
				'rot' : rot,
				'scl' : scl,
				'verts': verts,
				'subsurf': subsurf,
				'color': color,
				'specular': specular,
			}
		)
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



			########################################################################
			self.CLIENT_SCRIPT = open( os.path.join(SCRIPT_DIR,'client.js'), 'rb' ).read().decode('utf-8')
			h.append( '<script type="text/javascript">%s' %self.CLIENT_SCRIPT )
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

		#if path=='/favicon.ico': pass
		print('httpd reply browser', path)
		f = io.StringIO()

		if path=='/':
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

		elif path.startswith('/objects/'):
			name = path.split('/')[-1]
			if name.endswith('.dae'):
				start_response('200 OK', [('Content-Type','text/xml; charset=utf-8')])
				name = name[ : -4 ]
				if arg == 'center':
					return [ dump_collada(name,center=True) ]
				else:
					return [ dump_collada(name) ]

			elif self.THREE:
				start_response('200 OK', [('Content-Type','text/html; charset=utf-8')])
				f.write( self.get_header(webgl=True) )

			else:	# simple fallback
				start_response('200 OK', [('Content-Type','text/html; charset=utf-8')])
				f.write( self.get_header() )
				ob = bpy.data.objects[ name ]
				f.write('<h4>NAME: %s</h4>'%name)
				f.write('<h4>TYPE: %s</h4>'%ob.type)
				vec = ob.matrix_world.to_translation()
				f.write('<h4>LOCATION: %s</h4>'%vec)

		elif path.startswith('/javascripts/'):
			start_response('200 OK', [('Content-Type','text/javascript; charset=utf-8')])
			abspath = os.path.join( SCRIPT_DIR, path[1:] )
			data = open( abspath, 'rb' ).read()
			return [ data ]

		else:
			start_response('200 OK', [('Content-Type','text/plain; charset=utf-8')])

		return [f.getvalue().encode('utf-8')]




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



class ContextCopy(object):
	def __init__(self, context):
		copy = context.copy()		# returns dict
		for name in copy: setattr( self, name, copy[name] )
		self.blender_has_cursor = False	# extra


class SimpleDND(object):		## simple drag'n'drop API ##
	target = gtk.target_entry_new( 'test',1,gtk.TARGET_SAME_APP )
	def __init__(self):
		self.dragging = False
		self.source = None			# the destination may want to use the source widget directly
		self.object = None
		self._callback = None		# callback the destination should call
		self._args = None

	def make_source(self, a, ob):
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


#########################################################

class Slider(object):
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

class ToggleButton(object):
	def __init__(self, name=None, driveable=True):
		self.name = name

		self.widget = gtk.Frame()
		self.box = gtk.HBox(); self.widget.add( self.box )

		self.button = gtk.ToggleButton( self.name )
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

	def cb_by_index( self, button ):
		vec = getattr( self.target, self.target_path )
		vec[ self.target_index ] = self.cast( button.get_active() )

	def connect( self, object, path=None, index=None, cast=bool ):
		self.target = object
		self.target_path = path
		self.target_index = index
		self.cast = cast
		self.button.connect('toggled', self.cb_by_index)

	def drop_driver(self, wid, context, x, y, time):
		output = DND.object
		self.driver = output.bind( 'UUU', target=self.target, path=self.target_path, index=self.target_index, min=-2, max=2, mode='=' )
		self.driver.gain = 1.0
		self.button.set_label( '%s%s' %(icons.DRIVER,self.name.strip()))



class SimpleSlider(object):
	def __init__(self, object=None, name=None, title=None, value=0, min=0, max=1, border_width=2, driveable=False):
		if title: self.title = title
		else: self.title = name.replace('_',' ')

		if len(self.title) < 20:
			self.widget = gtk.Frame()
			self.modal = row = gtk.HBox()
			row.pack_start( gtk.Label(self.title), expand=False )
		else:
			self.widget = gtk.Frame( self.title )
			self.modal = row = gtk.HBox()
		self.widget.add( row )

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
			DND.make_destination( self.widget )
			self.widget.connect(
				'drag-drop', self.drop_driver,
				object, name
			)

	def drop_driver(self, wid, context, x, y, time, target, path):
		print('on drop')
		output = DND.object
		if path.startswith('ode_'):
			driver = output.bind( 'YYY', target=target, path=path, max=500 )
		else:
			driver = output.bind( 'YYY', target=target, path=path, min=-2, max=2 )

		self.widget.set_label( '%s	(%s%s)' %(self.title, icons.DRIVER, driver.name) )
		self.widget.remove( self.modal )
		self.modal = driver.get_widget( title='', expander=False )
		self.widget.add( self.modal )
		self.modal.show_all()



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

	def __init__(self, frequency=22050, streaming=False):
		#Speaker.Speakers.append( self )
		self.format=al.AL_FORMAT_MONO16
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

		self.max_raw = 0.1
		self.raw_adjustments = [ gtk.Adjustment( value=0, lower=0, upper=1 ) for i in range(n) ]
		self.norm_adjustments = [ gtk.Adjustment( value=0, lower=0, upper=1 ) for i in range(n) ]
		self.adjustments = [ gtk.Adjustment( value=0, lower=0, upper=1 ) for i in range(n) ]

		self.index = 0

	def get_analysis_widget(self):
		root = gtk.VBox()
		root.set_border_width(2)

		ex = gtk.Expander('Spectral Analysis'); ex.set_expanded(True)
		root.pack_start( ex, expand=False )
		box = gtk.VBox(); ex.add( box )

		slider = SimpleSlider( self, name='beats_threshold', value=self.beats_threshold, min=0.5, max=5 )
		box.pack_start( slider.widget, expand=False )


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


		ex = gtk.Expander('Pattern Matching'); ex.set_expanded(True)
		root.pack_start( ex, expand=False )
		box = gtk.VBox(); ex.add( box )
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


			h = max(raw)
			if h > self.max_raw:
				self.max_raw = h
				print('new max raw', h)

			mult = 1.0 / self.max_raw
			#if self.max_raw > 1.0: self.max_raw *= 0.99	# TODO better normalizer

			#self.raw_bands = [ power*mult for power in raw ]	# drivers fail if pointer is lost
			#for i,power in enumerate( self.raw_bands ):
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
		b = gtk.ToggleButton( icons.MICROPHONE )
		b.set_tooltip_text( 'toggle microphone' )
		b.connect('toggled', self.toggle_capture)
		root.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.SINE_WAVE )
		b.set_tooltip_text( 'toggle spectral analysis' )
		b.set_active( self.analysis )
		b.connect('toggled', lambda b,s: setattr(s,'analysis',b.get_active()), self)
		root.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.SPEAKER )
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

	def cb_drop_driver(self, wid, context, x, y, time, target, path, index, page):
		print('on drop')
		output = DND.object
		#driver = output.bind( 'XXX', target=self.object, path=path, index=index )
		if path.startswith('ode_'):
			driver = output.bind( 'XXX', target=target, path=path, index=index, max=500 )
		else:
			driver = output.bind( 'XXX', target=target, path=path, index=index )
		widget = driver.get_widget()
		page.pack_start( widget, expand=False )
		widget.show_all()


	def vector_widget( self, ob, name, title=None, expanded=True ):
		drivers = Driver.get_drivers(ob.name, name)	# classmethod

		vec = getattr(ob,name)

		if title: ex = gtk.Expander(title)
		else: ex = gtk.Expander(name)
		ex.set_expanded( expanded )

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

		return ex

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

			sw = gtk.ScrolledWindow()
			note.append_page( sw, gtk.Label(icons.TRANSFORM) )
			sw.set_policy(True,True)
			root = gtk.VBox(); root.set_border_width( 6 )
			sw.add_with_viewport( root )
			nice = {
				'location':'Location', 'scale':'Scale', 'rotation_euler':'Rotation',
			}
			tags='location scale rotation_euler'.split()
			for i,tag in enumerate(tags):
				root.pack_start(
					self.vector_widget(ob,tag, title=nice[tag], expanded=i is 0), 
					expand=False
				)

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




			else:
				############# physics driver forces ##############
				sw = gtk.ScrolledWindow()
				note.append_page( sw, gtk.Label(icons.FORCES) )
				sw.set_policy(True,True)
				root = gtk.VBox(); root.set_border_width( 6 )
				sw.add_with_viewport( root )
				nice = {
					'ode_global_force':'Global Force', 'ode_local_force':'Local Force',
					'ode_global_torque':'Global Torque', 'ode_local_torque':'Local Torque',
				}
				tags='ode_local_force ode_local_torque ode_global_force ode_local_torque'.split()
				for i,tag in enumerate(tags):
					root.pack_start(
						self.vector_widget(ob,tag, title=nice[tag], expanded=i is 0), 
						expand=False
					)


				sw = gtk.ScrolledWindow()
				note.append_page( sw, gtk.Label( icons.CONSTANT_FORCES ) )
				sw.set_policy(True,True)
				root = gtk.VBox(); root.set_border_width( 6 )
				sw.add_with_viewport( root )
				nice = {
					'ode_constant_global_force':'Constant Global Force', 
					'ode_constant_local_force':'Constant Local Force',
					'ode_constant_global_torque':'Constant Global Torque', 
					'ode_constant_local_torque':'Constant Local Torque',
				}
				tags='ode_constant_global_force ode_constant_local_force ode_constant_global_torque ode_constant_local_torque'.split()
				for i,tag in enumerate(tags):
					slider = Slider( ob, tag, min=-420, max=420 )
					root.pack_start( slider.widget, expand=False )


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

				s = Slider(ob, 'ode_mass', min=0.001, max=10.0)
				root.pack_start(s.widget, expand=False)
				s = Slider(ob, 'ode_linear_damping', min=0.0, max=1.0)
				root.pack_start(s.widget, expand=False)
				s = Slider(ob, 'ode_angular_damping', min=0.0, max=1.0)
				root.pack_start(s.widget, expand=False)

				s = Slider(
					ob, 'ode_force_driver_rate', 
					title='%s driver rate' %icons.FORCES, 
					min=0.0, max=1.0
				)
				root.pack_start(s.widget, expand=False)


				sw = gtk.ScrolledWindow()
				label = gtk.Label( icons.JOINT )
				note.append_page( sw, label )
				sw.set_policy(True,True)
				root = gtk.VBox(); root.set_border_width( 6 )
				sw.add_with_viewport( root )
				DND.make_destination( label )
				label.connect( 'drag-drop', self.cb_drop_joint, root )

			self.modal.show_all()



	def cb_drop_joint(self, wid, context, x, y, time, page):
		#widget = DND.callback( self.object )
		wrap = DND.object
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

		output = DND.object
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

		wrap = DND.object
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

class PyppetAPI(object):
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


##########################################################
class App( PyppetAPI ):
	def exit(self, arg):
		self.audio.exit()
		self.active = False
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

	# bpy.context workaround #
	def sync_context(self, region):
		#if self.recording:	# works but objects stick
		#	print('recording.........')
		#	bpy.ops.anim.keyframe_insert_menu( type='LocRot' )

		self.context = ContextCopy( bpy.context )
		self.lock.acquire()
		while gtk.gtk_events_pending():	# required to make callbacks safe
			gtk.gtk_main_iteration()
		self.lock.release()

	def toggle_overlays( self, button ):
		if button.get_active():
			for o in self.overlays: o.enable()
			for com in self.components: com.active = False
		else:
			for o in self.overlays: o.disable()
			for com in self.components: com.active = True


	def __init__(self):
		self.reset_models()
		self.recording = False
		self.selected = None
		self.active = True
		self.overlays = []
		self.components = []
		self.bwidth = 640
		self.bheight = 480
		self.lock = threading._allocate_lock()

		self.server = Server()
		self.client = Client()
		self.websocket_server = WebSocketServer( listen_port=8081 )
		self.websocket_server.start()

		self.audio = AudioThread()
		self.audio.start()

		self.context = ContextCopy( bpy.context )
		for area in bpy.context.screen.areas:		#bpy.context.window.screen.areas:
			if area.type == 'PROPERTIES':
				#area.width = 240		# readonly
				pass
			elif area.type == 'VIEW_3D':
				for reg in area.regions:
					if reg.type == 'WINDOW':
						## only POST_PIXEL is thread-safe and drag'n'drop safe  (NOT!) ##
						self._handle = reg.callback_add( self.sync_context, (reg,), 'PRE_VIEW' )
						break

	def start_record(self):
		self.recording = True
		self._rec_start_frame = self.context.scene.frame_current
		for ob in self.context.selected_objects:
			ob.animation_data_clear()
	def end_record(self):
		self.recording = False
		for name in ENGINE.objects:
			w = ENGINE.objects[ name ]
			print(name, w.recbuffer)


	def toggle_record( self, button ):
		if button.get_active(): self.start_record()
		else: self.end_record()


	def get_playback_widget(self):
		frame = gtk.Frame()
		root = gtk.HBox(); frame.add( root )

		b = gtk.ToggleButton( icons.PLAY )
		b.connect('toggled', lambda b: bpy.ops.screen.animation_play() )
		root.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.RECORD )
		b.connect('toggled', self.toggle_record )
		#b.connect('toggled', lambda b,s: setattr(s.context.scene.tool_settings,'use_keyframe_insert_auto',b.get_active()), self )
		#b.set_active( self.context.scene.tool_settings.use_keyframe_insert_auto )
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



	def create_ui(self, context):
		win = gtk.Window()
		win.set_size_request( 640, 480 )
		win.set_title( 'Pyppet '+VERSION )
		self.root = root = gtk.VBox()
		win.add( root )

		self.header = gtk.HBox()
		self.header.set_border_width(2)
		root.pack_start(self.header, expand=False)

		self.popup = Popup()
		b = gtk.ToggleButton( icons.POPUP )
		b.connect('toggled',self.popup.toggle_popup)
		self.header.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.OVERLAY )
		b.connect('toggled',self.toggle_overlays)
		self.header.pack_start( b, expand=False )

		self.header.pack_start( gtk.Label() )

		s = gtk.Switch()
		s.connect('button-press-event', self.cb_toggle_physics )
		s.set_tooltip_text( 'toggle physics' )
		self.header.pack_start( s, expand=False )
		b = gtk.ToggleButton( icons.PLAY_PHYSICS )
		b.connect('toggled', lambda b: ENGINE.toggle_pause(b.get_active()))
		self.header.pack_start( b, expand=False )

		self.header.pack_start( gtk.Label() )


		widget = self.audio.microphone.get_widget()
		self.header.pack_start( widget, expand=False )

		self.header.pack_start( gtk.Label() )

		self._frame = gtk.Frame()
		self._modal = gtk.Label()
		self._frame.add( self._modal )
		self.header.pack_start( self._frame )

		self.header.pack_start( gtk.Label() )

		self.header.pack_start( self.get_playback_widget() )

		self.body = gtk.HBox(); root.pack_start( self.body )
		self.canvas = gtk.Fixed()
		self.body.pack_start( self.canvas, expand=False )

		self.socket = gtk.Socket()
		#self.socket.set_size_request( 640, 480 )
		self.blender_container = eb = gtk.EventBox()
		eb.add( self.socket )
		self.canvas.put( eb, 0,0 )
		self.socket.connect('plug-added', self.on_plug)

		####################################
		self.footer = gtk.Frame()
		self.root.pack_start( self.footer, expand=False )
		w = self.audio.synth.channels[0].get_widget()
		self.footer.add( w )

		############## overlays #############
		ui = PropertiesUI( self.canvas, self.lock, context )
		self.components.append( ui )
		self.overlays += ui.overlays

		ui = OutlinerUI( self.canvas, self.lock, context )
		self.components.append( ui )
		self.overlays += ui.overlays

		win.connect('destroy', self.exit )
		win.show_all()

		while gtk.gtk_events_pending(): gtk.gtk_main_iteration()
		print('ready to xembed...')
		xid = self.get_window_xid( 'Blender' )
		self.socket.add_id( xid )

		for o in self.overlays: o.disable()

	def on_plug(self, args):
		print( 'on plug...' )
		win = self.socket.get_plug_window()
		print(win)
		#win.set_title('stolen window')
		#self.socket.show_all()
		self.bwidth = win.get_width() - 420
		self.bheight = win.get_height() - 340
		self.socket.set_size_request( self.bwidth, self.bheight )
		#Blender.window_expand()
		Blender.window_resize( self.bwidth, self.bheight )		# required - replaces wnck unshade hack
		#bpy.ops.wm.window_fullscreen_toggle()
		Blender.window_lower()


	def get_window_xid( self, name ):
		p =os.popen('xwininfo -int -name %s' %name)
		data = p.read().strip()
		p.close()
		if data.startswith('xwininfo: error:'): return None
		elif data:
			lines = data.splitlines()
			return int( lines[0].split()[3] )


	def mainloop(self):
		C = Blender.Context( bpy.context )
		while self.active:

			if DND.dragging and False:	# not safe with drag and drop
				print('outer gtk iter')
				Blender.iterate(C, draw=False)
				if gtk.gtk_events_pending():
					#print('gtk update', time.time())
					#self.lock.acquire()
					while gtk.gtk_events_pending():
						gtk.gtk_main_iteration()
					#self.lock.release()

			#print( 'MAINLOOP', bpy.context, bpy.context.scene )	# bpy.context is not in sync after first Blender.iterate(C)
			#print( 'MAINLOOP', bpy.data.scenes, bpy.data.scenes[0] )	# this remains valid
			#print( bpy.data.objects )	# this also remains valid

			#if not DND.dragging:
			if True:
				Blender.iterate(C)
				if not self.active: break
				#print('mainloop', self.context, self.context.scene)	# THIS TRICK WORKS!
				#bpy.context = self.context	#  this wont work

				win = Blender.Window( self.context.window )
				# grabcursor on click and drag (view3d only)
				#print(win, win.winid, win.grabcursor, win.windowstate, win.modalcursor)
				self.context.blender_has_cursor = bool( win.grabcursor )
				if self.context.blender_has_cursor: pass #print('blender has cursor')

				#print(win.active)
				#Blender.blender.wm_window_lower( win )	# useless
				#win.active = 1	#  useless
				#win.windowstate = 0
				#Blender.blender.GHOST_setAcceptDragOperation( win.ghostwin, 0 )
				#Blender.blender.GHOST_SetWindowOrder(win.ghostwin, Blender.blender.GHOST_kWindowOrderBottom)

				#Blender.blender.GHOST_InvalidateWindow(win.ghostwin)
				#Blender.blender.GHOST_SetWindowState(win.ghostwin, Blender.blender.GHOST_kWindowStateNormal)

				## force redraw in VIEW_3D ##
				for area in self.context.window.screen.areas:		#bpy.context.window.screen.areas:
					if area.type == 'VIEW_3D':
						for reg in area.regions:
							if reg.type == 'WINDOW':
								reg.tag_redraw()	# bpy.context valid from redraw callbacks
								break

			DriverManager.update()
			self.audio.update()		# updates gtk widgets

			if self.context.scene.frame_current != int(self._current_frame_adjustment.get_value()):
				self._current_frame_adjustment.set_value( self.context.scene.frame_current )

			self.update_selected_widget()

			for o in self.overlays:
				o.update( self.context.window.screen, self.bwidth, self.bheight )

			for com in self.components: com.iterate( self.context )
			self.popup.update( self.context )

			models = self.entities.values()
			for mod in models: mod.update_ui( self.context )

			if ENGINE.active and not ENGINE.paused:
				ENGINE.sync( self.context, self.recording )
				for mod in models:
					mod.update( self.context )

			self.server.update( self.context )
			self.client.update( self.context )
			self.websocket_server.update( self.context )

			#if self.recording:
			#	print('recording...')
			#	bpy.ops.anim.keyframe_insert_menu( type='LocRot' )

			#if not DND.dragging:
			#Blender.iterate(C, self.lock)

	def update_selected_widget(self):
		if self.context.active_object and self.context.active_object.name != self.selected:
			self.selected = self.context.active_object.name
			self._frame.remove( self._modal )
			self._modal = root = gtk.HBox()
			self._frame.add( root )
			ob = bpy.data.objects[ self.selected ]
			#root.pack_start( gtk.Label(ob.name), expand=False )

			if ob.type == 'ARMATURE':
				b = gtk.ToggleButton( icons.MODE )
				b.set_tooltip_text('toggle pose mode')
				root.pack_start( b, expand=False )
				b.set_active( self.context.mode=='POSE' )
				b.connect('toggled', self.toggle_pose_mode)

				if ob.name not in self.entities:
					biped = self.GetBiped( ob )
					b = gtk.Button( icons.BIPED )
					root.pack_start( b, expand=False )
					b.connect('clicked', lambda b,bi: [b.hide(), bi.create()], biped)

			else:
				b = gtk.ToggleButton( icons.BODY )
				b.set_tooltip_text('toggle body physics')
				root.pack_start( b, expand=False )
				b.set_active( ob.ode_use_body )
				b.connect('toggled', lambda b,o: setattr(o,'ode_use_body',b.get_active()), ob)

				b = gtk.ToggleButton( icons.COLLISION )
				b.set_tooltip_text('toggle collision')
				root.pack_start( b, expand=False )
				b.set_active( ob.ode_use_collision )
				b.connect('toggled', lambda b,o: setattr(o,'ode_use_collision',b.get_active()), ob)

				b = gtk.ToggleButton( icons.GRAVITY )
				b.set_tooltip_text('toggle gravity')
				root.pack_start( b, expand=False )
				b.set_active( ob.ode_use_gravity )
				b.connect('toggled', lambda b,o: setattr(o,'ode_use_gravity',b.get_active()), ob)

			root.show_all()

	def toggle_pose_mode(self,button):
		if button.get_active():
			bpy.ops.object.mode_set( mode='POSE' )
		else:
			bpy.ops.object.mode_set( mode='OBJECT' )


######## Pyppet Singleton #########
Pyppet = App()

#bpy.types.Scene.use_gtk = bpy.props.BoolProperty(
#	name='enable gtk', 
#	description='toggle GTK3',
#	default=False,
#	update=lambda a,b: Pyppet.toggle_gtk(a,b)
#)

#################################
class Overlay(object):
	def enable(self):
		self.active = self.show = True
		self.container.show()
	def disable(self):
		self.active = self.show = False
		self.container.hide()

	def __init__(self, widget, canvas, area, region, min_width=100):
		self.active = False
		self.show = False
		self.widget = widget
		self.canvas = canvas
		self.area = area
		self.region = region
		self.min_width = min_width

		self.container = gtk.EventBox()
		self.container.add( widget )
		self.canvas.put( self.container, 0,0 )

	def update(self, screen, width, height):
		if not self.active: return

		#self.container.set_state_flags( gtk.STATE_FLAG_FOCUSED )

		for area in screen.areas:		#bpy.context.window.screen.areas:
			if area.type == self.area:		# VIEW_3D, INFO
				for reg in area.regions:
					if reg.type == self.region:
						if reg.width < self.min_width:
							self.show = False
							self.container.hide()
						elif not self.show:
							self.show = True
							self.container.show()

						self.widget.set_size_request( reg.width-2, reg.height )
						###########################################
						r = Blender.Region( reg )
						rct = r.winrct	# blender window space
						#print(rct.ymin, rct.ymax)
						self.canvas.move( self.container, rct.xmin+2, height - rct.ymax )
						#self.canvas.move( self.container, 1440, height - rct.ymax )
						return

		## hide if area not found ##
		self.show = False
		self.container.hide()

class Component(object):
	def create_widget(self): pass
	def iterate(self, context): pass
	def __init__(self,canvas, lock, context):
		self.canvas = canvas
		self.lock = lock
		self.overlays = []
		self.create_widget(context)	# overloaded

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


class OutlinerUI( Component ):
	def create_widget(self, context):
		self.objects = {}	# name : ObjectWrapper
		self.meshes = {}

		sw = gtk.ScrolledWindow()
		self.lister = box = gtk.VBox()
		box.set_border_width(6)
		sw.add_with_viewport( box )
		sw.set_policy(True,False)

		o = Overlay( sw, self.canvas, 'OUTLINER', 'WINDOW', min_width=100 )
		self.overlays.append( o )


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




class PropertiesUI( Component ):
	def new_page( self, title ):
		sw = gtk.ScrolledWindow()
		self.notebook.append_page( sw, gtk.Label(title) )
		box = gtk.VBox()
		sw.add_with_viewport( box )
		sw.set_policy(True,False)
		return box

	def create_widget(self, context):
		self.notebook = gtk.Notebook()
		#self.notebook.set_tab_pos( gtk.POS_RIGHT )
		o = Overlay( self.notebook, self.canvas, 'PROPERTIES', 'WINDOW', min_width=220 )
		self.overlays.append( o )

		box = self.new_page( icons.WEBCAM )	# webcam
		widget = Webcam.Widget( box )
		self.webcam = widget.webcam
		self.webcam.start_thread( self.lock )
		bpy.data.images.new( name='webcam', width=320, height=240 )

		box = self.new_page( icons.KINECT )		# kinect
		widget = Kinect.Widget( box )
		self.kinect = widget.kinect
		widget.start_threads( self.lock )
		bpy.data.images.new( name='kinect', width=320, height=240 )

		box = self.new_page( icons.GAMEPAD )	# gamepad
		self.gamepads_widget = GamepadsWidget( box )

		box = self.new_page( icons.WIIMOTE )	# wiimote
		self.wiimotes_widget = WiimotesWidget( box )

		box = self.new_page( icons.MICROPHONE )	# microphone
		widget = Pyppet.audio.microphone.get_analysis_widget()
		box.pack_start( widget )

		box = self.new_page( icons.PHYSICS )
		self.engine = Physics.ENGINE
		self.physics_widget = PhysicsWidget( box, context )

	def iterate(self, context):
		self.physics_widget.update_ui( context )
		self.gamepads_widget.update()
		self.wiimotes_widget.update()
		#self.engine.sync( context )

		img = bpy.data.images['webcam']
		if img.bindcode:
			ptr = self.webcam.preview_image.imageData
			self.upload_texture_data( img, ptr )

		img = bpy.data.images['kinect']
		if img.bindcode and self.kinect.PREVIEW_IMAGE:
			ptr = self.kinect.PREVIEW_IMAGE.imageData
			self.upload_texture_data( img, ptr )


	def upload_texture_data( self, img, ptr, width=320, height=240 ):
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





class PhysicsWidget(object):

	def __init__(self, parent, context):
		self.engine = Physics.ENGINE
		root = gtk.VBox(); root.set_border_width( 3 )
		parent.add( root )

		#b = gtk.CheckButton('physics active')
		#b.set_active( bool(self.engine.active) )
		#b.connect('toggled', lambda button: Pyppet.toggle_physics(button.get_active()) )
		#root.pack_start( b, expand=False )
		#root.pack_start( gtk.HSeparator(), expand=True )

		s = Slider(context.scene.game_settings, 'fps')
		root.pack_start(s.widget, expand=False)

		s = Slider(context.scene.world, 'ode_ERP', min=0.0001, max=1.0)
		root.pack_start(s.widget, expand=False)

		s = Slider(context.scene.world, 'ode_CFM')
		root.pack_start(s.widget, expand=False)

		s = Slider(context.scene.world, 'ode_linear_damping')
		root.pack_start(s.widget, expand=False)

		s = Slider(context.scene.world, 'ode_angular_damping')
		root.pack_start(s.widget, expand=False)

		root.pack_start( gtk.HSeparator(), expand=True )

		s = Slider(context.scene.world, 'ode_gravity', title='Gravity')
		root.pack_start(s.widget, expand=False)


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


############## Device Output ##############
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
		if expander: ex = gtk.Expander( title ); ex.set_expanded(True)
		else: ex = gtk.Frame( title )
		ex.set_border_width(4)
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

			#b = gtk.Button('✗')
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

	## TODO deprecate wnck-helper hack ##
	wnck_helper = os.path.join(SCRIPT_DIR, 'wnck-helper.py')
	assert os.path.isfile( wnck_helper )
	os.system( wnck_helper )

	## run pyppet ##
	Pyppet.create_ui( bpy.context )	# bpy.context still valid before mainloop
	Pyppet.mainloop()



