# API Generator with binary data packing
# Copyright Brett Hartshorn 2012-2013
# License: "New" BSD

import time, inspect, struct, ctypes, random
import collections
try: import bpy, mathutils
except ImportError: pass

#from bpy.props import *
#bpy.types.Object.on_click = IntProperty(
#    name="function id", description="(internal) on click function id", 
#    default=0, min=0, max=256)
#
#bpy.types.Object.on_input = IntProperty(
#    name="function id", description="(internal) on keyboard input function id", 
#    default=0, min=0, max=256)

## decorators ##
_decorated = {}
_singleton_classes = {}
def _new_singleton(cls, *args, **kw): # this was ok until python 3.2.3 - invalid in python 3.3.1
	assert cls not in _singleton_classes  ## ensure a singleton instance
	#self = super(A, cls).__new__(cls)
	self = object.__new__(cls)  ## assumes that cls subclasses from object
	_singleton_classes[ cls ] = self
	for name in dir(self):
		if name in _decorated:  ## check for callbacks
			func = _decorated[ name ]
			if not inspect.ismethod( func ):
				method = getattr(self, name)
				assert inspect.ismethod( method )
				_decorated[ name ] = method

	return self

def websocket_singleton( cls ):
	'''
	class decorator @
	use __new__ to capture creation of class
	'''
	cls.__new__ = _new_singleton
	return cls

def websocket_callback(func):
	name = func.__name__
	assert name not in _decorated
	_decorated[ name ] = func
	return func

def websocket_callback_names():
	return list(_decorated.keys())

def get_decorated():
	return _decorated


def register_type(T, unpacker):
	'''
	unpacker is a function that can take the uid and return the proxy object
	'''
	cls = CallbackFunction
	#CallbackFunction.register_type(T,unpacker)
	id_byte_size=4
	assert id_byte_size in (1,2,4,8)
	cls.TYPES[ T ] = {'unpacker':unpacker,'bytes':id_byte_size}


class BlenderProxy(object): pass
class UserProxy(object): pass  ## this needs to be registered with an unpacker that can deal with your custom user class

######################################


def get_callback( name ):
	return CallbackFunction.callbacks[ name ]

def get_callbacks( ob, viewer=None ): ## deprecated
	a = get_wrapped_objects()[ob]
	if viewer: b = a[viewer]() # get internal
	else: b = a() # get internal
	return b.on_click, b.on_input



def generate_api( a, **kw ):
	'''
	generates byte code : function wrappers
	you can require your api to always pass a first argument that is typed
	(all arguments must be type using ctypes or a object that subclasses from Proxy)
	'''
	api = {}
	a.update(
		{'generic_on_click':generic_on_click, 'generic_on_input':generic_on_input}
	)
	for i,name in enumerate( a ):
		func = a[name] # get function
		byte_code = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'[ i ]
		api[ name ] = CallbackFunction( func, name, byte_code, **kw )
	print('generate_api', api)
	return api


def get_game_settings( ob ):
	scripts = []
	for con in ob.game.controllers:
		if con.type != 'PYTHON': continue
		script = {
			'text_block':con.text, 
			'text':con.text.as_string(),
			'clickable': False,
			'inputable': False,
		}
		scripts.append( script )

		for act in con.actuators:
			if act.type == 'MOTION': pass

		for sen in ob.game.sensors:
			if sen.type not in ('TOUCH', 'KEYBOARD'): continue
			if con.name not in sen.controllers: continue

			if sen.type == 'TOUCH':
				script['clickable'] = True
				assert _check_for_function_name( script['text'], 'on_click' )
			elif sen.type == 'KEYBOARD':
				script['inputable'] = True
				assert _check_for_function_name( script['text'], 'on_input' )

	return scripts


def generate_javascript():
	g = '_callbacks_'
	a = ['var %s = {};'%g]
	for cb in CallbackFunction.CALLBACKS.values():
		a.append( cb.generate_javascript(g) )
	return '\n'.join( a )


