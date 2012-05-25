# _*_ coding: utf-8 _*_

BIDIRECTIONAL = '⥂'

POSITIVE_OFFSET = '⊕'
NEGATIVE_OFFSET = '⊝'

SHAPE_KEYS = 'shape keys'
SHAPE_KEYS_ICON = '⍢'
ACTIVE_BONE = 'active bone'
ACTIVE_BONE_ICON = '⊶'

DYNAMIC_TARGETS = 'dynamic targets'
DYNAMIC_TARGETS_ICON = '⊹'


WEIGHT = '⥤'
RAW_POWER = '⥴'
NORMALIZED_POWER = '⥵'

PROGRESSIVE_TEXTURES = '⏳'

DROP_HERE = '𝘥𝘳𝘰𝘱-𝘩𝘦𝘳𝘦'

STREAMING = '𝄏'

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

OUTLINER = 'outliner'
OUTLINER_ICON = '⑆'

TOOLS = '𝙩𝙤𝙤𝙡𝙨'

FX = '𝗙𝗫'
FX_LAYERS = '☄'

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

DRIVERS_ICON = DRIVER = '⎆'
DRIVERS = 'drivers'

FORCES_ICON = '⤽'
FORCES = 'forces'

WEBCAM = '📹'
KINECT = '㉿'
GAMEPAD = '🎮'
WIIMOTE = '⍠'

DEVICES_ICON = '⥅'
DEVICES = 'devices'

PHYSICS_ICON = '⌘'
PHYSICS = 'physics'

MODIFIERS_ICON = '⑇'
MODIFIERS = 'modifiers'

CONSTRAINTS_ICON = '⧪'
CONSTRAINTS = 'constraints'

MATERIALS_ICON = '💎'
MATERIALS = 'materials'

SETTINGS = 'settings'

CONTACT = '⧂'

VISIBLE_RENDER = '⎊'
VISIBLE_EDITMODE = '⌗'
VISIBLE = '⌕'
RIG_VISIBLE = '⏛'
RESTRICT_SELECTION = '⌖'

DELETE = '✗'

GRAVITY = 'ⴿ'

WEBGL = 'webGL'
WEBGL_ICON = '⎅'

POPUP = '𝛒𝛐𝛒𝛖𝛒'

UI = '𝗨𝗶'

OVERLAY = '⎚'

FULLSCREEN = '⬚'

PLAY_PHYSICS = '⧐'

PYPPET = 'Pyppet'

PLAY = '⊳'
RECORD = '⊚'

PHYSICS_RIG_ICON = RAGDOLL = '☠'
PHYSICS_RIG = 'physics rig'

BIPED = '🏃'

ROPE = '⟅'

JOINTS_ICON = JOINT = 'ⵞ'
JOINTS = 'joints'

TRANSFORM = '⇨'

XYZ = {'x':'𝗫', 'y':'𝗬', 'z':'𝗭'}
RGB = {'r':'𝙍', 'g':'𝙂', 'b':'𝘽'}

