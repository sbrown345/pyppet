## Server Module ##
## TODO websocket client to server

import os, sys, time

## make sure we can import and load data from same directory ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.append( SCRIPT_DIR )

################# Server ################
import wsgiref
import wsgiref.simple_server
import io, socket, select, pickle, urllib
import urllib.request
import urllib.parse

from websocket import websockify as websocket
import json

import bpy, mathutils
from bpy.props import *


from core import *
from random import *

DEFAULT_STREAMING_LEVEL_OF_INTEREST_MAX_DISTANCE = 20.0

## hook into external API's ##
#bpy = NotImplemented
Pyppet = NotImplemented
def set_api( blender_api=None, user_api=None ):
	global Pyppet
	Pyppet = user_api
##############################

if 'pyppet-server' in sys.argv:
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		s.connect(("gmail.com",80))	# may fail if not connected to internet
		HOST_NAME = s.getsockname()[0]
		s.close()
	except:
		HOST_NAME = socket.gethostbyname(socket.gethostname())
	del s

else:
	## it depends on the linux, but most likely socket.gethostbyname is going to return the local address,
	## not the internet address we need ##
	HOST_NAME = socket.gethostbyname(socket.gethostname())

#HOST_NAME = '192.168.0.14'
print('[HOST_NAME: %s]'%HOST_NAME)


##################### PyRNA ###################
bpy.types.Object.webgl_lens_flare_scale = FloatProperty(
    name="lens flare scale", description="size of lens flare for webGL client", 
    default=1.0)


bpy.types.Object.webgl_progressive_textures = BoolProperty( 
	name='use progressive texture loading in webGL client', 
	default=False 
)

bpy.types.Object.webgl_stream_mesh = BoolProperty( name='stream mesh to webGL client', default=False )

bpy.types.Object.webgl_auto_subdivison = BoolProperty( name='auto subdivide', default=False )

bpy.types.Object.webgl_normal_map = FloatProperty(
    name="normal map scale", description="normal map scale for webGL client", 
    default=0.75)

## ID of zero is a dead object ##
bpy.types.Object.UID = IntProperty(
    name="unique ID", description="unique ID for webGL client", 
    default=0, min=0, max=2**14)

def get_object_by_UID( uid ):
	if type(uid) is str: uid = int( uid.replace('_','') )
	ids = []
	ob = None
	for o in bpy.data.objects:
		if o.UID:
			if o.UID == uid: ob = o
			ids.append( o.UID )
			print(o.name, o.UID)

	assert len(ids) == len( set(ids) )

	if not ob: print('UID not found', uid)
	return ob

def UID( ob ):
	'''
	sets and returns simple unique ID for object.
	note: when merging data, need to check all ID's are unique
	note: copy object duplicates the UID
	'''
	ids = [o.UID for o in bpy.data.objects]
	if not ob.UID or ids.count( ob.UID ) > 1:
		ob.UID = max( ids ) + 1
	assert ob.UID
	return ob.UID

#--------------------------------------------------

def dump_collada_pure_base_mesh( name, center=False ):	# NOT USED
	state = save_selection()
	for ob in bpy.context.scene.objects: ob.select = False
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
	S = Blender.Scene( bpy.context.scene )
	S.collada_export(  
			url, 
			0, #apply modifiers 
			0, #mesh-view/render
			1, #selected only
			0, #include children
			0, #include armatures,
			1, #deform bones only
			0, #active uv only
			1, #include uv textures
			1, #include material textures
			1, #use tex copies
			0, #use object instances
			0, #sort by name
			0, #second lift compatible
			)



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

bpy.types.Object.is_lod_proxy = BoolProperty(
	name='is LOD proxy',
	description='prevents the LOD proxy from being streamed directly to WebGL client',
	default=False)


## optimize the collada by using this blank material ##
if '_blank_material_' not in bpy.data.materials:
	BLANK_MATERIAL = bpy.data.materials.new(name='_blank_material_')
	BLANK_MATERIAL.diffuse_color = [1,1,1]
BLANK_MATERIAL = bpy.data.materials[ '_blank_material_' ]

def _dump_collada_data_helper( data ):
	data.transform( SWAP_MESH )	# flip YZ for Three.js
	data.calc_normals()
	for i,mat in enumerate(data.materials): data.materials[ i ] = None
	if data.materials: data.materials[0] = BLANK_MATERIAL
	else: data.materials.append( BLANK_MATERIAL )


