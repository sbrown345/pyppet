# Simple Action API with binary data packing
# Copyright Brett Hartshorn 2012-2013
# License: "New" BSD

import bpy
import struct
import collections
import inspect
import ctypes

import api_gen
from api_gen import BlenderProxy, UserProxy


def generate_javascript():
	print('DEPRECATED - replace simple_action_api.generate_javascript with api_gen.generate_javascript')
	return api_gen.generate_javascript()


def new_action( code, args, user=None ):
	assert user ## require actions be taken by users
	wrapper = api_gen.CallbackFunction.CALLBACKS[code]
	kwargs = wrapper.decode_args( args )
	print('new_action', code, args)
	return Action( user, wrapper.callback, kwargs )


class Action(object):
	def __init__(self, user, callback, kw):
		self.user = user
		self.callback = callback
		self.arguments = kw

	def do(self):
		print('doing action', self.callback, self.arguments)
		self.callback(
			**self.arguments
		)



#################################### callbacks example #################################

def default_click_callback( ob=BlenderProxy ):
	print('select callback')
	for o in bpy.context.scene.objects: o.select=False
	ob.select = True # this also makes it active for keyboard input client-side
	bpy.context.scene.objects.active = ob

def default_input_callback( ob=BlenderProxy, input_string=ctypes.c_char_p ):
	print( 'INPUT CALLBACK', input_string )
	w = api_gen.get_wrapped_objects()[ ob ]
	print(w)


_api = {
	'default_click': default_click_callback,
	'default_input' : default_input_callback,
}

def create_callback_api( api=_api ): return api_gen.generate_api( api )