def get_wrapped_objects():
	return Cache.objects

def wrap_object( ob ):
	return Cache.wrap_object(ob )

###################################################



class CacheSingleton(object):
	def __init__(self):
		self.objects = {} # blender object : object view
	#@classmethod
	def wrap_object(cls,ob):
		#assert ob not in cls.objects  ## threading?
		if ob not in cls.objects:
			view = create_object_view( ob )
			cls.objects[ ob ] = view
			return view

Cache = CacheSingleton()


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
		self.x = x; self.y = y; self.z = z
		self.indices = {}
		self.deltas = {}
		self.offsets = {} ## abs/rel mode ##
		if x is not None: self.indices[ 0 ] = x
		if y is not None: self.indices[ 1 ] = y
		if z is not None: self.indices[ 2 ] = z
		self.seconds = seconds
		self.animations = []
		self.callbacks = collections.OrderedDict() # keep callback order

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
				assert isinstance(target, Container)
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

class ContainerInternal(object):
	'''
	Wrapper that allows scripts to get into the hidden properties of Container.
	Scripts call the ObjectView instance to get this wrapper.
	'''
	def __init__(self, v): self.__dict__['__object_view'] = v
	def __setattr__(self, name, value): setattr(self.__dict__['__object_view'], '_Container__'+name, value)
	def __getattr__(self, name): return getattr(self.__dict__['__object_view'], '_Container__'+name)


class Container(object):
	#__properties = {} # global to all subclasses (if they do not provide their own)
	#__viewers    = {} # global to all subclasses - thanks Miran.
	__parent     = None # upstream items
	__proxy      = None # "a['something'] = x" can trigger passing the attribute to proxy if defined
	__allow_viewers = False
	__allow_upstream_attributes = [] # this can be True (allow all) or a list of names to allow
	__allow_upstream_properties = [] # this can be True or a list of names to allow

	def __init__(self, **kw):
		self.__properties = {}
		self.__subproperties = {}
		self.__viewers = {}
		self.__eval_queue = []
		self.__proxy = None
		self.__sproxy = None
		self.__sproxy_attrs = []
		for name in kw: setattr(self, '_Container__'+name, kw[name])

	def __subproxy(self, sproxy, *names ):
		'''
		This can be used to have a second proxy where some named items
		will get set on the subproxy instead of the main proxy.
		'''
		assert len(names)
		self.__sproxy = sproxy
		self.__sproxy_attrs = names
		for name in names: assert hasattr(sproxy, name)


	def __eval(self, *args):
		if args: self.__eval_queue.extend( args )

	def __call__(self, viewer=None, reset=False ):
		'''
		The Container only contains data attributes to keep scripting these objects simple.
		To get to the internal API of Container call the instance: "obinternal = obview()"
		'''
		if viewer:
			assert self.__allow_viewers
			#assert viewer not in self.__viewers
			if viewer not in self.__viewers:
				view = View( 
					viewer=viewer, 
					parent=self,        # for upstream properties
					proxy=self.__proxy, # use same proxy
					sproxy=self.__sproxy,
					sproxy_attrs=self.__sproxy_attrs,
					allow_upstream_attributes=True,
					allow_upstream_properties=True,
					#allow_viewers=True,
				)
				self.__viewers[ viewer ] = view
			view = self.__viewers[ viewer ]
			#view( reset=True )
			return view

		elif reset:  ## restore proxy attributes to view
			assert self.__proxy
			pnames = dir(self.__proxy)
			for n in dir(self):
				if n.startswith('_'): continue
				if n in pnames:
					attr = self.__dict__[n]
					setattr(self.__proxy, n, attr)

		else:
			return ContainerInternal(self)

	################# Object Attributes ######################
	#def __setattribute__(self,name,value):
	def __setattr__(self,name,value):
		'''
		a.location = (x,y,z) # set something on the blender object,
		and cache as normal attribute.
		'''
		assert not name.startswith('__')
		self.__dict__[name] = value

	def __getattr__(self,name):
		allow = self.__allow_upstream_attributes
		if (allow is True or name in allow) and self.__parent:
			return getattr(self.__parent, name)

	################### Dict-Like Features ####################
	def __dir__(self):
		keys = list( self.__properties.keys() )
		allow = self.__allow_upstream_attributes
		if allow:
			if allow is True:
				if self.__parent:
					keys.extend( dir(self.__parent) )
			else:
				assert type(allow) is list
				keys.extend( allow )
		return keys

	def __contains__(self, name):
		allow = self.__allow_upstream_attributes
		if name in self.__properties:
			return True
		elif (allow is True or name in allow) and self.__parent and name in self.__parent:
			return True
		else:
			return False

	def __setitem__(self, name, value):
		'''
		a["x"] = xxx # set custom property for all viewers,
		also sets the value on the proxy, if there is a proxy,
		and the proxy has an attribute of the same name.
		note: watch out for the names in your proxy and the names
		used purely as custom attributes do not conflict

		## note python3 switched to using a slice object (no slicing is used here anyways)
		'''

		if isinstance(value, Animation):
			anim = value
			anim.bind( self, name )
			anim.animate()

		elif isinstance(value, Animations):
			value.bind( self, name )

		else:
			assert type(name) is str

			## DEPRECATED ##
			#if name.startswith('.'): # special syntax for substructures: a['.attr[0].subattr']
			#	assert self.__proxy
			#	self.__subproperties[name] = value
			#	a = name.replace('[', ' ').replace(']', ' ').replace('"', ' ').split()
			#	attr, key, subattr = a
			#	item = getattr(self.__proxy, attr)[ int(key) ]
			#	setattr(item, subattr, value)
			#
			#else:

			self.__properties[ name ] = value
			p = self.__proxy
			if self.__sproxy and name in self.__sproxy_attrs: p = self.__sproxy

			if p and name in dir(p):  ## a wrapped blender object
				do = True
				if type(value) is list:
					if len(value) != len(getattr(p,name)): do = False
				if do:
					setattr(p, name, value)


	def __getitem__(self, name):
		'''
		a["x"] # get custom property
		'''
		if type(name) is str:
			if name in self.__properties:
				return self.__properties[ name ]
			elif (self.__allow_upstream_properties is True or name in self.__allow_upstream_properties) and self.__parent:
				assert not name.startswith('_')
				return self.__parent[ name ]
			else:
				raise KeyError

		else:
			raise KeyError

