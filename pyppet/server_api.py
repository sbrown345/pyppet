# Simple Server API with Users
# Copyright Brett Hartshorn 2012-2013
# License: "New" BSD

import os, sys, ctypes, time
import bpy

## make sure we can import and load data from same directory ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.append( SCRIPT_DIR )

import core
import Server
import simple_action_api
import api_gen
from api_gen import BlenderProxy, UserProxy

def default_select_callback( user=UserProxy, ob=BlenderProxy ):
	print('select callback', user, ob)
	w = api_gen.get_wrapper_objects()[ ob ]


def default_input_callback( user=UserProxy, ob=BlenderProxy, input_string=ctypes.c_char_p ):
	print( 'default INPUT CALLBACK', user, ob, input_string )

def select_callback( ob=BlenderProxy ):
	print('select callback')
	for o in bpy.context.scene.objects: o.select=False
	ob.select = True # this also makes it active for keyboard input client-side
	bpy.context.scene.objects.active = ob

API = {
	'select': default_select_callback,
	'input'	: default_input_callback,
}

class UserServer( Server.WebSocketServer ):
	def start(self):
		print('[START WEBSOCKET SERVER: %s %s]' %(self.listen_host, self.listen_port))
		simple_action_api.create_callback_api( API )
		self._start_threaded()
		return True


class App( core.BlenderHack ):
	def __init__(self):
		assert self.setup_blender_hack( bpy.context, use_gtk=False )
		Server.set_api( self )

	def start_server(self):
		self.server = Server.WebServer()
		self.websocket_server = UserServer( listen_host=Server.HOST_NAME, listen_port=8081 )
		self.websocket_server.start()	# polls in a thread


	def mainloop(self):
		print('enter main')
		drops = 0
		self._mainloop_prev_time = time.time()
		self.active = True
		while self.active:
			now = time.time()
			dt = 1.0 / ( now - self._mainloop_prev_time )
			self._mainloop_prev_time = now
			#print('FPS', dt)

			self.update_blender()

			#if ENGINE and ENGINE.active and not ENGINE.paused: self.update_physics( now, drop_frame )

			#win = Blender.Window( self.context.window )
			#print(win, win.winid, win.grabcursor, win.windowstate, win.modalcursor)
			#self.context.blender_has_cursor = bool( win.grabcursor )
			#if self.physics_running and self.context.scene.frame_current==1:
			#	if self.context.screen.is_animation_playing:
			#		clear_cloth_caches()

			if not self._image_editor_handle:
				# ImageEditor redraw callback will update http-server,
				# if ImageEditor is now shown, still need to update the server.
				self.server.update( self.context )

			self.websocket_server.update( self.context )

if __name__ == '__main__':
	app = App()
	app.start_server()
	print('-----main loop------')
	app.mainloop()
