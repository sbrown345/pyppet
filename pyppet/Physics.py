## Ode Physics Addon for Blender
## by Brett Hart, March 9th, 2011
## (updated for Blender2.6.1 matrix-style)
## License: BSD

DEFAULT_ERP = 0.25		# collision bounce gains energy if this is too high > 0.5
DEFAULT_CFM = 0.05


import os, sys, time, ctypes
import threading
import bpy, mathutils
from bpy.props import *
from random import *
## make sure we can import from same directory ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.append( SCRIPT_DIR )
import ode

def _None(arg): return None		# stupid rule, why should the func have to return None - TODO talk to ideasman again.


#################### pyRNA ##################
bpy.types.Object.ode_use_soft_collision = BoolProperty( name='use soft collision', default=False )
bpy.types.Object.ode_soft_collision_erp = FloatProperty( name='soft collision ERP', default=0.05 )
bpy.types.Object.ode_soft_collision_cfm = FloatProperty( name='soft collision CFM', default=0.15 )


bpy.types.Object.ode_friction = FloatProperty( name='body friction', default=0.5 )

bpy.types.Object.ode_bounce = FloatProperty( name='body bounce', default=0.025 )


bpy.types.Object.ode_use_body = BoolProperty( 
	name='use physics body', default=False, 
	update=lambda self,con:  ENGINE.get_wrapper(self).toggle_body(self.ode_use_body)
)


bpy.types.Object.ode_use_gravity = BoolProperty( 
	name='use gravity', default=True,		# ode defaults to True
	update=lambda self, con: _None(ENGINE.get_wrapper(self).body.SetGravityMode(self.ode_use_gravity))
)

bpy.types.Object.ode_mass = FloatProperty( 
	name='body mass', default=0.5,
	update=lambda self, con: ENGINE.get_wrapper(self).set_mass(self.ode_mass)
)

bpy.types.Object.ode_linear_damping = FloatProperty( 
	name='linear damping', default=0.0420,
	update=lambda self, con: _None( ENGINE.get_wrapper(self).body.SetLinearDamping( self.ode_linear_damping ) )
)

bpy.types.Object.ode_angular_damping = FloatProperty( 
	name='angular damping', default=0.1,
	update=lambda self, con: _None( ENGINE.get_wrapper(self).body.SetAngularDamping( self.ode_angular_damping ) )
)


bpy.types.Object.ode_use_collision = BoolProperty( 
	name='use collision', default=False,
	update=lambda self, con: ENGINE.get_wrapper(self).toggle_collision(self.ode_use_collision)
)



########################## updated by devices ####################
bpy.types.Object.ode_constant_global_force = FloatVectorProperty( name='constant global force' )	
bpy.types.Object.ode_constant_local_force = FloatVectorProperty( name='constant local force' )
bpy.types.Object.ode_constant_global_torque = FloatVectorProperty( name='constant global torque' )
bpy.types.Object.ode_constant_local_torque = FloatVectorProperty( name='constant local torque' )

########################## updated by devices ####################
bpy.types.Object.ode_global_force = FloatVectorProperty( name='global force' )	
bpy.types.Object.ode_local_force = FloatVectorProperty( name='local force' )
bpy.types.Object.ode_global_torque = FloatVectorProperty( name='local torque' )
bpy.types.Object.ode_local_torque = FloatVectorProperty( name='local torque' )
#################################################################
bpy.types.Object.ode_force_driver_rate = FloatProperty( name='force driver rate', default=0.420, min=.0, max=1.0 )

bpy.types.World.ode_speed = FloatProperty( 'physics speed', min=0.01, max=1.0, default=0.05 )


def _set_gravity(world,context):
	x,y,z = world.ode_gravity
	ENGINE.world.SetGravity( x,y,z )
bpy.types.World.ode_gravity = FloatVectorProperty( 'gravity', min=-20, max=20, default=(.0,.0,-9.810), update=_set_gravity )

bpy.types.World.ode_ERP = FloatProperty(
	'error reduction param', min=.0, max=1.0, default=DEFAULT_ERP,
	update= lambda w,c: _None( ENGINE.world.SetERP(w.ode_ERP) )
)
bpy.types.World.ode_CFM = FloatProperty(
	'constant force mixing', min=.00001, max=10.0, default=DEFAULT_CFM,
	update= lambda w,c: _None( ENGINE.world.SetCFM(w.ode_CFM) )
)
bpy.types.World.ode_quickstep_iterations = IntProperty( 'quick step iterations', min=1, max=64, default=20 )

bpy.types.World.ode_linear_damping = FloatProperty(
	'linear damping', min=.0, max=10.0, default=.0,
	update= lambda w,c: _None( ENGINE.world.SetLinearDamping(w.ode_linear_damping) )
)
bpy.types.World.ode_angular_damping = FloatProperty(
	'angular damping', min=.0, max=10.0, default=.0,
	update= lambda w,c: _None( ENGINE.world.SetAngularDamping(w.ode_angular_damping) )
)