def dump_collada( ob, center=False, hires=False ):
	assert bpy.context.mode !='EDIT'
	name = ob.name
	state = save_selection()
	uid = UID( ob )
	print('Object:%s UID:%s'%(ob,uid))
	for o in bpy.context.scene.objects: o.select = False

	mods = []	# to restore later #
	for mod in ob.modifiers:
		#if mod.type in ('ARMATURE', 'MULTIRES', 'SUBSURF') and mod.show_viewport:
		if mod.type in ('ARMATURE', 'SUBSURF') and mod.show_viewport:
			mod.show_viewport = False
			mods.append( mod )	

	if not hires and len(ob.data.vertices) >= 12:	# if lowres LOD
		print('[ DUMPING LOWRES ]')

		url = '/tmp/%s(lowres).dae' %name

		## check for pre-generated proxy ##
		proxy = None
		for child in ob.children:
			if child.is_lod_proxy:
				proxy = child; break
		if not proxy:	# otherwise generate a new one #
			data = create_LOD( ob )
			_dump_collada_data_helper( data )

			proxy = bpy.data.objects.new(name='__%s__'%uid, object_data=data)
			bpy.context.scene.objects.link( proxy )
			proxy.is_lod_proxy = True
			proxy.draw_type = 'WIRE'

			bpy.ops.object.mode_set( mode='OBJECT' )

			active = bpy.context.scene.objects.active
			proxy.select = True
			bpy.context.scene.objects.active = proxy	# required by smart_project
			bpy.ops.uv.smart_project()		# no need to be in edit mode
			proxy.data.update()			# required
			#bpy.ops.object.shade_smooth()
			bpy.context.scene.objects.active = active


		proxy.hide_select = False	# if True this blocks selecting even here in python!
		proxy.parent = None	# make sure to clear parent before collada export
		proxy.matrix_world = ob.matrix_world.copy()		
		proxy.select = True
		proxy.name = '__%s__'%uid
		assert '.' not in proxy.name	# ensure name is unique
		## ctypes hack avoids polling issue ##
		Blender.Scene( bpy.context.scene ).collada_export(  
			url, 
			0, #apply modifiers 
			0, #mesh-view/render
			1, #selected only
			0, #include children
			0, #include armatures,
			1, #deform bones only
			0, #active uv only
			1, #include uv textures
			1, #include material textures
			1, #use tex copies
			0, #use object instances
			0, #sort by name
			0, #second lift compatible
			)



		proxy.name = 'LOD'	# need to rename

		proxy.matrix_world.identity()
		proxy.rotation_euler.x = -math.pi/2
		proxy.parent = ob
		proxy.hide_select = True


	else: 	# hires
		print('[ DUMPING HIRES ]')
		url = '/tmp/%s(hires).dae' %name

		data = ob.to_mesh(Pyppet.context.scene, True, "PREVIEW")
		_dump_collada_data_helper( data )

		############## create temp object for export ############
		tmp = bpy.data.objects.new(name='__%s__'%uid, object_data=data)
		assert '.' not in tmp.name	# ensure name is unique
		Pyppet.context.scene.objects.link( tmp )
		tmp.matrix_world = ob.matrix_world.copy()
		tmp.select = True

		## ctypes hack avoids polling issue ##
		Blender.Scene( Pyppet.context.scene ).collada_export( 
			url, 
			0, #apply modifiers 
			0, #mesh-view/render
			1, #selected only
			0, #include children
			0, #include armatures,
			1, #deform bones only
			0, #active uv only
			1, #include uv textures
			1, #include material textures
			1, #use tex copies
			0, #use object instances
			0, #sort by name
			0, #second lift compatible
			)

		## clean up ##
		Pyppet.context.scene.objects.unlink(tmp)
		tmp.user_clear()
		bpy.data.objects.remove(tmp)

	#__________________________________________________________________#
	for mod in mods: mod.show_viewport = True  # restore modifiers
	restore_selection( state )
	return open(url,'rb').read()


def create_LOD( ob, ratio=0.2 ):
	# TODO generate mapping, cache #
	mod = ob.modifiers.new(name='temp', type='DECIMATE' )
	mod.ratio = ratio
	mesh = ob.to_mesh(Pyppet.context.scene, True, "PREVIEW")
	ob.modifiers.remove( mod )
	return mesh



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
			slider = Slider( self, name=name, title='', max=10.0, driveable=True )
			root.pack_start( slider.widget, expand=False )

		return root

