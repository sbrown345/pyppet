# API Generator with binary data packing
# Copyright Brett Hartshorn 2012-2013
# License: "New" BSD

import inspect, struct, ctypes
import bpy
from bpy.props import *

#bpy.types.Object.on_click = IntProperty(
#    name="function id", description="(internal) on click function id", 
#    default=0, min=0, max=256)
#
#bpy.types.Object.on_input = IntProperty(
#    name="function id", description="(internal) on keyboard input function id", 
#    default=0, min=0, max=256)

def get_callback( name ):
	return CallbackFunction.callbacks[ name ]

def get_callbacks( ob, viewer=None ):
	a = get_wrapped_objects()[ob]
	if viewer: b = a[viewer]() # get internal
	else: b = a() # get internal
	return b.on_click, b.on_input

def get_callbacks_old( ob ):
	'''
	user sets callback by name in Blender using "custom properties" (id-props)
	'''
	on_click = on_input = None
	for prop in ob.items():
		name, value = prop
		if name not in ('on_click', 'on_input'): continue
		if value not in CallbackFunction.callbacks: continue

		c = CallbackFunction.callbacks[ value ]
		if ob not in CallbackFunction.CACHE: c(ob) # TODO change this to class method "cache_object"

		if name == 'on_click' and value in CallbackFunction.callbacks: on_click = c
		elif name == 'on_input' and value in CallbackFunction.callbacks: on_input = c

	return on_click, on_input


def get_custom_attributes_old( ob, convert_objects=False ):
	if ob not in CallbackFunction.CACHE: return None

	if convert_objects:
		d = {}
		d.update( CallbackFunction.CACHE[ob] )
		for n in d:
			if n in CallbackFunction._shared_namespace:
				T = CallbackFunction._shared_namespace[n]
				if T in CallbackFunction.TYPES:
					a = d[n]
					if hasattr( a, 'UID' ):
						d[n] = a.UID
					else:
						d[n] = id( a )
		return d
	else:
		return CallbackFunction.CACHE[ ob ]


def generate_api( a, **kw ):
	'''
	generates byte code : function wrappers
	you can require your api to always pass a first argument that is typed
	(all arguments must be type using ctypes or a object that subclasses from Proxy)
	'''
	api = {}
	for i,name in enumerate( a ):
		func = a[name] # get function
		byte_code = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'[ i ]
		api[ name ] = CallbackFunction( func, name, byte_code, **kw )
	return api

def register_type(T, unpacker): CallbackFunction.register_type(T,unpacker)

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



class Cache(object):
	objects = {} # blender object : object view
	@classmethod
	def wrap_object(cls,ob):
		assert ob not in cls.objects
		view = create_object_view( ob )
		cls.objects[ ob ] = view
		return view


class ContainerInternal(object):
	'''
	Wrapper that allows scripts to get into the hidden properties of Container.
	Scripts call the ObjectView instance to get this wrapper.
	'''
	def __init__(self, v): self.__object_view = v
	def __setattr__(self, name, value): setattr(self.__object_view, '_Container__'+name, value)
	def __getattr__(self, name): return getattr(self.__object_view, '_Container__'+name)


class Container(object):
	__properties = {} # global to all subclasses (if they do not provide their own)
	__viewers    = {} # global to all subclasses
	__parent     = None # upstream items
	__proxy      = None # "a.something = x" can trigger passing the attribute to proxy if defined
	__allow_viewers = False
	__allow_upstream_attributes = [] # this can be True (allow all) or a list of names to allow
	__allow_upstream_properties = [] # this can be True or a list of names to allow

	def __init__(self, **kw):
		for name in kw:
			setattr(self, '_Container__'+name, kw[name])

	def __call__(self, viewer=None):
		'''
		The Container only contains data attributes to keep scripting these objects simple.
		To get to the internal API of Container call the instance: "obinternal = obview()"
		'''
		if viewer:
			assert self.__allow_viewers
			assert viewer not in self.__viewers
			view = View( 
				viewer=viewer, 
				parent=self,        # for upstream properties
				proxy=self.__proxy, # copy proxy
			)
			self.__viewers[ viewer ] = view
			return view
		else:
			return ContainerInternal(self)

	################# Object Attributes ######################
	def __setattr__(self,name,value):
		'''
		a.location = (x,y,z) # set something on the blender object,
		and cache as normal attribute.
		'''
		assert not name.startswith('__')
		setattr(self, name, value)
		if self.__proxy:  ## a wrapped blender object
			setattr(self.__proxy, name, value)

	def __getattr__(self,name):
		allow = self.__allow_upstream_attributes
		if (allow is True or name in allow) and self.__parent:
			return getattr(self.__parent)

	################### Dict-Like Features ####################
	def __setitem__(self, name, value):
		'''
		a["x"] = xxx # set custom property for all viewers
		'''
		assert type(name) is str
		self.__properties[ name ] = value

	def __getitem__(self, name):
		'''
		a["x"] # get custom property
		a[viewer]["x"] # get a property local to a viewer
		'''
		if type(name) is str:
			if name in self.__properties:
				return self.__properties[ name ]
			elif (self.__allow_upstream_properties is True or name in self.__allow_upstream_properties) and self.__parent:
				assert not name.startswith('_')
				return self.__parent[ name ]
			else:
				raise KeyError
		else: # get a viewer wrapper
			if self.__allow_viewers:
				return self.__viewers[ name ]  # a[ viewer ]
			else:
				raise KeyError


