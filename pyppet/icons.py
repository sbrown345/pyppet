# _*_ coding: utf-8 _*_
BLENDER = '🐵'
PLUS = '＋'
PIN = '📌'

SUBSURF = '⛶'

BIDIRECTIONAL = '⥂'

POSITIVE_OFFSET = '⊕'
NEGATIVE_OFFSET = '⊝'

SHAPE_KEYS = '𝙎𝙝𝙖𝙥𝙚s'
SHAPE_KEYS_ICON = '𝙎𝙝𝙖𝙥𝙚𝙨'
ACTIVE_BONE = '𝘼𝙘𝙩𝙞𝙫𝙚 𝘽𝙤𝙣𝙚'
ACTIVE_BONE_ICON = '🍖'

DYNAMIC_TARGETS = '𝘿𝙮𝙣𝙖𝙢𝙞𝙘 𝙏𝙖𝙧𝙜𝙚𝙩𝙨'
DYNAMIC_TARGETS_ICON = '🎯'


WEIGHT = '⥤'
RAW_POWER = '⥴'
NORMALIZED_POWER = '⥵'

PROGRESSIVE_TEXTURES = '🔀'

DROP_HERE = '𝘥𝘳𝘰𝘱-𝘩𝘦𝘳𝘦'

STREAMING = '🔛'

WIREFRAME = '⬚'
NAME = '⎁'
AXIS = '⎋'
XRAY = '⊗'

#UnicodeEncodeError: 'utf-8' codec can't encode character '\uddbd' in position 0: surrogates not allowed
def sans_serif( txt ):
	raw = 'abcdefghijklmnopqrstuvwxyz'
	font = '𝖺𝖻𝖼𝖽𝖾𝖿𝗀𝗁𝗂𝗃𝗄𝗅𝗆𝗇𝗈𝗉𝗊𝗋𝗌𝗍𝗎𝗏𝗐𝗑𝗒𝗓'
	s = ''
	for char in txt:
		if char in raw: s += font[ raw.index(char) ]
		else: s += char
	return s


EXPANDER_UP = '⬏'
EXPANDER_DOWN = '⬎'

TOP_UI = 'ⵠ'
BOTTOM_UI = 'ᐁ'
LEFT_UI = 'ᐘ'
RIGHT_UI = 'ᐒ'

OUTLINER = '𝙊𝙪𝙩𝙡𝙞𝙣𝙚𝙧'
OUTLINER_ICON = '⑆'

TOOLS = '𝙩𝙤𝙤𝙡𝙨'

FX = '𝗙𝗫'
FX_LAYERS1 = '≗'
FX_LAYERS2 = '≘'



REFRESH = '⟳'

FFT = '𝕗𝕗𝕥'

WRITE = '✎'

KEYBOARD = '⌨'

SOUTH_WEST_ARROW = '⬋'

SOUTH_ARROW = '⇩'

CAMERA = '🎥'

MODE = '⬕'

POSE = '☊'

SPEAKER = '🔊'

LIGHT = '☼'

MATERIAL = '▧'

TEXTURE = '▩'

MICROPHONE = '🎤'

SINE_WAVE = '∿'

TARGET = '⤞'

CONSTANT_FORCES = '⇝'


BODY = '⌬'

COLLISION = '⎒'

DND = ' ⎗ '

MULTIPLY = '⨉'

DRIVERS_ICON = '🔄'
DRIVER = '⎆'
DRIVERS = '𝘿𝙧𝙞𝙫𝙚𝙧𝙨'

FORCES_ICON = '𝙁𝙤𝙧𝙘𝙚𝙨'
FORCES = '𝙁𝙤𝙧𝙘𝙚𝙨'

WEBCAM = '📹'
KINECT = '㉿'
GAMEPAD = '🎮'
WIIMOTE = '⍠'

DEVICES_ICON = '🔌'
DEVICES = '𝘿𝙚𝙫𝙞𝙘𝙚𝙨'

PHYSICS_ICON = '𝙋𝙝𝙮𝙨𝙞𝙘𝙨'
PHYSICS = '𝙋𝙝𝙮𝙨𝙞𝙘𝙨'

MODIFIERS_ICON = '🔧'
MODIFIERS = '𝙈𝙤𝙙𝙞𝙛𝙞𝙚𝙧𝙨'

CONSTRAINTS_ICON = '🔗'
CONSTRAINTS = '𝘾𝙤𝙣𝙨𝙩𝙧𝙖𝙞𝙣𝙩𝙨'

MATERIALS_ICON = '𝙈𝙖𝙩𝙚𝙧𝙞𝙖𝙡𝙨'
MATERIALS = '𝙈𝙖𝙩𝙚𝙧𝙞𝙖𝙡𝙨'

SETTINGS = 'settings'

CONTACT = '⧂'

VISIBLE_RENDER = '⎊'
VISIBLE_EDITMODE = '⌗'
VISIBLE = '⌕'
RIG_VISIBLE = '⏛'
RESTRICT_SELECTION = '⌖'

DELETE = '✗'

GRAVITY = 'ⴿ'

WEBGL = '𝙒𝙚𝙗𝙂𝙇'
WEBGL_ICON = '𝙒𝙚𝙗𝙂𝙇'

POPUP = '𝛒𝛐𝛒𝛖𝛒'

UI = '𝗨𝗶'

OVERLAY = '⎚'

FULLSCREEN = '⬚'

PLAY_PHYSICS = '⧐'

PYPPET = 'Pyppet'

PLAY = '⊳'
RECORD = '⊚'

PHYSICS_RIG_ICON = RAGDOLL = '💀'
PHYSICS_RIG = 'physics rig'

BIPED = '🏃'

ROPE = '⟅'

JOINTS_ICON = JOINT = '💪'
JOINTS = 'joints'

TRANSFORM = '⇨'

XYZ = {'x':'𝗫', 'y':'𝗬', 'z':'𝗭'}
RGB = {'r':'𝙍', 'g':'𝙂', 'b':'𝘽'}