class WebGL(object):
	def __init__(self):
		self.effects = []
		group = [
			FX('fxaa', True),
			#self.effects.append( FX('ssao', False) )
			FX('dots', False, scale=1.8),
			FX('vignette', True, darkness=1.0),
			FX('bloom', True, opacity=0.333),
			FX('glowing_dots', False, scale=0.23),
		]
		self._page1 = list( group )
		self.effects += group

		group = [
			FX('blur_horizontal', True, r=0.5),
			FX('blur_vertical', True, r=0.5),
			FX('noise', False, nIntensity=0.01, sIntensity=0.5),
			FX('film', False, nIntensity=10.0, sIntensity=0.1),
		]
		self._page2 = list( group )
		self.effects += group

	def get_fx_widget_page1(self):
		root = gtk.VBox()
		root.set_border_width(3)
		for fx in self._page1: root.pack_start( fx.get_widget(), expand=False )
		return root

	def get_fx_widget_page2(self):
		root = gtk.VBox()
		root.set_border_width(3)
		for fx in self._page2: root.pack_start( fx.get_widget(), expand=False )
		return root

#------------------------------------------------------------------------------


#####################
class Player( object ):
	MAX_VERTS = 2000

	def __init__(self, ip, websocket=None):
		'''
		self.objects is a list of objects that the client should know about from its message stream,
		it can also be used as a cache.
		'''
		self.address = ip
		self.websocket = websocket

		self.objects = []	## list of objects client in client message stream

		## TODO expose these options with GTK
		self.camera_randomize = False
		self.camera_focus = 1.5
		self.camera_aperture = 0.15
		self.camera_maxblur = 1.0
		self.godrays = False


		if ip not in bpy.data.objects:
			print('creating new player gizmos')
			a = bpy.data.objects.new(name=ip, object_data=None)
			Pyppet.context.scene.objects.link( a )
			a.empty_draw_size = DEFAULT_STREAMING_LEVEL_OF_INTEREST_MAX_DISTANCE

			b = bpy.data.objects.new(name=ip+'-half_degraded', object_data=None)
			Pyppet.context.scene.objects.link( b )
			b.empty_draw_size = DEFAULT_STREAMING_LEVEL_OF_INTEREST_MAX_DISTANCE*2
			b.parent = a

			c = bpy.data.objects.new(name=ip+'-fully_degraded', object_data=None)
			Pyppet.context.scene.objects.link( c )
			c.empty_draw_size = DEFAULT_STREAMING_LEVEL_OF_INTEREST_MAX_DISTANCE*4
			c.parent = a

			for ob in (a,b,c):
				ob.empty_draw_type = 'SPHERE'
				ob.lock_location = [True]*3
				ob.lock_scale = [True]*3
				ob.lock_rotation = [True]*3

		self.streaming_boundry = bpy.data.objects[ ip ]
		self.streaming_boundry_half_degraded = bpy.data.objects[ ip+'-half_degraded' ]
		self.streaming_boundry_fully_degraded = bpy.data.objects[ ip+'-fully_degraded' ]
		self.location = self.streaming_boundry.location

	def set_location(self, loc):
		self.location.x = loc[0]
		self.location.y = loc[1]
		self.location.z = loc[2]

	def get_streaming_max_distance(self, degraded=False ):
		if degraded == 'half':
			return self.streaming_boundry_half_degraded.empty_draw_size
		elif degraded == 'full':
			return self.streaming_boundry_fully_degraded.empty_draw_size
		else:
			return self.streaming_boundry.empty_draw_size

	################################ convert to stream #######################################
	def create_stream_message( self, context ):
		'''
		packs all data in message stream into a dictionary,
		the dict is converted into json and later streamed to the client.
		'''
		#ip,port = sock.getsockname()
		#assert ip in self.clients
		#player_location = mathutils.Vector( self.clients[ip] )
		#player = GameManager.clients[ self.address ]

		msg = { 
			'meshes':{}, 
			'lights':{}, 
			'metas':{},
			'curves':{},
			'FX':{},
			'camera': {
				'rand':self.camera_randomize,
				'focus':self.camera_focus,
				'aperture':self.camera_aperture,
				'maxblur':self.camera_maxblur,
			},
			'godrays': self.godrays,
		}

		streaming_meshes = []
		far_objects = []		# far objects the player has not loaded yet

		for ob in context.scene.objects:
			if ob.is_lod_proxy: continue
			if ob.type not in ('CURVE','META','MESH','LAMP'): continue
			if ob.type=='MESH' and not ob.data.uv_textures:
				#print('WARN: not streaming mesh without uvmapping', ob.name)
				continue	# UV's required to generate tangents

			## do not stream objects too far from camera/player ##
			## if something is far, do not stream mesh data ##
			far = False
			distance = (self.location - ob.matrix_world.to_translation()).length
			if distance > self.get_streaming_max_distance():
				far = True
				if ob not in self.objects:
					if far_objects:
						far_objects.append( ob )
						continue
					else:
						far_objects.append( ob )	# let far obs slip thru one at a time
				elif distance < self.get_streaming_max_distance( degraded='half' ):
					if random() > 0.5: continue
				elif distance < self.get_streaming_max_distance( degraded='full' ):
					if random() > 0.25: continue
				else:
					continue

			if ob not in self.objects:		# keep track of what objects player knows about
				self.objects.append( ob )

			loc, rot, scl = (SWAP_OBJECT*ob.matrix_world).decompose()
			loc = loc.to_tuple()
			scl = scl.to_tuple()
			rot = (rot.w, rot.x, rot.y, rot.z)
			pak = { 'pos':loc, 'rot':rot, 'scl':scl }

			if ob.type == 'CURVE':
				msg[ 'curves' ][ '__%s__'%UID(ob) ] = pak
				pak[ 'splines' ] = splines = []
				pak[ 'segments_v' ] = ob.data.bevel_resolution
				pak[ 'radius' ] = ob.data.bevel_depth

				for spline in ob.data.splines:
					if len( spline.points ):	# favor NURBS style spline
						points = [ (v.co.x,v.co.y,v.co.z) for v in spline.points ]	# vec is len 4?
					else:					# fallback to bezier spline
						points = [ bez.co.to_tuple() for bez in spline.bezier_points ]

					s = {
						'closed' : spline.use_cyclic_u,
						'points' : points,
						'segments_u' : ob.data.resolution_u * spline.resolution_u,
						'color' : [1,1,1],
					}
					if len(ob.data.materials) and spline.material_index < len(ob.data.materials) and ob.data.materials[ spline.material_index ]:
						s['color'] = [ round(x,3) for x in ob.data.materials[spline.material_index].diffuse_color ]

					splines.append( s )


			elif ob.type == 'META':
				# note Three.js marching cubes metaball x,y,z is normalized to 0.0-1.0 range,
				# use fixed size scale as workaround #
				msg[ 'metas' ][ '__%s__'%UID(ob) ] = pak
				pak['elements'] = elements = []
				#pak['scl'] = ob.dimensions.to_tuple()	# use dimensions instead of scale - TODO ignore rotation?
				#sx,sy,sz = ob.dimensions
				sx = sy = sz = 10.0
				pak['scl'] = (sx,sy,sz)
				for e in ob.data.elements:
					elements.append(
						{
							'x':e.co.x / sx,
							'y':e.co.y / sy, 
							'z':e.co.z / sz,  
							'radius':e.radius
						}
					)
					# e also contains: radius, rotation, size_x,size_y,size_z, stiffness, type, use_negative

				pak['color'] = [ round(x,3) for x in ob.color ]


			elif ob.type == 'LAMP':
				msg[ 'lights' ][ '__%s__'%UID(ob) ] = pak
				pak['energy'] = ob.data.energy
				pak['color'] = [ round(a,3) for a in ob.data.color ]
				pak['dist'] = ob.data.distance
				pak['scale'] = ob.webgl_lens_flare_scale

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
					if len(ob.data.vertices) < self.MAX_VERTS and not far:
						streaming_meshes.append( ob )

				if ob.name in GameManager.RELOAD_TEXTURES:
					GameManager.RELOAD_TEXTURES.remove( ob.name )
					pak[ 'reload_textures' ] = True

				subsurf = 0
				for mod in ob.modifiers:
					if mod.type == 'SUBSURF':
						subsurf += mod.levels		# mod.render_levels
				pak[ 'subsurf' ] = subsurf
				pak[ 'ptex' ] = ob.webgl_progressive_textures
				pak[ 'norm' ] = ob.webgl_normal_map
				pak[ 'auto_subdiv' ] = ob.webgl_auto_subdivison

		for ob in streaming_meshes:
			pak = msg[ 'meshes' ][ '__%s__'%ob.UID ]

			mods = []
			for mod in ob.modifiers:
				#if mod.type in ('SUBSURF','MULTIRES') and mod.show_viewport:
				if mod.type in ('SUBSURF',) and mod.show_viewport:
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

			pak[ 'verts' ] = verts


		return msg