# setFDir1
#def setFDir1(self, fdir):
#"""setFDir1(fdir)
#
#Set the "first friction direction" vector that defines a direction
#along which frictional force is applied. It must be of unit length
#and perpendicular to the contact normal (so it is typically
#tangential to the contact surface).
#
#@param fdir: Friction direction
#@type fdir: 3-sequence of floats
#"""
#self._contact.fdir1[0] = fdir[0]
#self._contact.fdir1[1] = fdir[1]
#self._contact.fdir1[2] = fdir[2]

#[flags specifies how contacts should be generated if the objects
#touch. Currently the lower 16 bits of flags specifies the maximum
#number of contact points to generate. If this number is zero, this
#function just pretends that it is one - in other words you can not
#ask for zero contacts. All other bits in flags must be zero. In
#the future the other bits may be used to select other contact
#generation strategies.]


class OdeSingleton(object):
	'''
	each geom in self.space will be tested with ode.SpaceCollide2 against self.subspace,
	SubSpace geoms will not collide with eachother,
	if SubSpace contains nested spaces, they can collide?
	'''
	def reset( self ):
		if self.threaded: self.lock.acquire()
		[ ob.reset() for ob in self.objects.values() ]
		if self.threaded: self.lock.release()

	def start(self):
		self.active = False
		time.sleep(1)	# ensure thread is done
		print('starting ODE physics...')
		self._iterations = 0
		self._collision_iterations = 0
		self._start_time = time.time()
		self.active=True
		self.reset()
		if self.threaded: self.start_thread()

	def stop(self):
		print('stopping ODE physics.')
		self.active=False; self.reset()
		seconds = time.time() - self._start_time
		print('--ODE iterations:', self._iterations)
		print('--ODE seconds:', seconds)
		if self._iterations:
			avg = seconds / self._iterations
			print('--ODE average time per frame:', avg)
			fps = 1.0/avg
			print('--ODE FPS:', fps)
			if fps < 30: print('--WARNING: physics less than 30 FPS')

		if self._collision_iterations:
			avg = seconds / self._collision_iterations
			print('--ODE COLLISION average time per frame:', avg)
			fps = 1.0/avg
			print('--ODE COLLISION FPS:', fps)

		time.sleep(1)

	def exit(self): ode.CloseODE()
	def toggle_pause(self,switch):
		self.paused = switch

	def __init__(self, lock=None, space_type='HASH'):
		self.active = False
		self.paused = False
		ode.InitODE() ## initialize ODE ##

		self.world = ode.WorldCreate()
		self.world.SetERP( DEFAULT_ERP )
		self.world.SetCFM( DEFAULT_CFM )

		self.collision_world = ode.WorldCreate()

		self.world.SetGravity(.0,.0,-9.810)
		#self.world.SetQuickStepNumIterations(24)

		#self.bodyless_space = ode.SimpleSpaceCreate()

		if space_type == 'HASH':		# not any faster with the biped solver alone
			print('creating Hash space')
			#self.space = ode.HashSpaceCreate( self.bodyless_space )
			self.space = ode.HashSpaceCreate()
			## 2**-4 = 0.0625
			## 2**6 = 64
			self.space.HashSpaceSetLevels( -4, 6 )	# 2**min, 2**max

			self.subspace = ode.HashSpaceCreate()
			self.subspace.HashSpaceSetLevels( -4, 6 )

		else:
			print( '--creating Simple space' )
			self.space = ode.SimpleSpaceCreate()
			self.subspace = ode.SimpleSpaceCreate()

		self.bodyless_space = self.space
		#ode.SpaceSetSublevel( self.space, 2 )

		#self.space = ode.QuadTreeSpaceCreate(None, center4, extents4, depth)
		print( self.space )
		self.joint_group = ode.JointGroupCreate( 0 )		# max size (returns low-level pointer)
		self.objects = {}
		self.bodies = {}
		self.bodyless_geoms = {}
		self.body_geoms = {}

		self._tmp_joints = []

		self.substeps = 5
		self.rate = 1.0 / 20
		self.lock = lock

		if lock:
			self.threaded = True
		else:
			self.threaded = False

		self._iterations = 0
		self._collision_iterations = 0
		self._pending_near = []
		self._pending_contact_joints = []
		self._collision_state = []

	def get_wrapper(self, ob):
		if ob.name not in self.objects: self.objects[ ob.name ] = HybridObject( ob, self.world, self.space )
		return self.objects[ ob.name ]

	def sync( self, context, now, recording=False, drop_frame=False ):
		if not self.active: return

		### this was for fudging the location of an object while it was being moved in blender's viewport
		#if context.active_object and context.active_object.name in self.objects and False:
		#	#if self.threaded: self.lock.acquire()
		#
		#	obj = self.objects[ context.active_object.name ]
		#	body = obj.body
		#	if body:
		#		x1,y1,z1 = body.GetPosition()
		#		#x2,y2,z2 = context.active_object.location
		#		x2,y2,z2 = context.active_object.matrix_world.to_translation()
		#		dx = x1-x2
		#		dy = y1-y2
		#		dz = z1-z2
		#
		#		fudge = 0.5
		#		if context.blender_has_cursor or abs( x1-x2 ) > fudge or abs( y1-y2 ) > fudge or abs( z1-z2 ) > fudge:
		#			body.SetPosition( x2, y2, z2 )
		#			if not self.paused: body.AddForce( dx, dy, dz )
		#
		#	#if self.threaded: self.lock.release()

		if self.paused: return

		create = []
		if self.threaded: self.lock.acquire()
		for ob in bpy.data.objects:
			if ob.name not in self.objects: create.append( ob.name )
		if create:
			print('creating new physics objects')
			for name in create:
				ob = bpy.data.objects[ name ]
				self.objects[ ob.name ] = HybridObject( ob, self.world, self.space )
		if self.threaded: self.lock.release()


		fast = []	# avoids dict lookups below
		for ob in bpy.data.objects:
			if ob.name not in self.objects: continue
			obj = self.objects[ ob.name ]
			obj.sync( ob )		# gets new settings, calls AddForce etc...
			fast.append( (obj,ob) )

		#fps = context.scene.game_settings.fps
		#self.rate = rate = 1.0 / fps
		self.rate = context.scene.world.ode_speed

		if not self.threaded:
			#print('doing space collision and quickstep...')
			ode.SpaceCollide( self.space, None, self.near_callback )
			self.world.QuickStep( self.rate )
			ode.JointGroupEmpty( self.joint_group )
			self._iterations += 1


		if fast:
			#print('doing fast update on', fast)
			for obj, bo in fast:
				obj.update( bo, now, recording, update_blender=not drop_frame )


	def start_thread(self):
		threading._start_new_thread( self.loop, () )


	def loop(self):
		print('------starting ODE thread-----')

		state = []
		while self.active:
			start = time.time()

			[ wrap.sync_from_ode_thread() for wrap in self.objects.values() ]

			self.lock.acquire()

			#ode.SpaceCollide( self.space, None, self.near_callback_sync )
			self._pending_near = []
			ode.SpaceCollide( self.space, None, self.near_callback_sync_fast )
			if self._pending_near:
				for geom1, geom2 in self._pending_near:
					self.do_collision( geom1, geom2 )

			rate = self.rate / float(self.substeps)
			for i in range(int(self.substeps)): self.world.QuickStep( rate )

			ode.JointGroupEmpty( self.joint_group )

			self.lock.release()
			self._iterations += 1
			dt = time.time() - start
			if dt <= 0.03:
				time.sleep(0.03- dt)

		print('------exit ODE thread------')




	def near_callback( self, data, geom1, geom2 ):
		#if (geom1,geom2) in self._pending_near: print('1,2 already in')
		#if (geom2,geom1) in self._pending_near: print('2,1 already in')
		self._pending_near.append( (geom1, geom2) )


	def near_callback_sync_fast( self, data, geom1, geom2 ):
		'''
		near_callback_sync get's 34-36 FPS
		while this gets 36-45 FPS

		WHY?
			Something to do with the callbacks from C and the GIL?

		'''
		self._pending_near.append( (geom1, geom2) )



	PYOBJP = ctypes.POINTER(ctypes.py_object)
	def near_callback_sync( self, data, geom1, geom2 ):
		#print( 'near callback', geom1, geom2 )	# geom1,2 are lowlevel pointers, not wrapper objects
		body1 = ode.GeomGetBody( geom1 )
		body2 = ode.GeomGetBody( geom2 )
		_b1 = _b2 = None
		try: _b1 = body1.POINTER.contents
		except ValueError: pass
		try: _b2 = body2.POINTER.contents
		except ValueError: pass
		if not _b1 and not _b2:
			return

		ptr1 = ctypes.cast( ode.GeomGetData( geom1 ), self.PYOBJP )
		ob1 = ptr1.contents.value
		ptr2 = ctypes.cast( ode.GeomGetData( geom2 ), self.PYOBJP )
		ob2 = ptr2.contents.value

		dContactGeom = ode.ContactGeom.CSTRUCT		# get the raw ctypes struct
		geoms = (dContactGeom * 32)()
		geoms_ptr = ctypes.pointer( geoms )
		touching = ode.Collide( 
			geom1, 
			geom2,
			32,	# flags, actually number of 
			geoms_ptr,
			ctypes.sizeof( dContactGeom )
		)

		dContact = ode.Contact.CSTRUCT			# get the raw ctypes struct
		for i in range(touching):
			g = geoms_ptr.contents[ i ]
			con = dContact()
			con.surface.mode = ode.ContactBounce	# pyode default
			#con.surface.bounce = 0.1			# pyode default
			#con.surface.mu = 100.0
			con.geom = g

			## get "friction" and "bounce" settings from wrapper objects ##
			con.surface.mu = (ob1._friction + ob2._friction) * 100
			con.surface.bounce = ob1._bounce + ob2._bounce


			## user callbacks ##
			dojoint = True
			cmd = ob1.callback( ob2, con, g.pos, g.normal, g.depth, i, touching )
			if cmd == 'BREAK': break
			elif cmd == 'PASS': dojoint = False
			cmd = ob2.callback( ob1, con, g.pos, g.normal, g.depth, i, touching )
			if cmd == 'BREAK': break
			elif cmd == 'PASS': dojoint = False

			if dojoint:
				joint = ode.JointCreateContact( self.world, self.joint_group, ctypes.pointer(con) )
				joint.Attach( body1, body2 )




	def do_collision( self, geom1, geom2 ):
		#print('doing collision', geom1, geom2)
		body1 = ode.GeomGetBody( geom1 )
		body2 = ode.GeomGetBody( geom2 )
		_b1 = _b2 = None
		try: _b1 = body1.POINTER.contents
		except ValueError: pass
		try: _b2 = body2.POINTER.contents
		except ValueError: pass
		if not _b1 and not _b2:
			return

		#if ode.GeomIsSpace(geom1) or ode.GeomIsSpace(geom2): return

		ptr1 = ctypes.cast( ode.GeomGetData( geom1 ), self.PYOBJP )
		ob1 = ptr1.contents.value
		ptr2 = ctypes.cast( ode.GeomGetData( geom2 ), self.PYOBJP )
		ob2 = ptr2.contents.value

		if ob1.no_collision_groups or ob2.no_collision_groups:
			for cat in ob1.no_collision_groups:
				if cat in ob2.no_collision_groups: return
			for cat in ob2.no_collision_groups:
				if cat in ob1.no_collision_groups: return


		dContactGeom = ode.ContactGeom.CSTRUCT		# get the raw ctypes struct
		geoms = (dContactGeom * 32)()
		geoms_ptr = ctypes.pointer( geoms )
		touching = ode.Collide( 
			geom1, 
			geom2,
			32,	# flags, actually number of 
			geoms_ptr,
			ctypes.sizeof( dContactGeom )
		)

		dContact = ode.Contact.CSTRUCT			# get the raw ctypes struct
		for i in range(touching):
			g = geoms_ptr.contents[ i ]
			con = dContact()
			con.geom = g
			con.surface.mu = (ob1._friction + ob2._friction) * 100

			if ob1._soft or ob2._soft:
				con.surface.mode = ode.ContactSoftERP | ode.ContactSoftCFM
				con.surface.soft_erp = 0.0
				con.surface.soft_cfm = 0.0
				if ob1._soft:
					con.surface.soft_erp += ob1._soft_erp
					con.surface.soft_cfm += ob1._soft_cfm
				if ob2._soft:
					con.surface.soft_erp += ob2._soft_erp
					con.surface.soft_cfm += ob2._soft_cfm

			else:
				con.surface.mode = ode.ContactBounce
				con.surface.bounce = ob1._bounce + ob2._bounce

			info = {'location':g.pos, 'normal':g.normal, 'depth':g.depth}
			ob1._touching[ ob2.name ] = info
			ob2._touching[ ob1.name ] = info

			joint = ode.JointCreateContact( self.world, self.joint_group, ctypes.pointer(con) )
			joint.Attach( body1, body2 )