class View( Container ):
	'''
	A client/player view on an object can contain its own local attributes and properties,
	if an attr/prop is not found locally, this view will check if the parent
	has that attribute - this allows for "parent attributes" and local ones.
	'''
	#__allow_viewers = True  ## TODO test allowing viewers of a view
	#__allow_upstream_properties = True # allow all
	#__allow_upstream_attributes = True # allow all
	pass


class ObjectView( Container ):
	'''
	Caching and Database proxy object.
	a = ObjectView(blender_object)
	a.location = (1,2,3)  # caches tuple and assigns location to wrapped blender object
	a["location"] = (1,2,3) # save custom attribute, not assigned to wrapped, broadcast to all viewers.
	a[viewer1]['some_local_attribute'] = 'xxx' # sets attribute only for viewer1
	a[viewer2][...]

	Calling an ObjectView will return a wrapper of the view, required to get the callbacks.
	b = a()
	on_click_callback = b.on_click
	'''
	#__allow_viewers = True
	#__allow_upstream_properties = []
	#__allow_upstream_attributes = []
	pass

# monkey patch this to allow the blender user to attach properties to objects from blender
USER_CUSTOM_ATTRIBUTES = ['text_flip']

def compile_script( text ):
	exec( text )
	return locals()

def create_object_view( ob ):
	print('------------create object view-----------')
	on_click = None #'default_click' # defaults for testing
	on_touch = None #'default_touch' # TODO
	on_input = None #'default_input'  # defaults for testing

	############ Blender's ID-Props API #########
	user_props = {}
	special_attrs = {}
	if hasattr(ob, 'items'):
		print('////////checking blender id props////////')
		for prop in ob.items():
			name, value = prop
			if name == '_RNA_UI': continue  # used by blender internally

			if name == 'on_click':
				on_click = value
			elif name == 'on_input':
				on_input = value
			elif name in USER_CUSTOM_ATTRIBUTES:
				user_props[ name ] = value
			else:
				print('WARN unknown id-prop:', name, value)
				raise RuntimeError

	#if hasattr(ob, 'name') and ob.name in CallbackFunction.callbacks:
	#	print('auto hooking object by name to callback function')
	#	on_click = ob.name
	for script in get_game_settings( ob ):
		if script['clickable']:
			on_click = 'generic_on_click'
			c = compile_script( script['text'] )

			classes = []
			for a in c.values():
				if inspect.isclass( a ):
					classes.append( a )

			if 'on_click' in c and inspect.isfunction( c['on_click'] ):
				special_attrs['on_click_callback'] = c['on_click']  ## simple function

			elif len(classes):
				assert len(classes) == 1  ## we can support multiple classes with user decorators
				instance = classes[0]()   ## what args should be passed to instance?
				method = getattr( instance, 'on_click' )
				special_attrs[ 'on_click_callback' ] = method

			else:
				raise RuntimeError


		if script['inputable']:
			on_input = 'generic_on_input'

	#############################################
	print(ob, on_click, on_input)
	if on_click:
		if on_click in CallbackFunction.callbacks:
			on_click = CallbackFunction.callbacks[ on_click ]
			user_props[ 'clickable' ] = True
		else:
			print(CallbackFunction.callbacks)
			print('WARNING: undefined callback:', on_click)
			raise RuntimeError
	if on_input:
		if on_input in CallbackFunction.callbacks:
			on_input = CallbackFunction.callbacks[ on_input ]
		else:
			print('WARNING: undefined callback:', on_input)
			raise RuntimeError

	v = ObjectView(
		proxy=ob,
		on_click=on_click,
		on_input=on_input,
		label=None,
		allow_viewers=True,
	)
	if user_props:
		for name in user_props:
			v[ name ] = user_props[ name ]

	if special_attrs:
		for name in special_attrs:
			setattr(v, name, special_attrs[name])

	return v