##################################################
class GameManager( object ):
	RELOAD_TEXTURES = []
	clients = {}	# ip : camera/player location

	@classmethod
	def add_player( self, ip, websocket=None ):
		player = Player( ip, websocket=websocket )
		self.clients[ ip ] = player
		return player

##################################################
class WebSocketServer( websocket.WebSocketServer ):
	buffer_size = 8096*2
	client = None
	webGL = WebGL()
	active = False

	def new_client(self):  ## websocket.py API ##
		ip,port = self.client.getsockname()
		if ip in GameManager.clients: print('[websocket] RELOADING CLIENT:', ip)
		else:
			print('_'*80)
			print('[websocket] NEW CLIENT:', ip)
			GameManager.add_player( ip, websocket=self.client )
		player = GameManager.clients[ ip ]


	def start_deprecated(self):
		self.daemon = False # daemon mode will not work inside blender
		self.verbose = True
		self.start_server()

	def start(self):
		print('[START WEBSOCKET SERVER: %s %s]' %(self.listen_host, self.listen_port))
		self.active = False
		#try:
		#	sock = self.socket(self.listen_host, self.listen_port)
		#except:
		#	print('ERROR [websocket] failed to listen on port: %s' %self.listen_port)
		#	return False
		sock = self.socket(self.listen_host, self.listen_port)

		self.active = True
		self.listen_socket = sock

		print('--starting websocket server thread--')
		threading._start_new_thread(
			self.new_client_listener_thread, (sock,)
		)
		return True

	def new_client_listener_thread(self, lsock):
		while self.active:
			try:
				#self.poll()
				ready = select.select([lsock], [], [], 0.5)[0]
				if lsock in ready: startsock, address = lsock.accept()
				else: continue
			except Exception: continue
			## keep outside of try for debugging ##
			self.top_new_client(startsock, address)	# sets.client and calls new_client()
		print('[websocket] debug thread exit')
		lsock.close()
		self.listen_socket = None
		#lsock.shutdown()


	def stop(self):
		if self.active:
			self.active = False
			time.sleep(0.1)
			print('[websocket] closing main listener socket')
			if self.listen_socket: self.listen_socket.close()
			#self.send_close()
			#raise self.EClose(closed)


	###################### server mainloop ####################
	_bps_start = None
	_bps = 0

	def update( self, context ):	# called from main thread
		#if not GameManager.clients: return
		players = []
		rlist = []# self.listen_socket ]
		wlist = []
		for player in GameManager.clients.values():
			if player.websocket:
				rlist.append( player.websocket )
				wlist.append( player.websocket )
				players.append( player )

		ins, outs, excepts = select.select(rlist, wlist, [], 0.01)
		if excepts: raise Exception("[websocket] Socket exception")


		if not outs and players:
			print('[websocket] no clients ready to read....')

		######## bug? can't listen and spawn new clients from main thread?
		#if self.listen_socket in outs and False:
		#	print('[websocket] new client...')
		#	sock, address = self.listen_socket.accept()
		#	self.top_new_client(sock, address)	# this is part of websocket.py API: it sets self.client=sock, and calls new_client()
		#	#outs.remove( self.listen_socket )

		for sock in outs:
			#if sock is self.listen_socket: continue

			player = players[ rlist.index(sock) ]
			msg = player.create_stream_message( context )
			print(player, msg)

			for fx in  self.webGL.effects:  ## TODO move to player class
				msg['FX'][fx.name]= ( fx.enabled, fx.get_uniforms() )

			## dump to json and encode to bytes ##
			rawbytes = json.dumps( msg ).encode('utf-8')
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


			self.client = sock
			try:
				pending = self.send_frames(cqueue)
				if pending: print('[websocket] failed to send', pending)
				else: pass #print('[websocket sent]', cqueue)
			except:
				print('[websocket error] can not send_frames')
			self.client = None

		for sock in ins:
			#if sock is self.listen_socket: continue
			player = players[ rlist.index(sock) ]

			self.client = sock

			frames, closed = self.recv_frames()
			print('got from client', frames)
			if closed:
				print('[websocket] CLOSING CLIENT')
				try:
					self.send_close()
					raise self.EClose(closed)
				except: pass
				self.client = None
			elif frames:
				for frame in frames:
					print('--got frame from client--')
					print('>>>',frame)
			elif not closed:
				print('[websocket ERROR] client sent nothing')

			self.client = None