LOCK = threading._allocate_lock()
if hasattr(ode, 'InitODE'):
	ENGINE = OdeSingleton( lock=LOCK )
else:
	ENGINE = None
	print(ode, dir(ode))
	raise RuntimeError

############################################################
class Joint( object ):
	Types = {
		'ball' : 'Ball',
		'hinge' : 'Hinge', 
		'slider' : 'Slider', 
		'universal' : 'Universal', 
		'dual-hinge' : 'Hinge2', 
		'fixed' : 'Fixed', 
		'angular-motor' : 'AMotor', 
		'linear-motor' : 'LMotor', 
		'planar' : 'Plane2D', 
		'slider-hinge' : 'PR',
		'slider-universal' : 'PU',
		'piston' : 'Piston',
	}
	Tooltips = {
		'ball' : 'simple ball and socket joint',
		'hinge' : 'simple hinge joint (rotoide)', 
		'slider' : 'simple slider joint (prismatic)', 
		'universal' : 'A universal joint is like a ball and socket joint that constrains an extra degree of rotational freedom. Given axis 1 on body 1, and axis 2 on body 2 that is perpendicular to axis 1, it keeps them perpendicular.', 
		'dual-hinge' : 'The hinge-2 joint is the same as two hinges connected in series, with different hinge axes. An example, shown in the above picture is the steering wheel of a car, where one axis allows the wheel to be steered and the other axis allows the wheel to rotate.', 
		'fixed' : 'simple fixed joint, can produce spring-like effects when used with high CFM', 
		'angular-motor' : 'An angular motor (AMotor) allows the relative angular velocities of two bodies to be controlled. The angular velocity can be controlled on up to three axes, allowing torque motors and stops to be set for rotation about those axes', 
		'linear-motor' : 'A linear motor (LMotor) allows the relative linear velocities of two bodies to be controlled. The linear velocity can be controlled on up to three axes, allowing torque motors and stops to be set for translation along those axes', 
		'planar' : 'The plane-2d joint acts on a body and constrains it to the Z == 0 plane.', 
		'slider-hinge' : 'A prismatic and rotoide joint (JointPR) combines a Slider (prismatic) and a Hinge (rotoide).',
		'slider-universal' : 'A prismatic-Universal joint (JointPU) combines a Slider (prismatic) between body1 and the anchor and a Universal joint at the anchor position. This joint provide 1 degree of freedom in translation and 2 degrees of freedom in rotation.',
		'piston' : 'A piston joint is similar to a Slider joint except that rotation around the translation axis is possible.',

	}
	
	Params = 'ERP CFM LoStop HiStop Vel FMax FudgeFactor Bounce StopERP StopCFM SuspensionERP SuspensionCFM'.split()

	def __init__(self, name, parent=None, child=None, type='fixed', axis1=(1.0,.0,.0), axis2=(.0,1.0,.0) ):
		self.parent = parent
		self.child = child
		self.name = name
		self.type = type
		self.joint = None
		self.breaking_threshold = None
		self.damage_threshold = None
		self.broken = False
		self.slaves = []		# sub-joints
		self.settings = ['type', 'breaking_threshold']	# for loading/saving TODO - or just save all simple py types?
		self.feedback = ode.JointFeedback()

		self.axis1 = axis1
		self.axis2 = axis2

		self._on_broken_callback = None	# user callback
		self._on_broken_args = None

		self.set_type( type )	# must be last

	def set_type( self, type ):
		self.type = type					# nice name
		self.dtype = Joint.Types[type]		# ode name

		## Sneaky - get the get/set funcs dynamically based on what joint type we are ##
		self._set_func = getattr( ode, 'JointSet%sParam'%self.dtype )
		self._get_func = getattr( ode, 'JointGet%sParam'%self.dtype )

		if self.joint: ode.JointDestroy(self.joint)
		world = self.parent.world
		func = getattr(ode, 'JointCreate%s'%self.dtype)
		self.joint = j = func( world )
		ode.JointAttach( j, self.parent.body, self.child.body )

		x,y,z = self.parent.body.GetPosition()

		if type == 'fixed': ode.JointSetFixed( j )
		elif type == 'angular-motor': pass
		elif type == 'linear-motor': pass
		elif type == 'planar': pass
		elif type == 'slider': pass

		elif type == 'ball': ode.JointSetBallAnchor(self.joint, x,y,z )
		elif type == 'hinge':
			ode.JointSetHingeAnchor(self.joint, x,y,z )
			ode.JointSetHingeAxis( self.joint, *self.axis1 )

		elif type == 'universal':
			print('setting universal joint anchor', x,y,z)
			ode.JointSetUniversalAnchor(self.joint, x,y,z )
			ode.JointSetUniversalAxis1( self.joint, *self.axis1 )
			ode.JointSetUniversalAxis2( self.joint, *self.axis2 )

		elif type == 'dual-hinge':
			print('setting hinge2 joint anchor', x,y,z)
			ode.JointSetHinge2Anchor(self.joint, x,y,z )
		elif type == 'PR': ode.JointSetPRAnchor(self.joint, x,y,z )
		elif type == 'PU': ode.JointSetPUAnchor(self.joint, x,y,z )
		elif type == 'piston': ode.JointSetPistonAnchor(self.joint, x,y,z )
		else:
			print('ERROR: unknown joint type', type)
			assert 0

		ode.JointSetFeedback( self.joint, self.feedback )



	def set_on_broken_callback( self, func, *args ):
		self._on_broken_callback = func
		self._on_broken_args = args

	def get_stress(self):
		s = []
		for vec in (self.feedback.f1, self.feedback.f2, self.feedback.t1, self.feedback.t2):
			x,y,z,null = vec
			s += [abs(x), abs(y), abs(z)]
		return sum(s) / float(len(s))

	def break_joint(self):	# do not actually delete the joint
		print('breaking joint',self.name)
		if self.broken: print('WARN: joint already broken')
		else:
			self.broken = True

			if ENGINE.lock: ENGINE.lock.acquire()
			ode.JointDisable( self.joint )
			if ENGINE.lock: ENGINE.lock.release()

			for joint in self.slaves: joint.break_joint()
			if self._on_broken_callback:
				self._on_broken_callback( *self._on_broken_args )


	def restore(self):
		if self.broken:
			self.broken = False
			ode.JointEnable( self.joint )
			for joint in self.slaves:
				joint.restore()

	def damage(self,value):
		#erp = self.get_param( 'ERP' )
		#self.set_param('ERP', 0.1)
		#self.set_param('CFM', 0.1)
		#self.child.increase_mass( value )
		#self.parent.increase_mass( value*0.25 )
		bpy.data.objects[ self.child.name ].ode_constant_global_force[2] -= value * 10
		bpy.data.objects[ self.parent.name ].ode_constant_global_force[2] -= value * 20
		#self.breaking_threshold *= 0.9
		#print('breaking thresh reduced to', self.breaking_threshold)

	def repair(self,value): pass


	def __del__(self):
		print('deleting joint',self.name)
		ode.JointDestroy( self.joint )

	def is_active(self): return bool( ode.JointIsEnabled(self.joint) )

	def toggle(self,switch):
		if switch: ode.JointEnable( self.joint )
		else: ode.JointDisable( self.joint )


	def set_param( self, param, *args ):
		'''
		automatically sets param for all axes:
			eg. ERP, ERP1, ERP2, ERP3
		'''
		assert param in Joint.Params

		if param not in self.settings: self.settings.append( param )	# TODO, cache here?

		P = getattr(ode, 'Param%s'%param)
		params = []
		for i in range(3): params.append( getattr(ode, 'Param%s%s' %(param,i+1)) )

		self._set_func( self.joint, P, args[0] )

		if len(args)==3:
			setattr(self,param,args)
			for i,p in enumerate(params):
				self._set_func( self.joint, p, args[i] )

		elif len(args)==1:
			setattr(self,param,args[0])
			for i,p in enumerate(params):
				self._set_func( self.joint, p, args[0] )

	def get_param(self, param):
		assert param in Joint.Params
		P = getattr(ode, 'Param%s'%param)
		return self._get_func( self.joint, P )

