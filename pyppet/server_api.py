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

def default_click_callback( user=UserProxy, ob=BlenderProxy ):
	print('select callback', user, ob)
	w = api_gen.get_wrapper_objects()[ ob ]


def default_input_callback( user=UserProxy, ob=BlenderProxy, input_string=ctypes.c_char_p ):
	print( 'default INPUT CALLBACK', user, ob, input_string )
	if ob.name == 'login':
		if 'login.input' not in bpy.data.objects:
			a = bpy.data.objects.new(
				name="[data] %s"%name, 
				object_data= a.data 
			)
			bpy.context.scene.objects.link( a )
			a.parent = ob


API = {
	'default_click': default_click_callback,
	'default_input'	: default_input_callback,
}
simple_action_api.create_callback_api( API )

class UserServer( Server.WebSocketServer ):
	def start(self):
		print('[START WEBSOCKET SERVER: %s %s]' %(self.listen_host, self.listen_port))
		self._start_threaded()
		return True


class App( core.BlenderHack ):
	def __init__(self):
		print('init server app')
		self.setup_blender_hack( bpy.context, use_gtk=False, headless=True )
		print('blender hack setup ok')
		Server.set_api( self )
		print('custom api set')

	def start_server(self):
		#self.server = Server.WebServer()
		self.websocket_server = UserServer( listen_host=Server.HOST_NAME, listen_port=8080 )
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

			fully_updated = self.update_blender()

			#if ENGINE and ENGINE.active and not ENGINE.paused: self.update_physics( now, drop_frame )

			#win = Blender.Window( self.context.window )
			#print(win, win.winid, win.grabcursor, win.windowstate, win.modalcursor)
			#self.context.blender_has_cursor = bool( win.grabcursor )
			#if self.physics_running and self.context.scene.frame_current==1:
			#	if self.context.screen.is_animation_playing:
			#		clear_cloth_caches()

			if not fully_updated:
				# ImageEditor redraw callback will update http-server,
				# if ImageEditor is now shown, still need to update the server.
				#self.server.update( self.context )
				pass

			self.websocket_server.update( self.context, timeout=0.03 )
			time.sleep(0.01)

if __name__ == '__main__':
	app = App()
	app.start_server()
	print('-----main loop------')
	app.mainloop()
