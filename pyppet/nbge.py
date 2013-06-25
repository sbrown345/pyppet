## Not Blender Game Engine API ##
## by Brett Hartshorn - 2013 ##
## License: New BSD ##
import os, bpy
from animation_api import *

RELOAD_EXTERNAL_LINKED_TEXT = False
RELOAD_EXTERNAL_TEXT = False

##########################################################################
def _check_for_function_name( txt, name ):
	for line in txt.splitlines():
		line = line.strip()	# strip whitespace
		if line.startswith('def %s('%name):
			return True
	return False

def _check_for_decorator( txt, name ):
	for line in txt.splitlines():
		line = line.strip()	# strip whitespace
		if line.startswith('@%s'%name):
			return True
	return False

def actuators_to_animations( wrapper=None, actuators=None, location=True, rotation=True ):
	assert wrapper is not None
	assert actuators is not None
	loc_anims = []
	rot_anims = []
	for act in actuators:
		if act.type == 'MOTION':
			if location:
				if act.use_local_location: mode = 'RELATIVE'
				else: mode = 'ABSOLUTE'
				x,y,z = act.offset_location
				loc_anims.append(
					Animation(x=x, y=y, z=z, mode=mode)
				)

			if rotation:
				if act.use_local_rotation: mode = 'RELATIVE'
				else: mode = 'ABSOLUTE'
				x,y,z = act.offset_rotation
				rot_anims.append(
					Animation(x=x, y=y, z=z, mode=mode)
				)


	r = {}
	if len(loc_anims):
		a = Animations( *loc_anims ); r['location'] = a
		wrapper['location'] = a
	if len(rot_anims):
		a = Animations( *rot_anims ); r['rotation'] = a
		wrapper['rotation_euler'] = a

	return r

##########################################################################
def get_game_settings( ob ):
	'''
	checks an objects logic bricks, and extracts some basic logic and options from it.
	the python code will be cached and executed later.
	'''
	scripts = []
	for con in ob.game.controllers:
		if con.type != 'PYTHON': continue
		if con.text is None: continue

		script = {
			'text_block':con.text, 
			'text':con.text.as_string(),
			'clickable': False,
			'inputable': False,
			'init'  : False,
		}
		scripts.append( script )

		if con.text.filepath:
			path = bpy.path.abspath(con.text.filepath)
			if not os.path.isfile( path ):
				print('WARNING: can not find source script!')
				print(path)
			else:
				file_text = open( path, 'rb' ).read().decode('utf-8')
				if file_text != script['text']:
					#if con.text.is_library_indirect and RELOAD_EXTERNAL_LINKED_TEXT: ( text.is_library_indirect is new in blender 2.66) are text nodes that are linked in considered "indirect"
					if con.text.library and RELOAD_EXTERNAL_LINKED_TEXT:
						script['text'] = file_text
					elif not con.text.library and RELOAD_EXTERNAL_TEXT:
						script['text'] = file_text

		if len(con.actuators):
			script['actuators'] = []
			for act in con.actuators:
				script['actuators'].append( act )

		for sen in ob.game.sensors:
			if sen.type not in ('TOUCH', 'KEYBOARD'): continue
			if con.name not in sen.controllers: continue

			if sen.type == 'TOUCH':
				script['clickable'] = True
				#assert _check_for_function_name( script['text'], 'on_click' )
				assert _check_for_decorator( script['text'], 'decorators.click' )
			elif sen.type == 'KEYBOARD':
				script['inputable'] = True
				#assert _check_for_function_name( script['text'], 'on_input' )
				assert _check_for_decorator( script['text'], 'decorators.input' )

		if _check_for_decorator( script['text'], 'decorators.init' ):
			script['init'] = True

	return scripts
