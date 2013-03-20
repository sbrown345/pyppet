# Simple Action API with binary data packing
# Copyright Brett Hartshorn 2012-2013
# License: "New" BSD

import bpy
import struct
import collections
import inspect
import ctypes

import api_gen as api

class BlenderProxy(object): pass
class UserInstance(object): pass

def get_blender_object_by_uid(uid):
	for o in bpy.data.objects:
		if o.UID == uid: return o

api.register_type( BlenderProxy, get_blender_object_by_uid )
api.register_type( UserInstance, get_blender_object_by_uid )


def generate_javascript(): return api.generate_javascript()


def new_action( code, args, user=None ):
	assert user ## require actions be taken by users
	wrapper = api.CallbackFunction.CALLBACKS[code]
	kwargs = wrapper.decode_args( args )
	print('new_action', code, args)
	return Action( user, wrapper.callback, kwargs )


class Action(object):
	def __init__(self, user, callback, kw):
		self.user = user
		self.callback = callback
		self.arguments = kw

	def do(self):
		print('doing action')
		self.callback(
			#self.user,    # pass user to the callback, allows callback to directly write on the websocket
			**self.arguments
		)


###################################################


#################################### callbacks #################################

def input_callback( ob=BlenderProxy, input_string=ctypes.c_char_p ):
	print( 'INPUT CALLBACK', input_string )

def select_callback( ob=BlenderProxy ):
	assert ob is not BlenderProxy ## this is just used for the introspection kwargs hack
	for o in bpy.context.scene.objects: o.select=False
	ob.select = True # this also makes it active for keyboard input client-side
	bpy.context.scene.objects.active = ob

def name_callback( ob=BlenderProxy ):
	for o in bpy.context.scene.objects:
		if o.type == 'FONT':
			o.data.body = ob.name

def input_form( ob=BlenderProxy, data=ctypes.c_char_p ):
	pass


def input_multi_form( user=UserInstance, ob=BlenderProxy, data=ctypes.c_char_p ):
	pass


_api = {
	'select': select_callback,
	'input' : input_callback,
	#'name'  : name_callback,
}
API = api.generate_api( _api )
print(API)

