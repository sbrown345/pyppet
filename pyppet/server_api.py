# Simple Server API with Users
# Copyright Brett Hartshorn 2012-2013
# License: "New" BSD

import os, sys, ctypes
import bpy

## make sure we can import and load data from same directory ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.append( SCRIPT_DIR )

import Server
import simple_action_api
import api_gen
from api_gen import BlenderProxy, UserProxy
import pyppet

def default_select_callback( user=UserProxy, ob=BlenderProxy ):
	print('select callback', user, ob)
	w = api_gen.get_wrapper_objects()[ ob ]


def input_callback( ob=BlenderProxy, input_string=ctypes.c_char_p ):
	print( 'INPUT CALLBACK', input_string )

def select_callback( ob=BlenderProxy ):
	print('select callback')
	for o in bpy.context.scene.objects: o.select=False
	ob.select = True # this also makes it active for keyboard input client-side
	bpy.context.scene.objects.active = ob

API = {
	'select': default_select_callback,
	'input'	: None,
}

class UserServer( Server.WebSocketServer ):
	def start(self):
		print('[START WEBSOCKET SERVER: %s %s]' %(self.listen_host, self.listen_port))
		simple_action_api.create_callback_api( API )
		self._start_threaded()
		return True


class App( pyppet.App ):
	def start_webserver(self):
		self.server = Server.WebServer()
		#self.client = Client()
		self.websocket_server = UserServer( listen_host=Server.HOST_NAME, listen_port=8081 )
		self.websocket_server.start()	# polls in a thread

if __name__ == '__main__':
	app = App()
	print('-----create ui------')
	win = app.create_ui( bpy.context )	# bpy.context still valid before mainloop
	app.setup_3dsmax( win.get_clipboard() )
	print('-----main loop------')
	app.mainloop()