##########################################################################
def _check_for_function_name( txt, name ):
	for line in txt.splitlines():
		line = line.strip()	# strip whitespace
		if line.startswith('def %s('%name):
			return True



##########################################################################

class CallbackFunction(object):
	#CACHE = {}
	#def __call__(self, _ob, **kw):
	#	if _ob not in self.CACHE: self.CACHE[ _ob ] = {}
	#	d = self.CACHE[ _ob ]
	#	for name in kw:
	#		assert name in self.arguments
	#		d[name] = kw[name]
	#	return ord(self.code)

	CALLBACKS = {} ## byte-code : function wrapper
	callbacks = {} ## orig name : function wrapper
	TYPES = {}  ## each type will need its own custom unpacking functions that take some ID.
	#@classmethod
	#def register_type(cls, T, unpacker, id_byte_size=4):
	#	'''
	#	unpacker is a function that can take the uid and return the proxy object
	#	'''
	#	assert id_byte_size in (1,2,4,8)
	#	cls.TYPES[ T ] = {'unpacker':unpacker,'bytes':id_byte_size}


	_ctypes_to_struct_format = {
		ctypes.c_uint32 :'I',
		ctypes.c_int32  :'i',
		ctypes.c_uint16 :'H',
		ctypes.c_int16  :'h',
		ctypes.c_float  :'f',
		ctypes.c_char_p :'s', # special array of char
	}


	_shared_namespace = {} # keyword args in callbacks are all in the same namespace

	def __init__( self, func, name, code, require_first_argument=None ):
		spec = inspect.getargspec( func )
		if spec.args and spec.args[0]=='self':
			self.is_method = True
			args = spec.args[ 1: ]
			if inspect.ismethod( func ):
				self.is_method_bound = True
			else:
				self.is_method_bound = False
				## TODO allow unbound methods ##
				print(func, name)
				raise RuntimeError('you must resolve these to functions or methods on a singleton instance')

		else:
			self.is_method = False
			args = spec.args

		assert len(args) == len(spec.defaults) ## require all keyword args and typed

		self.CALLBACKS[ code ] = self
		self.callbacks[ name ] = self

		self.name = name
		self.callback = func
		self.code = code

		self.arguments = [] 
		self.struct_format = '<' # always little endian?
		self.arg_types = {}

		if require_first_argument:
			assert spec.defaults[0] is require_first_argument

		for arg_name, arg_hint in zip(args, spec.defaults):
			if arg_name in self._shared_namespace: assert self._shared_namespace[ arg_name ] is arg_hint
			self._shared_namespace[ arg_name ] = arg_hint

			if arg_hint is BlenderProxy: assert arg_name == 'ob'
			elif arg_hint is UserProxy: assert arg_name == 'user'

			self.arguments.append( arg_name )
			if arg_hint in self._ctypes_to_struct_format:
				self.struct_format += self._ctypes_to_struct_format[ arg_hint ]
			else:
				self.struct_format += {1:'B', 2:'H', 4:'I', 8:'L'}[ self.TYPES[arg_hint]['bytes'] ]
			self.arg_types[arg_name] = arg_hint

		if 's' in self.struct_format:
			assert self.struct_format.count('s')==1  # only a single variable length string is allowed at the end
			assert self.struct_format.endswith('s')
			self.sends_string_data = True
		else:
			self.sends_string_data = False


	def decode_args( self, data ):
		'''
		returns keyword args, (callback needs full keyword typed args)
		'''
		kw = {}
		fmt = self.struct_format

		if fmt.endswith('s'): # special case, read one variable length string
			fmt = fmt[:-1]
			header = struct.calcsize( fmt ); print('header', header)
			string = data[ header : ].decode('utf-8'); print('string', string)
			data = data[ : header ]; print('data', data)
			#a = struct.unpack('%ss'%len(string), string)[0].decode('utf-8')
			#print(a)
			kw[ self.arguments[-1] ] = string

		if data: # packed data can precede variable length string data
			args = struct.unpack( fmt, data )  ## unpack data

			for i,name in enumerate( self.arguments ):  ## check for UID's and replace them with real objects
				if name in kw: continue
				ctype = self.arg_types[name]
				if ctype in self.TYPES:
					## the user must provide the unpacker function, takes UID and returns a object
					kw[ name ] = self.TYPES[ ctype ]['unpacker']( args[i] )
				else:
					kw[ name ] = args[i]  ## already unpacked above

		return kw



	def size_of(self, T):
		if T in self.TYPES:
			return  self.TYPES[ T ][ 'bytes' ]  # return ID size in bytes (ID's can be 8,16,32,64bits)
		else:
			return ctypes.sizeof( T )

	def proxy_to_js_buffer_type(self, T):
		b = self.TYPES[T]['bytes']
		if b==1: return 'Uint8Array'
		elif b==2: return 'Uint16Array'
		elif b==4: return 'Uint32Array'
		elif b==8:
			#return 'Uint64Array'
			raise NotImplemented

	_ctype_to_js_buffer_type = {
		ctypes.c_float: 'Float32Array',
		ctypes.c_int32: 'Int32Array',
		ctypes.c_uint32: 'Uint32Array',
		ctypes.c_int16: 'Int16Array',
		ctypes.c_uint16: 'Uint16Array',
	}

	def generate_javascript(self, global_container_name):
		'''
		Genereate javascript functions that send binary data on the websocket.
		The server needs to call this and insert it into the javascript sent
		to the client.
		'''
		if self.sends_string_data:
			## the javascript client needs to capture window.addEventListener 'keypress'
			## and pass the newline to the "selected" object's .do_on_input_callback(txt)
			r = ['//generated string function: %s' %self.name]
			r.append( '%s["%s"] = function ( args, txt ) {'%(global_container_name, self.code) )

		else:
			r = ['//generated binary function: %s' %self.name]
			r.append( '%s["%s"] = function ( args ) {'%(global_container_name, self.code) )

		## set function code as first byte of array to send ##
		r.append( '  var arr = [%s]; //function code'%ord(self.code))

		binary = False
		for i,arg_name in enumerate( self.arguments): ## TODO optimize packing
			ctype = self.arg_types[arg_name]
			if ctype is ctypes.c_char_p: continue
			binary = True
			size = self.size_of( ctype )
			r.append( '  //%s' %arg_name)
			r.append( '  var buffer = new ArrayBuffer(%s);'%size )
			r.append( '  var bytesView = new Uint8Array(buffer);' )
			if ctype in self.TYPES:
				r.append( '  var view = new %s(buffer);' %self.proxy_to_js_buffer_type(ctype) )
				r.append( '  if (args.%s._uid_ != undefined) {'%arg_name) # allow object or direct uid
				r.append( '  view[0] = args.%s._uid_;'%arg_name )
				r.append( '  } else { view[0] = args.%s }' %arg_name)
			else:
				r.append( '  var view = new %s(buffer);' %self._ctype_to_js_buffer_type[ctype] )
				r.append( '  view[ 0 ] = args.%s;'%arg_name )
			r.append( '  arr = arr.concat( Array.apply([],bytesView) );')

		## always sending the function id in binary (might not be a single byte in the future)

		if self.sends_string_data:
			#r.append('	ws.send_string( txt );')
			r.append('	arr = arr.concat( txt.split("").map(function(c){return c.charCodeAt(0);}) );')

		r.append('  ws.send( arr ); // send packed data to server')

		r.append('  ws.flush(); // ensure the servers gets the frame whole')
		r.append('  return arr;')
		r.append( '  }')

		return '\n'.join(r)

