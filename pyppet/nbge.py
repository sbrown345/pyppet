## Not Blender Game Engine API ##
## by Brett Hartshorn - 2013 ##
## License: New BSD ##
import os, collections, bpy
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

def actions_to_animations( wrapper=None, actuators=None, location=True, rotation=True, scale=True ):
	assert actuators is not None
	D = collections.OrderedDict()

	for act in actuators:
		if act.type != 'ACTION':
			continue
		if not act.action:
			print('WARNING: ActionActuator is missing a target Action')
			continue


		assert act.play_mode == 'PLAY' ## TODO support pingpong and others...
		loc_anims = []
		rot_anims = []
		scl_anims = []
		loc_curves = [None]*3
		rot_curves = [None]*3
		scl_curves = [None]*3
		action = act.action
		print('action name', action.name)  ## user defined name


		for f in action.fcurves:
			if f.data_path == 'location':
				loc_curves[ f.array_index ] = f

				if not loc_anims:
					loc_anims = [ Animation(seconds=k.co[0]/24.0, x=1,y=1,z=1, mode="RELATIVE") for k in f.keyframe_points ]

			if f.data_path == 'rotation_euler':
				rot_curves[ f.array_index ] = f

				if not loc_anims:
					rot_anims = [ Animation(seconds=k.co[0]/24.0, x=1,y=1,z=1, mode="RELATIVE") for k in f.keyframe_points ]

			if f.data_path == 'scale':
				scl_curves[ f.array_index ] = f

				if not scl_anims:
					scl_anims = [ Animation(seconds=k.co[0]/24.0, x=1,y=1,z=1, mode="RELATIVE") for k in f.keyframe_points ]


		if location:
			for i,anim in enumerate(loc_anims):
				anim.x = loc_curves[ 0 ].keyframe_points[ i ].co[1]
				anim.y = loc_curves[ 1 ].keyframe_points[ i ].co[1]
				anim.z = loc_curves[ 2 ].keyframe_points[ i ].co[1]

		if rotation:
			for i,anim in enumerate(rot_anims):
				anim.x = rot_curves[ 0 ].keyframe_points[ i ].co[1]
				anim.y = rot_curves[ 1 ].keyframe_points[ i ].co[1]
				anim.z = rot_curves[ 2 ].keyframe_points[ i ].co[1]

		if scale:
			for i,anim in enumerate(scl_anims):
				anim.x = scl_curves[ 0 ].keyframe_points[ i ].co[1]
				anim.y = scl_curves[ 1 ].keyframe_points[ i ].co[1]
				anim.z = scl_curves[ 2 ].keyframe_points[ i ].co[1]

		r = {}
		if len(loc_anims):
			a = Animations( *loc_anims ); r['location'] = a
			if wrapper: wrapper['location'] = a
		if len(rot_anims):
			a = Animations( *rot_anims ); r['rotation'] = a
			if wrapper: wrapper['rotation_euler'] = a

		if len(scl_anims):
			a = Animations( *scl_anims ); r['scale'] = a
			if wrapper: wrapper['scale'] = a


		if r:
			D[action.name] = r

	return D



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
class Message(object):
	def __init__(self, msg):
		assert msg.type == 'MESSAGE'
		self.name = msg.subject
		self.callback = None

		if hasattr(msg, 'body_message'):
			self.type = "OUTPUT"
			self.data = eval( msg.body_message )
			self.to = msg.to_property # (string name of object)
		else:
			self.type = "INPUT"

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
			'in_messages' : [],
			'out_messages': [],
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
				if act.type == 'MESSAGE':
					script['out_messages'].append( Message(act) )
				else:
					script['actuators'].append( act )

		for sen in ob.game.sensors:
			if con.name not in sen.controllers: continue

			if sen.type == 'MESSAGE':
				script['in_messages'].append( Message(sen) )
				continue


			if sen.type not in ('TOUCH', 'KEYBOARD'):
				continue

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



class AnimationGroup(object):
	def __init__(self, actuators):
		self.tracks = actions_to_animations( actuators=actuators ) # note, OrderedDict

	def get_track_names(self):
		return self.tracks.keys()

	def play_track(self, wrapper=None, track_name=None, location=True, rotation=True, scale=True):
		assert wrapper # need a wrapper object to play the track on
		assert track_name in self.tracks
		track = self.tracks[ track_name ]
		if 'location' in track and location:
			wrapper['location'] = track['location'] # Animations object

		if 'rotation' in track and location:
			wrapper['rotation_euler'] = track['rotation']

		if 'scale' in track and location:
			wrapper['scale'] = track['scale']

