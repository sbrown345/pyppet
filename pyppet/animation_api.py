## Simple Animation API ##
## by Brett Hartshorn 2013 ##
## License: New BSD ##
import time, collections
import bpy, mathutils

class SimpleAnimationManager(object):
	def __init__(self):
		self.anims = []
		self.keys = {}

	def tick(self):
		now = time.time()
		done = []
		for a in self.anims:
			if a.tick( now ):
				done.append( a )

		for a in done:
			self.anims.remove( a )

	def add(self, anim):
		ob = anim.target
		attr = anim.attribute
		key = (ob,attr)
		if key in self.keys:
			a = self.keys.pop(key)
			if not a.done: a.finish()
		self.keys[ key ] = anim
		self.anims.append( anim )

AnimationManager = SimpleAnimationManager()

class AnimAPI(object):
	def animate( self, loop=False ):
		self.start_time = time.time()
		if self.delay: self.start_time += self.delay

		self.last_tick = self.start_time
		self.done = False
		self.loop = loop
		self.update_deltas()

		#AnimationManager.objects.append( self )
		AnimationManager.add( self )
		return self

	def update_deltas(self): pass

class Animations( AnimAPI ):
	def __init__(self, *anims):
		self.animations = anims
		for a in anims: a.link_animations( anims )

	def bind( self, target, attribute ):
		self.target = target
		self.attribute = attribute
		for anim in self.animations:
			anim.bind( target, attribute )
		self.animations[0].animate()

	def tick( self, T ):
		for anim in self.animations:
			if not anim.done:
				return anim.tick( T )

	def finish(self):
		for anim in self.animations:
			if not anim.done:
				anim.finish()


class Animation( AnimAPI ):
	'''
	Simple animation class that can animate python attributes: numbers, and strings.

	To animate a blender modifier:
		mod = ob.modifiers[0]
		Animation( value=xxx ).bind( mod ).animate()

	For pickling an Animation, modifiers and constaints can be later resolved using "cns = eval(bpy-path)"
		This works because on pickling we can save the path with: "bpy-path = repr(cns)"

		This true.
			assert cns == eval(repr(cns))


	'''

	def __init__(self, seconds=1.0, value=None, x=None, y=None, z=None, mode='ABSOLUTE', delay=None ):
		assert mode in ('RELATIVE', 'ABSOLUTE')
		self.mode = mode
		self.done = False
		self.value = value
		self.type = type(value)
		self.delay = delay
		self.indices = {}
		self.deltas = {}
		self.offsets = {} ## abs/rel mode ##
		if x is not None: self.indices[ 0 ] = x
		if y is not None: self.indices[ 1 ] = y
		if z is not None: self.indices[ 2 ] = z
		self.seconds = seconds
		self.animations = []
		self.callbacks = collections.OrderedDict() # keep callback order

	def get_x(self): return self.indices[0]
	def set_x(self,v): self.indices[0] = v
	x = property( get_x, set_x )

	def get_y(self): return self.indices[1]
	def set_y(self,v): self.indices[1] = v
	y = property( get_y, set_y )

	def get_z(self): return self.indices[2]
	def set_z(self,v): self.indices[2] = v
	z = property( get_z, set_z )

	def on_finished( self, callback, *args):
		self.callbacks[ callback ] = args
		return self  # so we can so singleliners like: a=Animation().on_finished(mycb)

	def link_animations(self, anims):
		self.animations = anims

	def bind( self, target, attribute=None ):
		self.target = target
		self.attribute = attribute

		if self.type is not str:
			#assert attribute in target
			if attribute not in target: ## copy from blender proxy if not already cached in view/container
				#assert isinstance(target, Container)
				internal = target()
				if hasattr(internal.proxy, attribute):
					a = getattr(internal.proxy, attribute)
					if isinstance(a, mathutils.Vector): a = list( a.to_tuple() )
					elif isinstance(a, mathutils.Euler): a = [a.x, a.y, a.z]
					target[ attribute ] = a

			if self.mode == 'RELATIVE':
				## offset value ##
				if self.indices:
					attr = self.target[ self.attribute ]
					for index in self.indices:
						self.indices[ index ] += attr[index]
				else:
					attr = self.target[ self.attribute ]
					self.value += attr

		return self

	def update_deltas(self):
		if self.type is str:
			if self.attribute in self.target:
				self.delta = len(self.target[self.attribute])
			else:
				self.delta = 0

		elif self.indices:
			attr = self.target[ self.attribute ]
			self.deltas = {}
			for index in self.indices:
				self.deltas[ index ] = self.indices[index] - attr[index]
		else:
			attr = self.target[ self.attribute ]
			self.delta = self.value - attr


	def finish(self):
		self.done = True
		if self.value is not None:
			attr = self.target[ self.attribute ]
			self.target[ self.attribute ] = self.value
		else:
			assert self.indices
			attr = self.target[self.attribute]
			for index in self.indices:
				attr[ index ] = self.indices[ index ]
			self.target[self.attribute] = attr # reassign

		if self.callbacks:
			for cb in self.callbacks:
				args = self.callbacks[cb]
				cb( *args )

		if self.animations:
			idx = self.animations.index(self)
			if idx+1 < len(self.animations):
				self.animations[ idx+1 ].animate()


	def tick( self, T ):
		assert self.target
		Dt = T - self.start_time
		if Dt >= self.seconds:
			self.finish()

		elif self.type is str:

			if self.attribute in self.target:
				attr = self.target[self.attribute]
			else:
				attr = ''
	
			if self.delta:
				if random.random()>0.5:
					self.delta -= 1
					self.target[self.attribute] = attr[:-1]
			if attr != self.value:
				if random.random()>0.3:
					n = len(attr)
					self.target[self.attribute] = self.value[:n+1]

		else:
			d = T - self.last_tick
			if not d:
				print('WARN T - self.last_tick div by zero!')
				return self.done  ## prevent divide by zero

			step = d / self.seconds
			attr = self.target[self.attribute]
			if type(attr) is mathutils.Vector:
				attr = list( attr.to_tuple() )

			if self.value is not None:
				value = attr
				value += self.delta * step
				self.target[ self.attribute ] = value

			else:
				assert self.indices
				for index in self.indices:
					value = attr[ index ]
					delta = self.deltas[ index ]
					value += delta * step
					attr[ index ] = value

				self.target[self.attribute] = attr # reassign

		self.last_tick = T

		return self.done
