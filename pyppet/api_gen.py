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

def get_callbacks( ob ):
	'''
	user sets callback by name in Blender using "custom properties" (id-props)
	'''
	on_click = on_input = None
	for prop in ob.items():
		name, value = prop
		if name not in ('on_click', 'on_input'): continue
		if value not in CallbackFunction.callbacks: continue

		c = CallbackFunction.callbacks[ value ]
		if ob not in CallbackFunction.CACHE: c(ob) # TODO chance this to class method "cache_object"

		if name == 'on_click' and value in CallbackFunction.callbacks: on_click = c
		elif name == 'on_input' and value in CallbackFunction.callbacks: on_input = c

	return on_click, on_input


def get_custom_attributes( ob, convert_objects=False ):
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


##########################################################################
class CallbackFunction(object):
	CACHE = {}
	def __call__(self, _ob, **kw):
		if _ob not in self.CACHE: self.CACHE[ _ob ] = {}
		d = self.CACHE[ _ob ]
		for name in kw:
			assert name in self.arguments
			d[name] = kw[name]
		return ord(self.code)

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



class Proxy(object):
	_instances = []

	def __init__(self, ob):
		self.instance = ob
		#if id(ob)...
		Proxy.instances.append( self )

	def forget(self): Proxy.instances.remove(self)

	def generate_javascript(self): pass







