import bpy
import struct
import collections
import inspect
import ctypes

def select_callback( uid=ctypes.c_uint ):
	assert uid is not ctypes.c_uint  ## this is just used for the introspection kwargs hack

	#elif len(frame)==4:  moved to simple_action_api.py
	#	print(frame)
	#	uid = struct.unpack('<I', frame)[0]
	uid = _unpack()
	for ob in bpy.context.scene.objects: ob.select=False
	ob = get_object_by_UID( uid ) # TODO XXXXXXXXXXXX
	ob.select = True
	bpy.context.scene.objects.active = ob




_API = {
	'select': select_callback,

}


def _introspect( func ):
	a = {'callback':func, 'arguments':[], 'struct-format':None}


API = { _:_introspect(_API[_]) for _ in _API }


def _decode_args( code, data ):
	fmt = API[ code ]
	args = struct.unpack( fmt, data )
	kw = {}
	for name in API[ code ]['arguments']:
		kw[ name ] = API[ name ]



def new_action( code, args, player=None ):
	kwargs = _decode_args( code, args )


	return Action( kwargs )





class Action(object):
	def __init__(self, **kw):
		for name in kw:
			setattr(self,name, kw[name])


	def do(self):
