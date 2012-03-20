BIDIRECTIONAL = '⥂'

POSITIVE_OFFSET = '⊕'
NEGATIVE_OFFSET = '⊝'

SHAPE_KEYS = '𝓼𝓱𝓪𝓹𝓮 𝓴𝓮𝔂𝓼'
SHAPE_KEYS_ICON = '⍢'
ACTIVE_BONE = '𝓪𝓬𝓽𝓲𝓿𝓮 𝓫𝓸𝓷𝓮'
ACTIVE_BONE_ICON = '⊶'

DYNAMIC_TARGETS = '𝓭𝔂𝓷𝓪𝓶𝓲𝓬 𝓽𝓪𝓻𝓰𝓮𝓽𝓼'
DYNAMIC_TARGETS_ICON = '⊹'


WEIGHT = '⥤'
RAW_POWER = '⥴'
NORMALIZED_POWER = '⥵'

PROGRESSIVE_TEXTURES = 'ᨖ'

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

BOTTOM_UI = 'ᐁ'
LEFT_UI = 'ᐘ'
RIGHT_UI = 'ᐒ'

OUTLINER = '𝓸𝓾𝓽𝓵𝓲𝓷𝓮𝓻'
OUTLINER_ICON = '⑆'

TOOLS = '𝙩𝙤𝙤𝙡𝙨'

FX = '𝗙𝗫'
FX_LAYERS = '𐎒'

REFRESH = '⟳'

FFT = '𝕗𝕗𝕥'

WRITE = '✎'

KEYBOARD = '⌨'

SOUTH_WEST_ARROW = '⬋'

SOUTH_ARROW = '⇩'

CAMERA = '⏣'

MODE = '⬕'

POSE = '☊'

SPEAKER = 'ↂ'

LIGHT = '☼'

MATERIAL = '▧'

TEXTURE = '▩'

MICROPHONE = '𐎘'

SINE_WAVE = '∿'

TARGET = '⤞'

CONSTANT_FORCES = '⇝'


BODY = '⌬'

COLLISION = '⎒'

DND = ' ⎗ '

MULTIPLY = '⨉'

DRIVERS_ICON = DRIVER = '⎆'
DRIVERS = '𝓭𝓻𝓲𝓿𝓮𝓻𝓼'

FORCES_ICON = '⤽'
FORCES = '𝓯𝓸𝓻𝓬𝓮𝓼'

WEBCAM = '⍜'
KINECT = '㉿'
GAMEPAD = '⚯'
WIIMOTE = '⍠'

DEVICES_ICON = '⥅'
DEVICES = '𝓭𝓮𝓿𝓲𝓬𝓮𝓼'

PHYSICS_ICON = '⌘'
PHYSICS = '𝓹𝓱𝔂𝓼𝓲𝓬𝓼'

MODIFIERS_ICON = '⑇'
MODIFIERS = '𝓶𝓸𝓭𝓲𝓯𝓲𝓮𝓻𝓼'

CONSTRAINTS_ICON = '⑈'
CONSTRAINTS = '𝓬𝓸𝓷𝓼𝓽𝓻𝓪𝓲𝓷𝓽𝓼'

MATERIALS_ICON = '▧'
MATERIALS = '𝓶𝓪𝓽𝓮𝓻𝓲𝓪𝓵𝓼'

SETTINGS = '𝓼𝓮𝓽𝓽𝓲𝓷𝓰𝓼'

CONTACT = '𐎌'

VISIBLE_RENDER = '⎊'
VISIBLE_EDITMODE = '⌗'
VISIBLE = '⌕'
RIG_VISIBLE = '⏛'
RESTRICT_SELECTION = '⌖'

DELETE = '✗'

GRAVITY = 'ⴿ'

WEBGL = '𝔀𝓮𝓫𝓰𝓵'
WEBGL_ICON = '〄'

POPUP = '𝛒𝛐𝛒𝛖𝛒'

UI = '𝗨𝗶'

OVERLAY = '⎚'

FULLSCREEN = '⬚'

PLAY_PHYSICS = '⧐'

PYPPET = 'Ⲣⲩⲣⲣⲉⲧ'

PLAY = '⊳'
RECORD = '⊚'

PHYSICS_RIG_ICON = RAGDOLL = '☠'
PHYSICS_RIG = '𝓹𝓱𝔂𝓼𝓲𝓬𝓼 𝓻𝓲𝓰'

BIPED = 'Ꮬ'

ROPE = '⟅'

JOINTS_ICON = JOINT = 'ⵞ'
JOINTS = '𝓳𝓸𝓲𝓷𝓽𝓼'

TRANSFORM = '⇨'

XYZ = {'x':'𝗫', 'y':'𝗬', 'z':'𝗭'}
RGB = {'r':'𝙍', 'g':'𝙂', 'b':'𝘽'}