#####################
import socketserver
class ForkingWebServer( socketserver.ForkingMixIn, wsgiref.simple_server.WSGIServer ):
	''' TODO test forking server '''
	pass
def make_forking_server( host, port, callback ):
	server = ForkingWebServer((host, port), wsgiref.simple_server.WSGIRequestHandler)
	server.set_app(callback)
	return server

class WebServer( object ):
	CLIENT_SCRIPT = open( os.path.join(SCRIPT_DIR,'client.js'), 'rb' ).read().decode('utf-8')

	def __init__(self, host=HOST_NAME, port=8080):
		self.init_webserver( host=host, port=port )
		print('webserver init complete')
		print('-'*80)

	def open_firefox(self):
		print('open_firefox')
		cmd = [
			'firefox', 
			'-new-instance', 
			'-new-window', 
			'http://%s:%s'%(self.host,self.httpd_port)
		]
		print(cmd)
		p = subprocess.Popen( cmd )
		return p

	def update(self, context=None):
		#print('webserver update from mainloop', context)
		if self.httpd: self.httpd.handle_request()

	def close(self):
		if self.httpd:
			self.httpd.server_close()	# this is REQUIRED

	def init_webserver(self, host='localhost', port=8080, forking=False, timeout=0):
		print('[INIT WEBSERVER: %s %s]' %(host, port))
		self.host = host
		self.httpd_port = port
		self.hires_progressive_textures = True

		if forking:
			self.httpd = make_forking_server( self.host, self.httpd_port, self.httpd_reply )
		else:

			#try:  ## this would be required for non-server client/peers ##
			#	self.httpd = wsgiref.simple_server.make_server( self.host, self.httpd_port, self.httpd_reply )
			#except:
			#	print('ERROR: failed to bind to port', self.httpd_port)
			#	self.httpd = None

			self.httpd = wsgiref.simple_server.make_server( self.host, self.httpd_port, self.httpd_reply )

		print(self.httpd)
		if self.httpd:
			self.httpd.timeout = timeout

		self.THREE = None
		path = os.path.join(SCRIPT_DIR, 'javascripts/Three.js')
		#if os.path.isfile( path ): self.THREE = open( path, 'rb' ).read()
		#else: print('ERROR: missing ./javascripts/Three.js')
		self.THREE = open( path, 'rb' ).read()
		#print(self.THREE)

	def get_header(self, title='http://%s'%HOST_NAME, webgl=False):
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
			h.append( '<script type="text/javascript" src="/javascripts/loaders/ColladaLoader.js"></script>' )
			h.append( '<script type="text/javascript" src="/javascripts/modifiers/SubdivisionModifier.js"></script>' )
			h.append( '<script type="text/javascript" src="/javascripts/ShaderExtras.js"></script>' )
			h.append( '<script type="text/javascript" src="/javascripts/MarchingCubes.js"></script>' )
			h.append( '<script type="text/javascript" src="/javascripts/ShaderGodRays.js"></script>' )

			h.append( '<script type="text/javascript" src="/javascripts/Curve.js"></script>' )
			h.append( '<script type="text/javascript" src="/javascripts/geometries/TubeGeometry.js"></script>' )

			for tag in 'EffectComposer RenderPass BloomPass ShaderPass MaskPass SavePass FilmPass DotScreenPass'.split():
				h.append( '<script type="text/javascript" src="/javascripts/postprocessing/%s.js"></script>' %tag )



			######################### Pyppet WebGL Client ##############################
			self.CLIENT_SCRIPT = open( os.path.join(SCRIPT_DIR,'client.js'), 'rb' ).read().decode('utf-8')
			h.append( '<script type="text/javascript">' )

			h.append( 'var HOST = "%s";' %HOST_NAME )


			if self.hires_progressive_textures:
				h.append( 'var MAX_PROGRESSIVE_TEXTURE = 2048;' )
				h.append( 'var MAX_PROGRESSIVE_NORMALS = 1024;' )
				h.append( 'var MAX_PROGRESSIVE_DISPLACEMENT = 512;' )
				h.append( 'var MAX_PROGRESSIVE_DEFAULT = 256;' )
			else:
				h.append( 'var MAX_PROGRESSIVE_TEXTURE = 512;' )
				h.append( 'var MAX_PROGRESSIVE_NORMALS = 512;' )
				h.append( 'var MAX_PROGRESSIVE_DISPLACEMENT = 512;' )
				h.append( 'var MAX_PROGRESSIVE_DEFAULT = 256;' )


			h.append( self.CLIENT_SCRIPT )
			h.append( '</script>' )

		return '\n'.join( h )

	def http_reply_python( self, env, start_response):
		# overload me for custom protocols talking to other Python clients #
		raise NotImplemented

	def httpd_reply( self, env, start_response ):	# main entry point for http server
		#print('httpd_reply', env)
		agent = env['HTTP_USER_AGENT']		# browser type
		if agent == 'Python-urllib/3.2': return self.httpd_reply_python( env, start_response )
		else: return self.httpd_reply_browser( env, start_response )

	def httpd_reply_browser(self, env, start_response ):
		path = env['PATH_INFO']
		host = env['HTTP_HOST']
		client = env['REMOTE_ADDR']
		arg = env['QUERY_STRING']
		#print('http_reply_browser', path, host, client, arg)

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

			## peer UDP is deprecated
			#if self.clients:
			#	f.write('<h2>Streaming Clients</h2><ul>')
			#	for a in self.clients: f.write('<li><a href="http://%s">%s</a></li>' %(a,a))
			#	f.write('</ul>')
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
			## mini API for getting objects in different formats, example:
			## http://server/objects/a.dae
			## http://server/objects/a.obj  (TODO)

			url = path[ 9 : ]
			name = path.split('/')[-1]
			if name.endswith('.dae'):
				print('dump collada request', name)

				start_response('200 OK', [('Content-Type','text/xml; charset=utf-8')])
				uid = name[ : -4 ]
				ob = get_object_by_UID( uid )
				if arg == 'center':
					return [ dump_collada(ob,center=True) ]
				elif arg == 'hires':
					return [ dump_collada(ob,hires=True) ]
				else:
					return [ dump_collada(ob) ]

			elif os.path.isfile( url ):
				data = open( url, 'rb' ).read()
				start_response('200 OK', [('Content-Length',str(len(data)))])
				return [ data ]

			else:
				print('WARNING: unknown request', path)


		elif path.startswith('/javascripts/'):
			## serve static javascript files
			start_response('200 OK', [('Content-Type','text/javascript; charset=utf-8')])
			data = open( relpath, 'rb' ).read()
			return [ data ]

		elif path.startswith('/bake/'):
			## bake texture maps backend ##
			print( 'PATH', path, arg)
			uid = path.split('/')[-1][ :-4 ]	# strip ".jpg"
			ob = get_object_by_UID( uid )

			data = None
			if path.startswith('/bake/LOD/'):
				for child in ob.children:
					if child.is_lod_proxy:
						data = Pyppet.bake_image(
							child, 
							*arg.split('|'),
							extra_objects=[ob]
						)
						break

			if not data:	# fallback for meshes that are already low resolution without a proxy
				data = Pyppet.bake_image( ob, *arg.split('|') )

			start_response('200 OK', [('Content-Length',str(len(data)))])
			return [ data ]


		elif path.startswith('/textures/'):
			data = open( relpath, 'rb' ).read()
			start_response('200 OK', [('Content-Length',str(len(data)))])
			return [ data ]


		elif path.startswith('/RPC/'):
			## tiny remote procedure call API
			if path.startswith('/RPC/player/'):
				pos = [float(a) for a in path.split('/')[-1].split(',')]

				if client not in GameManager.clients:
					print('new player', pos)
					## hook point for backends to connect auth server
					GameManager.add_player( client )

				player = GameManager.clients[ client ]
				player.set_location( pos )

				start_response('200 OK', [('Content-Length','0')])
				return []

			elif path.startswith('/RPC/select/'):
				if bpy.context.mode == 'OBJECT':
					uid = path.split('/')[-1]
					print('RPC', uid)
					for ob in bpy.context.scene.objects: ob.select=False
					ob = get_object_by_UID( uid )
					ob.select = True
					bpy.context.scene.objects.active = ob

				start_response('200 OK', [('Content-Length','0')])
				return []

		else:
			print( 'SERVER ERROR: invalid path', path )


