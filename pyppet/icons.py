COOL_ICONS = 'ᚗ⤽୭୬ଷපඳශවඉ⟲⟳⤘⤌⤍⤎⤏⤑⥅⥆ܔⵛⵞⵓ𐎒𐎌𐎋〄ㄖ⇠⇡⇢⇣⇦⇧⇨⇩ᨖ▓▒░▩▦▧◍⬔⬕'

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

OUTLINER = '￼'

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
FORCES = '⌘'

BODY = '⌬'

COLLISION = '⎒'

DND = ' ⎗ '

MULTIPLY = '⨉'
SUBTRACT = '−'

DRIVER = '⎆'

WEBCAM = '⍜'
KINECT = '㉿'
GAMEPAD = '⚯'
WIIMOTE = '⍠'
PHYSICS = '𝓹𝓱𝔂𝓼𝓲𝓬𝓼'

MODIFIERS = '𝓶𝓸𝓭𝓲𝓯𝓲𝓮𝓻𝓼'
CONSTRAINTS = '𝓬𝓸𝓷𝓼𝓽𝓻𝓪𝓲𝓷𝓽𝓼'
MATERIALS = '𝓶𝓪𝓽𝓮𝓻𝓲𝓪𝓵𝓼'
SETTINGS = '𝓼𝓮𝓽𝓽𝓲𝓷𝓰𝓼'

CONTACT = 'ⴿ'

VISIBLE_RENDER = '⎊'
VISIBLE_EDITMODE = '⌗'
VISIBLE = '⌕'
RESTRICT_SELECTION = '⌖'

DELETE = '✗'

GRAVITY = '〄'

POPUP = '𝛒𝛐𝛒𝛖𝛒'

DEVICES = '𝓭𝓮𝓿𝓲𝓬𝓮𝓼'

UI = '𝗨𝗶'

OVERLAY = '⎚'

FULLSCREEN = '⬚'

PLAY_PHYSICS = '⧐'

PYPPET = 'Ⲣⲩⲣⲣⲉⲧ'

PLAY = '⊳'
RECORD = '⊚'

RAGDOLL = ''		#☠

BIPED = 'Ꮬ'

ROPE = '⟅'

JOINT = 'ⵞ'

TRANSFORM = '⇨'

XYZ = {'x':'𝗫', 'y':'𝗬', 'z':'𝗭'}
RGB = {'r':'𝙍', 'g':'𝙂', 'b':'𝘽'}