class View( Container ):
	'''
	A client/player view on an object can contain its own local attributes and properties,
	if an attr/prop is not found locally, this view will check if the parent
	has that attribute - this allows for "parent attributes" and local ones.
	'''
	__allow_viewers = False  ## TODO test setting this to True and allowing viewers of a view
	__allow_upstream_properties = True # allow all
	__allow_upstream_attributes = True # allow all



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
	__allow_viewers = False  ## TODO test setting this to True and allowing viewers of a view
	__allow_upstream_properties = []
	__allow_upstream_attributes = []

def create_object_view( ob ):
	v = ObjectView(
		proxy=ob,
		on_click=CallbackFunction.callbacks[ ob.on_click ],
		on_input=CallbackFunction.callbacks[ ob.on_input ],
	)
	return v




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
	@classmethod
	def register_type(cls, T, unpacker, id_byte_size=4):
		'''
		unpacker is a function that can take the uid and return the proxy object
		'''
		assert id_byte_size in (1,2,4,8)
		cls.TYPES[ T ] = {'unpacker':unpacker,'bytes':id_byte_size}


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
		assert len(spec.args) == len(spec.defaults) ## require all keyword args and typed
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

		for arg_name, arg_hint in zip(spec.args, spec.defaults):
			if arg_name in self._shared_namespace:
				assert self._shared_namespace[ arg_name ] is arg_hint
			self._shared_namespace[ arg_name ] = arg_hint

			self.arguments.append( arg_name )
			if arg_hint in self._ctypes_to_struct_format:
				self.struct_format += self._ctypes_to_struct_format[ arg_hint ]
			else:
				self.struct_format += {1:'B', 2:'H', 4:'I', 8:'L'}[ self.TYPES[arg_hint]['bytes'] ]
			self.arg_types[arg_name] = arg_hint

		if 's' in self.struct_format:
			assert self.struct_format.count('s')==1
			assert self.struct_format.endswith('s')



	def decode_args( self, data ):
		'''
		returns keyword args, (callback needs full keyword typed args)
		'''
		kw = {}
		fmt = self.struct_format

		if fmt.endswith('s'): # special case, read one variable length string
			fmt = fmt[:-1]
			header = struct.calcsize( fmt )
			data = data[ : header ]
			string = data[ header : ]
			kw[ self.arguments[-1] ] = struct.unpack('%ss'%len(string), string)

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

		r = ['//generated function: %s' %self.name]
		a = self.arguments
		#r.append( '%s["%s"] = function ( %s ) {'%(global_container_name, self.code, ','.join(a)) )
		r.append( '%s["%s"] = function ( args ) {'%(global_container_name, self.code) )
		#r.append( '  var x = [];')

		## set function code as first byte of array to send ##
		r.append( '  var arr = [%s]; //function code'%ord(self.code))

		for i,arg_name in enumerate(a): ## TODO optimize packing
			ctype = self.arg_types[arg_name]
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


		#for i,arg_name in enumerate(a): r.append( '  arr = arr.concat( x[%s] );'%i )
		r.append('  ws.send( arr ); // send packed data to server')
		r.append('  ws.flush(); // ensure the servers gets the frame whole')
		r.append('  return arr;')
		r.append( '  }')

		return '\n'.join(r)