#-----------------------------------------------------------------------





#-----------------------------------------------------------------------
class Remote3dsMax(object):
	def __init__(self, api, exe_path=None, use_wine=True):
		if not exe_path:
			exe_path = os.path.expanduser('~/.wine/drive_c/Program Files/Autodesk/3ds Max 2009/3dsmax.exe')
		self.exe_path = exe_path
		self.use_wine = use_wine
		self._wait_for_loading = []
		self._load_3ds_files = []
		self._prevcmd = None

		import Database
		self.db = Database.create_database( api )


	def run(self):
		cmd = []
		if self.use_wine: cmd.append( 'wine' )

		cmd = [self.exe_path, '-q', '-u', 'MAXScript', 'pyppet/stream_api.ms']
		print(cmd)
		self._proc = subprocess.Popen( cmd )

	def update(self, clipboard):
		try:
			txt = clipboard.wait_for_text()
		except ValueError: #NULL pointer access
			txt = ''

		if txt.startswith('@'):
			db = self.db

			cmd, cat, args = txt[1:].split('@')
			name, args = args.split('~')
			exargs = None
			if '*' in args:
				args, exargs = args.split('*')

			if txt != self._prevcmd:
				print('-'*80)
				print(cmd)
				print(name)
				print(args)
			self._prevcmd = txt
			#)))))))))))))))))))))))))))))))))))))))))))))


			# args is pos, scl, quat #
			pos,scl,quat = args.split('|')
			pos = eval(pos)
			scl = eval(scl)
			_, w, x,y,z = quat.replace(')','').split()
			quat = (float(w),float(x),float(y),float(z))


			######################################################################
			## API ##

			if cmd == 'UPDATE:STREAM':
				if name not in db.objects:
					print('adding new object from update stream')
					db.add_object(name, pos, scl, quat)

				# TODO switch this back on when we can load FBX or something else (.3ds breaks triangles and vertex order)
				#if exargs: # streaming mesh
				#	verts = [ eval('(%s)'%v) for v in exargs[1:-1].split('][') ]
				#else:
				#	verts = None
				verts = None
				db.update_object(name, pos, scl, quat, category=cat, vertices=verts)

			if cmd == 'UPDATE:SELECT':
				pass

			elif cmd == 'SAVING:3DS': ## TODO check this is sending from stream_api.ms
				if name not in self._wait_for_loading:
					self._wait_for_loading.append( name )

			elif cmd == 'LOAD:3DS':
				#TODO-enable-when-catching-saveing:3ds##assert name == self._wait_for_loading.pop()
				loaded = self.load_3ds( name )

				
			elif cmd == '@database:add_object@':
				#self._wait_for_loading.append( name )
				if name not in db.objects:
					db.add_object(name, pos, scl, quat, category=category)

				self.load_3ds( name )


	def load_3ds(self, name): ## FBX import is missing in blender
		path = os.path.expanduser('~/.wine/drive_c/%s.3ds'%name)
		assert os.path.isfile( path )
		db = self.db

		stat = os.stat( path )
		uid = (path, stat.st_mtime)
		if uid in self._load_3ds_files:
			### note: do not load file if it hasn't been updated yet, by checking the modified time "mtime"
			return

		self._load_3ds_files.append( uid )
		print('LOADING new 3ds',uid)

		obnames = bpy.data.objects.keys()

		bpy.ops.import_scene.autodesk_3ds(
			filepath=os.path.expanduser('~/.wine/drive_c/%s.3ds'%name), 
			filter_glob="*.3ds", 
			constrain_size=10, 
			use_image_search=False, 
			use_apply_transform=True, 
			axis_forward='Y', 
			axis_up='Z'
		)

		remove = []
		loaded = []
		for n in bpy.data.objects.keys():
			if n not in obnames:
				print('new import', n)
				ob = bpy.data.objects[ n ]
				ob.rotation_mode = 'QUATERNION'
				print(ob.type)
				if ob.type == 'MESH':
					iname = ob.name.split('.')[0]
					if iname in bpy.data.objects.keys():
						print('REPLACE')
						instance = bpy.data.objects[ iname ]
						if instance.type == 'EMPTY':
							instance.name = 'xxx'
							remove.append( instance )
							ob.name = iname
							db.objects[iname] = ob ## replace instance in database
							loaded.append( ob )
						else:
							instance.data = ob.data
							remove.append( ob )
							loaded.append( instance )
					else:
						print('ADD')
						db.objects[iname] = ob
						loaded.append( ob )


		while remove:
			ob = remove.pop()
			#bpy.context.scene.objects.unlink(ob)

		return loaded