#####################################################################################
def get_blender_object_by_uid(uid):
	for o in bpy.data.objects:
		if o.UID == uid: return o

register_type( BlenderProxy, get_blender_object_by_uid )

def generic_on_click(user=UserProxy, ob=BlenderProxy):
	'''
	the wrapper.on_click_callback is defined by the blender-user,
	from the BGE (blender game engine) logic bricks editor they need to create
	or link in a TextNode and attach it to the Python-controller in the logic editor,
	for each object that will have a given on click callback.
	The Python script in the TextNode must define a function called: "on_click"
	And, the Python-controller must have a Touch sensor as input.
	'''
	wrapper = get_wrapped_objects()[ob]
	wrapper.on_click_callback(
		wrapper=wrapper,
		user=user, 
		object=ob,
		view=wrapper( user ),
	)


def generic_on_input(user=UserProxy, ob=BlenderProxy, input_string=ctypes.c_char_p):
	'''
	this works the same as the above on click callback.

	blender example:
		def on_input( wrapper=None, user=None, object=None, view=None, text=None ):
			print(text)
	'''
	wrapper = get_wrapped_objects()[ob]
	wrapper.on_input_callback(
		wrapper=wrapper,
		user=user,
		object=ob,
		view=wrapper( user ),
		text=input_string.strip()
	)



if __name__ == '__main__':
	o = 'some object'
	w = wrap_object( o )
	print(w)
	v1 = 'some viewer1'
	v2 = 'some viewer2'
	view1 = w( v1 )
	view2 = w( v2 )
	view1['hi'] = 1
	view2['hi'] = 2
	assert 'hi' in view1

	print(view1, view1['hi'])
	print(view2, view2['hi'])
	v1i = view1()
	v2i = view2()
	print(v1i.properties)
	print(v2i.properties)

	assert view1['hi'] != view2['hi']

	## upstream properties
	w['up'] = 'xxx'
	assert view1['up'] == 'xxx'
	assert 'up' in view1
	print( view1['up'] )