JOINT_TYPES = list(Joint.Types.keys())


####################### object wrapper ######################
class HybridObject( object ):
	'''
	Geom/Body hybrid container,
	may be a body or geom, and may also contain sub-geoms
	'''
	def __init__( self, bo, world, space, lock=None ):
		self._friction = 0.0	# internal use only
		self._bounce = 0.0	# internal use only
		self._soft = True	# internal use only
		self._soft_erp = 0.0	# internal use only
		self._soft_cfm = 0.0	# internal use only
		self.blender_object = bo
		self.world = world
		self.space = space
		self.name = bo.name
		self.type = bo.type
		self.lock = lock

		self.recbuffer = []
		self.body = None
		self.collision_body = None

		self.geom = None
		self.geomtype = None
		self.subgeoms = []
		self.is_subgeom = False

		self.joints = {}
		self.alive = True
		self._touching = {}		# used by collision callback
		self.touching = {}		# used from outside of thread
		self.no_collision_groups = []
		self.transform = None	# used to set a transform directly, format: (pos,quat)
		self._blender_transform = None	# used by geom-only objects
		self.save_transform( bo )


	def append_subgeom( self, child ):
		assert not self.is_subgeom
		self.subgeoms.append( child )
		if self.name not in self.no_collision_groups:
			self.no_collision_groups.append( self.name )
		if self.name not in child.no_collision_groups:
			child.no_collision_groups.append( self.name )
		child.set_parent_body( self.body )

	def set_parent_body( self, body ):
		self.body = body
		self.is_subgeom = True
		if self.geom:
			self.geom.SetBody( self.body )
			pos,rot,scl = self._blender_transform
			self.geom.SetOffsetWorldPosition( *pos )
			self.geom.SetOffsetWorldQuaternion( rot )


	def reset_recording( self, buff ):
		self.transform = None
		self.recbuffer = buff

	def sync_from_ode_thread(self):
		'''
		do updates that are only safe from the ODE thread,
		or updates that need to happen before ODE collision check.
		'''
		self.touching = self._touching
		self._touching = {}

		## bodyless geoms always get updates from blender ##
		if self._blender_transform and self.geom and (not self.body or self.is_subgeom):
			geom = self.geom
			pos,rot,scl = self._blender_transform
			px,py,pz = pos
			rw,rx,ry,rz = rot
			sx,sy,sz = scl
			if self.is_subgeom:
				## problem is that a body could be offset from the armature bone, but the geoms stay in place,
				## then the offset gets updated incorrectly.
				#geom.SetOffsetWorldPosition( px, py, pz )
				#geom.SetOffsetWorldQuaternion( (rw,rx,ry,rz) )
				pass
			else:
				geom.SetPosition( px, py, pz )
				geom.SetQuaternion( (rw,rx,ry,rz) )

			if self.geomtype in 'BOX SPHERE CAPSULE CYLINDER'.split():
				sradius = ((sx+sy+sz) / 3.0) *0.5
				cradius = ((sx+sy)/2.0) * 0.5
				length = sz
				if self.geomtype == 'BOX': geom.BoxSetLengths( sx, sy, sz )
				elif self.geomtype == 'SPHERE': geom.SphereSetRadius( sradius )
				elif self.geomtype == 'CAPSULE': geom.CapsuleSetParams( sradius, length )
				elif self.geomtype == 'CYLINDER': geom.CylinderSetParams( sradius, length )

		elif self.body and self.transform and not self.is_subgeom:	# used by preview playback
			pos,rot = self.transform
			x,y,z = pos
			self.body.SetPosition( x, y, z )
			w,x,y,z = rot
			self.body.SetQuaternion( (w,x,y,z) )

	def sync( self, ob ):		# pre-sync, called before physics update

		## to make things thread-safe we need to copy these attributes from pyRNA ##
		self._friction = ob.ode_friction
		self._bounce = ob.ode_bounce
		self._soft = ob.ode_use_soft_collision
		self._soft_erp = ob.ode_soft_collision_erp
		self._soft_cfm = ob.ode_soft_collision_cfm

		pos,rot,scl = ob.matrix_world.decompose()
		px,py,pz = pos
		rw,rx,ry,rz = rot
		sx,sy,sz = scl
		if ob.type == 'MESH': sx,sy,sz = ob.dimensions

		self._blender_transform = ( (px,py,pz), (rw,rx,ry,rz), (sx,sy,sz) )	# geom uses this for record and sync

		if not self.is_subgeom and self.body and not self.transform:				# apply constant forces
			body = self.body

			x,y,z = ob.ode_local_force
			if x or y or z: body.AddRelForce( x,y,z )
			x,y,z = ob.ode_global_force
			if x or y or z: body.AddForce( x,y,z )
			x,y,z = ob.ode_local_torque
			if x or y or z: body.AddRelTorque( x,y,z )
			x,y,z = ob.ode_global_torque
			if x or y or z: body.AddTorque( x,y,z )

			rate = ob.ode_force_driver_rate
			for vec in (ob.ode_local_force, ob.ode_global_force, ob.ode_local_torque, ob.ode_global_torque):
				vec[0] *= rate
				vec[1] *= rate
				vec[2] *= rate

			x,y,z = ob.ode_constant_local_force
			if x or y or z: body.AddRelForce( x,y,z )
			x,y,z = ob.ode_constant_global_force
			if x or y or z: body.AddForce( x,y,z )
			x,y,z = ob.ode_constant_local_torque
			if x or y or z: body.AddRelTorque( x,y,z )
			x,y,z = ob.ode_constant_global_torque
			if x or y or z: body.AddTorque( x,y,z )


	def update( self, ob, now=None, recording=False, update_blender=False ):
		body = self.body
		geom = self.geom

		if body and not self.is_subgeom:
			qw,qx,qy,qz = body.GetQuaternion()
			x,y,z = body.GetPosition()
		elif geom:
			#qw,qx,qy,qz = geom.GetQuaternion()	# TODO make ctypes wrapper better
			#x,y,z = geom.GetPosition()
			pos,rot,scl = self._blender_transform
			x,y,z = pos; qw,qx,qy,qz = rot
		else:
			return

		self.position = (x,y,z)			# thread-safe to read
		self.rotation = (qw,qx,qy,qz)	# thread-safe to read

		if recording and not self.transform:	# do not record if using direct transform
			self.recbuffer.append( (now, (x,y,z), (qw,qx,qy,qz)) )

		if update_blender and body and not self.is_subgeom:		# slow because it triggers a DAG update?
			q = mathutils.Quaternion()
			q.w = qw; q.x=qx; q.y=qy; q.z=qz
			m = q.to_matrix().to_4x4()
			m[0][3] = x	# blender2.61 style
			m[1][3] = y
			m[2][3] = z
			sx,sy,sz = ob.scale		# save scale
			ob.matrix_world = m
			ob.scale = (sx,sy,sz)	# restore scale (in local space)


	##########################################################################
	##########################################################################
	def toggle_collision(self, switch):
		if not switch:
			if self.geom:
				if self.lock: self.lock.acquire()
				self.geom.Destroy()
				self.geom = None
				print('destroyed geom')
				if self.lock: self.lock.release()
			for child in self.subgeoms:
				child.toggle_collision( False )

		elif switch:
			self.reset_collision_type()
			for child in self.subgeoms:
				child.toggle_collision( True )

	def reset_collision_type(self):
		print('reset_collision_type>',self.name)
		if self.lock: self.lock.acquire()

		if self.geom:
			self.geom.Destroy()
			self.geom = None
			print('destroyed geom')

		ob = bpy.data.objects[ self.name ]
		pos,rot,scl = ob.matrix_world.decompose()
		px,py,pz = pos
		rw,rx,ry,rz = rot
		sx,sy,sz = scl
		if ob.type == 'MESH': sx,sy,sz = ob.dimensions

		self._blender_transform = ( (px,py,pz), (rw,rx,ry,rz), (sx,sy,sz) )	# sub-geom needs this for offset


		T = ob.game.collision_bounds_type
		if T in 'BOX SPHERE CAPSULE CYLINDER'.split():		#TODO: CONVEX_HULL, TRIANGLE_MESH
			self.geomtype = T
			print( '>>>new geom', T, self.name )

			sradius = ((sx+sy+sz) / 3.0) *0.5
			cradius = ((sx+sy)/2.0) * 0.5
			length = sz

			if self.body: space = self.space
			else: space = ENGINE.bodyless_space

			if T == 'BOX':
				print('>>box:', sx, sy, sz )
				self.geom = ode.CreateBox( space, sx, sy, sz )
			elif T == 'SPHERE': self.geom = ode.CreateSphere( space, sradius )
			elif T == 'CAPSULE': self.geom = ode.CreateCapsule( space, cradius, length )
			elif T == 'CYLINDER': self.geom = ode.CreateCylinder( space, cradius, length )
			#elif T == 'CONVEX_HULL': self.geom = ode.CreateConvex( self.space, planes, numplanes, points, numpoints, polys )
			geom = self.geom
			if self.body:
				print('<<<geom setting body>>>')
				geom.SetBody( self.body )
				#ENGINE.body_geoms[ self.name ] = self.geom
				if self.is_subgeom:
					self.geom.SetOffsetWorldPosition( px, py, pz )
					self.geom.SetOffsetWorldQuaternion( (rw,rx,ry,rz) )


			else:
				print('<<<bodyless geom>>>', px, py, pz)
				#ENGINE.bodyless_geoms[ self.name ] = self.geom
				print(ob.location)
				geom.SetPosition( px, py, pz )
				geom.SetQuaternion( (rw,rx,ry,rz) )

			self._geom_set_data_pointer = ctypes.pointer( ctypes.py_object(self) )	# keeping reference to pointer
			geom.SetData( self._geom_set_data_pointer )

			## not working? ##
			#ode.GeomSetCollideBits( self.geom, ctypes.c_ulong(int(randint(0,320000))) )
			#ode.GeomSetCategoryBits( self.geom, ctypes.c_ulong(int(randint(0,320000))) )
			#bits = ode.GeomGetCategoryBits( self.geom )
			#print('>>>category bits', bits)
			#bits = ode.GeomGetCollideBits( self.geom )
			#print('>>>collide bits', bits)


		if self.lock: self.lock.release()

	##########################################################################
	##########################################################################

	def pop_joint( self, name ): return self.joints.pop(name)
	def change_joint_type( self, name, type ): self.joints[name].set_type(type)

	def new_joint(self, parent=None, name='default', type='fixed'):
		'''
		attach self to parent using a ODE Joint
		'''
		assert name not in self.joints
		self.joints[name] = j = Joint(
			name, 
			parent=parent,
			child=self,
			type=type,
		)
		return j

	def set_mass( self, value ):
		print( 'set-mass',value )
		self.mass = mass = ode.Mass()
		mass.SetSphereTotal( value, 0.1)		# total mass, radius
		if self.body:
			self.body.SetMass( mass )
			if self.collision_body: self.collision_body.SetMass( mass )

	def increase_mass( self, value ):
		assert self.mass
		m = ode.Mass()
		m.SetSphereTotal( value, 0.1)
		self.mass.Add( m )


	def get_linear_vel( self ):
		if self.body: return self.body.GetLinearVel()		# localspace

	def get_average_linear_vel( self ):
		if self.body: 
			x,y,z = self.body.GetLinearVel()
			v = abs(x)+abs(y)+abs(z)
			return v/3.0

	def get_angular_vel( self ):
		if self.body: return self.body.GetAngularVel()


	def toggle_body(self, switch):
		assert not self.is_subgeom

		if switch:
			if not self.body:
				print( 'created new body', self.name )

				ob = bpy.data.objects[self.name]
				pos,rot,scl = ob.matrix_world.decompose()
				px,py,pz = pos
				rw,rx,ry,rz = rot
				sx,sy,sz = scl
				if ob.type == 'MESH': sx,sy,sz = ob.dimensions
				elif ob.type == 'EMPTY': pass	# TODO warn if draw size is not 1.0

				print('SETTING NEW BODY POS', px,py,pz)

				self.collision_body = ode.BodyCreate( ENGINE.collision_world )

				self.body = body = ode.BodyCreate( self.world )
				ENGINE.bodies[ self.name ] = body
				body.SetPosition( px,py,pz )
				body.SetQuaternion( (rw,rx,ry,rz) )
				body.SetGravityMode( ob.ode_use_gravity )
				self.set_mass( ob.ode_mass )		# reset mass
				#if self.type=='EMPTY':
				#	ob.ode_use_gravity = False	# force empties not to use gravity

				if self.geom:
					print('<<geom setting body>>')
					self.geom.SetBody( self.body )
				for child in self.subgeoms:
					child.set_parent_body( self.body )


		elif self.body:
			ENGINE.bodies.pop( self.name )
			self.body.Destroy()
			self.body = None
			for child in self.subgeoms: child.body = None
			print( 'body destroyed' )


	def reset(self):
		if self.name not in bpy.data.objects: return
		ob = bpy.data.objects[ self.name ]
		body = self.body
		if body and not self.is_subgeom:
			ob.matrix_world = self.start_matrix.copy()
			x,y,z = self.start_position
			body.SetPosition( x,y,z )
			w,x,y,z = self.start_rotation
			body.SetQuaternion( (w,x,y,z) )
			body.SetForce( .0, .0, .0 )
			body.SetTorque( .0, .0, .0 )
			body.SetLinearVel( .0, .0, .0 )
			body.SetAngularVel( .0, .0, .0 )


	def save_transform(self, bo):
		self.start_matrix = bo.matrix_world.copy()
		x,y,z = bo.matrix_world.to_translation()
		self.position = self.start_position = (x,y,z)
		w,x,y,z = bo.matrix_world.to_quaternion()
		self.rotation = self.start_rotation = (w,x,y,z)
		x,y,z = bo.matrix_world.to_scale()
		self.start_scale = (x,y,z)

	def set_transform( self, pos, rot ):
		if self.body and not self.is_subgeom:	# used by poser
			x,y,z = pos
			self.body.SetPosition( x, y, z )
			w,x,y,z = rot
			self.body.SetQuaternion( (w,x,y,z) )