class TestApp( BlenderHackLinux ):
	def __init__(self):
		assert self.setup_blender_hack( bpy.context )

		self.window = win = gtk.Window()
		win.connect('destroy', lambda w: setattr(self,'active',False) )
		win.set_title( 'tools' )	# note blender name not allowed here
		self.root = root = gtk.VBox()
		win.add( root )


		frame = gtk.Frame()
		frame.set_border_width( 10 )
		root.pack_start( frame, expand=False )
		button = gtk.Button('connect 3dsMax')
		button.set_border_width( 10 )
		button.connect('clicked', self.connect_3dsmax)
		frame.add( button )

		win.show_all()				# window and all widgets shown first
		self._clipboard = self.window.get_clipboard()  # clipboard is current workaround for talking to 3dsmax

		self.webserver = WebServer()
		self.websocket_server = WebSocketServer( listen_host=HOST_NAME, listen_port=8081 )
		self.websocket_server.start()	# polls in a thread

		self._3dsmax = None


	def connect_3dsmax(self, button):
		print('you clicked')
		self._3dsmax = Remote3dsMax( bpy )
		self._3dsmax.run()


	def mainloop(self):
		self.active = True
		while self.active:
			self.update_blender_and_gtk() # includes: self._3dsmax.update( self._clipboard )
			self.webserver.update()
			#if self._3dsmax: self._3dsmax.update( self.clipboard )

if __name__ == '__main__':
	print('running server test...')
	test = TestApp()
	test.mainloop()
	print('webserver test complete.')
