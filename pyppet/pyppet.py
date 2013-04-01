# _*_ coding: utf-8 _*_
# Pyppet2 - Copyright Brett Hartshorn 2012-2013
# License: "New" BSD
################################################################
VERSION = '1.9.8a'
################################################################
import os, sys, time, subprocess, threading, math, socket, ctypes
import wave
from random import *

## make sure we can import and load data from same directory ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.append( SCRIPT_DIR )

print('='*80)
print('loading core')
from core import *		# core API
print('='*80)
print('checking for collada export')
# blender apt-get native builds are missing Collada support
if hasattr( Blender.Scene( bpy.context.scene ), 'collada_export' ):
	USE_COLLADA = True
else:
	USE_COLLADA = False

print('='*80)
print('INIT-1 OK')


if sys.platform.startswith('win'):
	#dll = ctypes.CDLL('')	# this won't work on Windows
	#print(dll, dll._handle)	# _handle is a number address, changes each time

	#h=ctypes.windll.kernel32.GetModuleHandleW(None)
	h=ctypes.windll.kernel32.GetModuleHandleA(None)

	print(h)
	#from ctypes import wintypes
	#blender = ctypes.CDLL('blender.exe')
	#GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
	#GetCurrentProcess.restype = wintypes.HANDLE
	#phandle = GetCurrentProcess()
	#print(phandle)
	blender = ctypes.CDLL( '', handle=h )
	print(blender)
	func = blender.glPushMatrix
	print( func )
	func = blender.CTX_wm_window
	print( func )
	assert 0

	cygwin = ctypes.CDLL( 'cygwin1.dll' )
	print( cygwin )
	dlopen = cygwin.dlopen		# dlopen defined in dlfcn.h
	dlopen.argtypes = (ctypes.c_char_p, ctypes.c_int)
	dlopen.restype = ctypes.c_void_p
	#err:ntdll:RtlpWaitForCriticalSection section 0x610d1ef8 "?" wait timed out in thread 0018, blocked by 0000, retrying (60 sec)
	handle = dlopen( ctypes.c_char_p(b''), 2 )		# blocks
	print(handle)
	assert 0

from openGL import *
import SDL as sdl
import fluidsynth as fluid

import openal as al
if hasattr(al,'OpenDevice'): USE_OPENAL = True
else: USE_OPENAL = False


import fftw
#import cv
#import highgui as gui

import Webcam
import Kinect
import Wiimote
import Blender
import Physics
import Server
import server_api

import icons

import bpy, mathutils
from bpy.props import *

sdl.Init( sdl.SDL_INIT_JOYSTICK )

ENGINE = Physics.ENGINE		# physics engine singleton


## server code moved to Server.py

def ensure_unique_ids():
	pass	# TODO

#######################################################################
def rgb2gdk( r, g, b ): return gtk.GdkColor(0,int(r*65535),int(g*65535),int(b*65535))
def gdk2rgb( c ): return (c.red/65536.0, c.green/65536.0, c.blue/65536.0)

BLENDER_GREY = 114.0 / 255.0
USE_BLENDER_GREY = False

if USE_BLENDER_GREY:
	BG_COLOR = rgb2gdk( BLENDER_GREY, BLENDER_GREY, BLENDER_GREY )
	#BG_COLOR = rgb2gdk( 0.94, 0.94, 0.96 )
	BG_COLOR_DARK = rgb2gdk( 0.5, 0.5, 0.5 )
	DRIVER_COLOR = gtk.GdkRGBA(0.2,0.4,0.0,1.0)	# deprecate

def color_set( button, color, ob ):
	button.get_color( color )
	r,g,b = gdk2rgb( color )
	ob.color[0] = r
	ob.color[1] = g
	ob.color[2] = b



##############################
class AudioThread(object):
	lock = threading._allocate_lock()		# not required

	def __init__(self):
		self.active = False
		self.output = al.OpenDevice()
		self.context = al.CreateContext( self.output )
		al.MakeContextCurrent( self.context )
		self.microphone = Microphone( analysis=True, streaming=False )

		if hasattr(fluid,'new_fluid_synth'):
			self.synth = SynthMachine()
			self.synth.setup()
		else:
			self.synth = None

	def update(self):		# called from main #
		if self.active: self.microphone.sync()

	def loop(self):
		while self.active:
			self.microphone.update()
			if self.synth: self.synth.update()
			time.sleep(0.05)
		print('[audio thread finished]')
		self.microphone.close()

	def start(self):
		self.active = True
		threading._start_new_thread(self.loop, ())
		#threading._start_new_thread(Speaker.thread, ())


	def exit(self):
		print('[audio thread exit]')
		self.active = False
		time.sleep(0.1)
		if self.synth: self.synth.active = False

		#ctx=al.GetCurrentContext()
		#dev = al.GetContextsDevice(ctx)
		al.DestroyContext( self.context )
		if self.output: al.CloseDevice( self.output )



##############################
class Speaker(object):
	#Speakers = []
	#@classmethod
	#def thread(self):
	#	while True:
	#		AudioThread.lock.acquire()
	#		for speaker in self.Speakers:
	#			speaker.update()
	#		AudioThread.lock.release()
	#		time.sleep(0.1)

	def __init__(self, frequency=22050, stereo=False, streaming=False):
		#Speaker.Speakers.append( self )
		if stereo: self.format=al.AL_FORMAT_STEREO16
		else: self.format=al.AL_FORMAT_MONO16
		self.frequency = frequency
		self.streaming = streaming
		self.buffersize = 1024
		self.playing = False

		array = (ctypes.c_uint * 1)()
		al.GenSources( 1, array )
		assert al.GetError() == al.AL_NO_ERROR
		self.id = array[0]

		self.output_buffer_index = 0
		self.output_buffer_ids = None
		self.num_output_buffers = 16
		self.trash = []
		self.generate_buffers()

		self.gain = 1.0
		self.pitch = 1.0

	def cache_samples(self, samples):
		assert self.streaming == False
		self.generate_buffers()
		bid = self.output_buffer_ids[0]
		n = len(samples)
		data = (ctypes.c_byte*n)( *samples )
		ptr = ctypes.pointer( data )
		al.BufferData(
			bid,
			self.format, 
			ptr, 
			n, # size in bytes
			self.frequency,
		)
		al.Sourcei( self.id, al.AL_BUFFER, bid )


	def get_widget(self):
		root = gtk.HBox()
		bx = gtk.VBox(); root.pack_start( bx )
		slider = Slider( self, name='gain', driveable=True )
		bx.pack_start( slider.widget, expand=False )
		slider = Slider( self, name='pitch', driveable=True )
		bx.pack_start( slider.widget, expand=False )
		return root



	def generate_buffers(self):
		self.output_buffer_ids = (ctypes.c_uint * self.num_output_buffers)()
		al.GenBuffers( self.num_output_buffers, ctypes.pointer(self.output_buffer_ids) )
		assert al.GetError() == al.NO_ERROR


	def play(self, loop=False):
		self.playing = True
		al.SourcePlay( self.id )
		assert al.GetError() == al.NO_ERROR
		if loop: al.Sourcei( self.id, al.LOOPING, al.TRUE )

	def stop(self):
		al.SourceStop( self.id )
		assert al.GetError() == al.NO_ERROR


	def stream( self, array ):
		self.output_buffer_index += 1
		if self.output_buffer_index == self.num_output_buffers:
			self.output_buffer_index = 0
			self.generate_buffers()
		bid = self.output_buffer_ids[ self.output_buffer_index ]

		pointer = ctypes.pointer( array )
		bytes = len(array) * 2	# assume 16bit audio

		al.BufferData(
			bid,
			self.format, 
			pointer, 
			bytes,
			self.frequency,
		)
		assert al.GetError() == al.NO_ERROR

		al.SourceQueueBuffers( self.id, 1, ctypes.pointer(ctypes.c_uint(bid)) )
		assert al.GetError() == al.NO_ERROR

		self.trash.insert( 0, bid )

		ret = ctypes.pointer( ctypes.c_int(0) )
		al.GetSourcei( self.id, al.SOURCE_STATE, ret )
		if ret.contents.value != al.PLAYING:
			#AudioThread.lock.acquire()
			#print('RESTARTING PLAYBACK')
			self.play()
			#AudioThread.lock.release()

		self.update()

	def update(self):
		if not self.playing: return

		seconds = ctypes.pointer( ctypes.c_float(0.0) )
		al.GetSourcef( self.id, al.SEC_OFFSET, seconds )
		self.seconds = seconds.contents.value

		info = {}
		ret = ctypes.pointer( ctypes.c_int(0) )
		for tag in 'BYTE_OFFSET SOURCE_TYPE LOOPING BUFFER SOURCE_STATE BUFFERS_QUEUED BUFFERS_PROCESSED'.split():
			param = getattr(al, tag)
			al.GetSourcei( self.id, param, ret )
			info[tag] = ret.contents.value


		if self.streaming:
			#print( 'buffers processed', info['BUFFERS_PROCESSED'] )
			#print( 'buffers queued', info['BUFFERS_QUEUED'] )
			n = info['BUFFERS_PROCESSED']
			if n >= 1:
				#AudioThread.lock.acquire()
				ptr = (ctypes.c_uint * n)( *[self.trash.pop() for i in range(n)] )
				al.SourceUnqueueBuffers( self.id, n, ptr )
				assert al.GetError() == al.NO_ERROR
				al.DeleteBuffers( n, ptr )
				assert al.GetError() == al.NO_ERROR



############### Fluid Synth ############
class SynthChannel(object):
	def __init__(self, synth=None, index=0, sound_font=None, bank=0, patch=0 ):
		print('new synth channel', index, sound_font, bank, patch)
		self.synth = synth
		self.index = index
		self.sound_font = sound_font
		self.bank = bank
		self.patch = patch

		self.keys = [ 0.0 for i in range(128) ]				# driveable: 0.0-1.0
		self.previous_state = [ 0 for i in range(128) ]
		self.update_program()

	def update_program(self):
		self.synth.select_program( self.sound_font, self.index, self.bank, self.patch )

	def update(self):
		#if self.state == self.previous_state: return
		for i, value in enumerate(self.keys):
			v = int( value*127 )
			if v != self.previous_state[i]:
				self.previous_state[i] = v
				print('updating key state', i, v)
				if v: self.synth.note_on( self.index, i, v )
				else: self.synth.note_off( self.index, i )


	def next_patch( self ):
		self.patch += 1
		if self.patch > 127: self.patch = 127
		self.update_program()

	def previous_patch( self ):
		self.patch -= 1
		if self.patch < 0: self.patch = 0
		self.update_program()

	def cb_adjust_patch(self, adj):
		self.patch = int( adj.get_value() )
		self.update_program()

	def get_widget(self):
		root = gtk.HBox()

		frame = gtk.Frame('patch')
		root.pack_start( frame, expand=False )
		b = gtk.SpinButton(); frame.add( b )
		adj = b.get_adjustment()
		adj.configure( 
			value=self.patch, 
			lower=0, 
			upper=127, 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		adj.connect('value-changed', self.cb_adjust_patch)

		root.pack_start( gtk.Label() )

		keyboard = gtk.VBox(); keyboard.set_border_width(4)
		root.pack_start( keyboard, expand=False )
		row = gtk.HBox()
		keyboard.pack_start( row, expand=False )
		for i in range(20, 100):
			if i == 60:
				row = gtk.HBox()
				keyboard.pack_start( row, expand=False )
			b = ToggleButton('')
			b.connect( self, path='keys', index=i, cast=float )
			row.pack_start( b.widget, expand=False )

		#root.pack_start( gtk.Label() )

		root.pack_start( self.synth.speaker.get_widget(), expand=True )

		return root

	def toggle_key( self, button, index ):
		if button.get_active(): self.keys[ index ] = 1.0
		else: self.keys[ index ] = 0.0


class Synth( object ):
	Vibrato = 1
	Volume = 7
	Pan = 10
	Expression = 11
	Sustain = 64
	Reverb = 91
	Chorus = 93

	def __init__(self, gain=0.5, frequency=22050):
		self.gain = gain
		self.frequency = frequency
		self.settings = fluid.new_fluid_settings()
		fluid.settings_setnum( self.settings, 'synth.gain', gain )
		fluid.settings_setnum( self.settings, 'synth.sample-rate', frequency )
		self.sound_fonts = {}
		self.synth = fluid.new_fluid_synth( self.settings )

		self.samples = 1024
		self.buffer = (ctypes.c_int16 * self.samples)()
		self.buffer_ptr = ctypes.pointer( self.buffer )


	def get_stereo_samples( self ):
		fluid.synth_write_s16( 
			self.synth,
			self.samples,
			self.buffer_ptr, 0, 1,
			self.buffer_ptr, 1, 1,
		)
		return self.buffer

	def get_mono_samples( self ):
		fluid.synth_write_s16( 
			self.synth,
			self.samples,
			self.buffer_ptr, 0, 1,
			self.buffer_ptr, 0, 1,
		)
		return self.buffer


	def open_sound_font(self, url, update_midi_preset=0):
		id = fluid.synth_sfload( self.synth, url, update_midi_preset)
		assert id != -1
		self.sound_fonts[ os.path.split(url)[-1] ] = id
		return id

	def select_program( self, id, channel=0, bank=0, preset=0 ):
		fluid.synth_program_select( self.synth, channel, id, bank, preset )

	def note_on( self, chan, key, vel=127 ):
		if vel > 127: vel = 127
		elif vel < 0: vel = 0
		fluid.synth_noteon( self.synth, chan, key, vel )

	def note_off( self, chan, key ):
		fluid.synth_noteoff( self.synth, chan, key )

	def pitch_bend(self, chan, value):
		assert value >= -1.0 and value <= 1.0
		fluid.synth_pitch_bend( self.synth, chan, int(value*8192))

	def control_change( self, chan, ctrl, value ):
		"""Send control change value
		The controls that are recognized are dependent on the
		SoundFont.  Values are always 0 to 127.  Typical controls
		include:
		1 : vibrato
		7 : volume
		10 : pan (left to right)
		11 : expression (soft to loud)
		64 : sustain
		91 : reverb
		93 : chorus
		""" 
		fluid.synth_cc(self.synth, chan, ctrl, value)

	def change_program( self, chan, prog ):
		fluid.synth_program_change(self.synth, chan, prog )

	def select_bank( self, chan, bank ):
		fluid.synth_bank_select( self.synth, chan, bank )

	def select_sound_font( self, chan, name ):
		id = self.sound_fonts[ name ]
		fluid.synth_sfont_select( self.synth, chan, id )

	def reset(self):
		fluid.synth_program_reset( self.synth )

######################
class SynthMachine( Synth ):
	def setup(self):
		self.active = True
		url = os.path.join( SCRIPT_DIR, 'SoundFonts/Vintage Dreams Waves v2.sf2' )
		self.sound_font = self.open_sound_font( url )
		self.speaker = Speaker( frequency=self.frequency, streaming=True )
		self.channels = []
		for i in range(4):
			s = SynthChannel(synth=self, index=i, sound_font=self.sound_font, patch=i)
			self.channels.append( s )

	def update(self):
		if not self.active: return
		for chan in self.channels: chan.update()
		buff = self.get_mono_samples()
		speaker = self.speaker
		speaker.stream( buff )
		if not speaker.playing:
			speaker.play()





###########################################

class Audio(object):
	def __init__(self, analysis=False, streaming=True):
		self.active = True

		self.analysis = analysis
		self.streaming = streaming
		self.speakers = []
		self.buffersize = 1024
		self.input = None
		self.input_buffer = (ctypes.c_int16 * self.buffersize)()
		#self.input_buffer_ptr = ctypes.pointer( self.input_buffer )
		self.fftw_buffer_type = ( ctypes.c_double * 2 * self.buffersize )

		self.band_chunk = 32
		n = int( (self.buffersize / 2) / self.band_chunk )

		self.raw_bands = [ .0 for i in range(n) ]		# drivers fails if pointer is lost
		self.norm_bands = [ .0 for i in range(n) ]
		self.bands = [ .0 for i in range(n) ]

		self.beats_buffer_samples = 128
		self.beats_buffer = [ [0.0]*self.beats_buffer_samples for i in range(n) ]
		self.beats = [ False for i in range(n) ]
		self.beats_buttons = []
		self.beats_threshold = 2.0

		#self.max_raw = 0.1
		self.normalize = 1.0

		self.raw_adjustments = [ gtk.Adjustment( value=0, lower=0, upper=1 ) for i in range(n) ]
		self.norm_adjustments = [ gtk.Adjustment( value=0, lower=0, upper=1 ) for i in range(n) ]
		self.adjustments = [ gtk.Adjustment( value=0, lower=0, upper=1 ) for i in range(n) ]

		self.index = 0

	def get_analysis_widget(self):
		root = gtk.VBox()
		root.set_border_width(2)

		slider = Slider( self, name='normalize', value=self.normalize, min=0.5, max=5 )
		root.pack_start( slider.widget, expand=False )

		slider = Slider( self, name='beats_threshold', value=self.beats_threshold, min=0.5, max=5 )
		root.pack_start( slider.widget, expand=False )

		ex = gtk.Expander('raw bands')
		root.pack_start( ex, expand=False )
		box = gtk.VBox()
		sw = gtk.ScrolledWindow()
		sw.add_with_viewport( box )
		ex.add( sw )
		sw.set_size_request( 240,280 )

		for i, adjust in enumerate(self.raw_adjustments):
			row = gtk.HBox(); row.set_border_width(4)
			box.pack_start( row, expand=False )

			a = gtk.EventBox()
			title = '%s%s.band%s' %('raw',self.index,i)
			output = DeviceOutput( title, source=self.raw_bands, index=i )
			DND.make_source( a, output )

			a.add( gtk.Label(icons.DND) )
			row.pack_start( a, expand=False )

			scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
			scale.set_digits(3)
			row.pack_start( scale )

			a = gtk.EventBox()
			title = 'beat%s.button%s' %(self.index,i)
			b = gtk.ToggleButton('%s'%i)
			self.beats_buttons.append( b )
			output = DeviceOutput( title, source=self.beats, index=i )
			DND.make_source( b, output )
			a.add( b )
			row.pack_start( a, expand=False )


		ex = gtk.Expander('normalized bands')
		root.pack_start( ex, expand=False )
		box = gtk.VBox()
		sw = gtk.ScrolledWindow()
		sw.add_with_viewport( box )
		ex.add( sw )
		sw.set_size_request( 240,280 )

		for i, adjust in enumerate(self.norm_adjustments):
			row = gtk.HBox(); row.set_border_width(4)
			box.pack_start( row, expand=False )

			a = gtk.EventBox()
			title = '%s%s.band%s' %('norm',self.index,i)
			output = DeviceOutput( title, source=self.norm_bands, index=i )
			DND.make_source( a, output )

			a.add( gtk.Label(icons.DND) )
			row.pack_start( a, expand=False )

			scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
			scale.set_digits(3)
			row.pack_start( scale )

		return root

	def update(self):	# called from thread
		#for speaker in self.speakers: speaker.update()

		if self.analysis:
			complex = ctypes.c_double*2
			inbuff = self.fftw_buffer_type( *[complex(v,.0) for v in self.input_buffer] )
			outbuff = self.fftw_buffer_type()
			plan = fftw.plan_dft_1d( self.buffersize, inbuff, outbuff, fftw.FORWARD, fftw.ESTIMATE )
			fftw.execute( plan )

			real   = outbuff[ 0 ][0]
			imag = outbuff[ 0 ][1]
			self.power = math.sqrt( (real**2)+(imag**2) )

			raw = []
			bar = []
			for i in range( int(self.buffersize/2) ):
				real   = outbuff[ i+1 ][0]
				imag = outbuff[ i+1 ][1]
				power = math.sqrt( (real**2)+(imag**2) )
				bar.append( power )
				if len(bar) == self.band_chunk:
					raw.append( sum(bar) / float(self.band_chunk) )
					bar = []


			#h = max(raw)
			#if h > self.max_raw: self.max_raw = h; print('new max raw', h)
			#mult = 1.0 / self.max_raw
			#if self.max_raw > 1.0: self.max_raw *= 0.99	# TODO better normalizer
			mult = 1.0 / (self.normalize * 100000)		# values range from 200,000 to 2M

			for i,power in enumerate( raw ):
				power *= mult
				self.raw_bands[ i ] = power
				self.beats_buffer[ i ].insert( 0, power )
				self.beats_buffer[ i ].pop()
				avg = sum( self.beats_buffer[i] ) / float( self.beats_buffer_samples )
				#print('pow',power,'avg',avg)
				if power > avg * self.beats_threshold:
					self.beats[ i ] = True
				else:
					self.beats[ i ] = False

			high = max( self.raw_bands )
			mult = 1.0
			if high: mult /= high
			#self.norm_bands = [ power*mult for power in plot ]	# breaks drivers
			for i,power in enumerate(self.raw_bands):
				self.norm_bands[ i ] = power * mult



	def sync(self):	# called from main - (gtk not thread safe)
		if not self.active: return

		if self.beats_buttons:
			for i,power in enumerate( self.raw_bands ):
				self.raw_adjustments[ i ].set_value( power )
			for i,power in enumerate( self.norm_bands ):
				self.norm_adjustments[ i ].set_value( power )
			for i,beat in enumerate( self.beats ):
				self.beats_buttons[ i ].set_active( beat )


class Microphone( Audio ):
	def update(self):	# called from thread
		if not self.input: return
		ready = ctypes.pointer(ctypes.c_int())
		al.alcGetIntegerv( self.input, al.ALC_CAPTURE_SAMPLES, 1, ready )
		#print( ready.contents.value )
		if ready.contents.value >= self.buffersize:
			al.CaptureSamples(
				self.input,
				ctypes.pointer(self.input_buffer),
				self.buffersize
			)
			if self.streaming:
				for speaker in self.speakers:
					speaker.stream( self.input_buffer )
					if not speaker.playing:
						speaker.play()
		Audio.update( self )

	def start_capture( self, frequency=22050 ):
		print('[[starting mic capture]]')
		self.active = True
		self.frequency = frequency
		self.format=al.AL_FORMAT_MONO16
		self.input = al.CaptureOpenDevice( None, self.frequency, self.format, self.buffersize*2 )
		assert al.GetError() == al.AL_NO_ERROR
		al.CaptureStart( self.input )
		assert al.GetError() == al.AL_NO_ERROR
		if not self.speakers:
			s = Speaker( frequency=self.frequency, streaming=True )
			self.speakers.append( s )

	def stop_capture( self ):
		print('[[stop mic capture]]')
		al.CaptureStop( self.input )
		self.input = None
		self.active = False

	def close(self):
		self.active = False
		if self.input:
			print('[[closing mic]]')
			al.CaptureStop( self.input )
			al.CloseDevice( self.input )
			self.input = None


	def toggle_capture(self,button):
		if button.get_active(): self.start_capture()
		else: self.stop_capture()

	def get_widget(self):
		frame = gtk.Frame()
		root = gtk.HBox(); frame.add( root )

		b = gtk.ToggleButton( 'microphone' ); b.set_relief( gtk.RELIEF_NONE )
		b.set_tooltip_text( 'toggle microphone input' )
		b.connect('toggled', self.toggle_capture)
		root.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.FFT ); b.set_relief( gtk.RELIEF_NONE )
		b.set_tooltip_text( 'toggle spectral analysis' )
		b.set_active( self.analysis )
		b.connect('toggled', lambda b,s: setattr(s,'analysis',b.get_active()), self)
		root.pack_start( b, expand=False )

		b = gtk.ToggleButton( icons.SPEAKER ); b.set_relief( gtk.RELIEF_NONE )
		b.set_tooltip_text( 'toggle speaker output' )
		b.set_active( self.streaming )
		b.connect('toggled', lambda b,s: setattr(s,'streaming',b.get_active()), self)
		root.pack_start( b, expand=False )

		return frame



##############################




class Popup( ToolWindow ):
	def __init__(self):
		self.modal = gtk.Frame()
		ToolWindow.__init__(self, x=200, y=140, width=320, height=220, child=self.modal)
		win = self.window
		win.connect('destroy', self.hide )
		win.set_deletable(False)


	def hide(self,win):
		print('HIDE')
		win.hide()



	def refresh(self): self.object = None	# force reload



	def update(self, context):
		if context.active_object and context.active_object.name != self.object:
			print('UPDATING POPUP...')
			ob = context.active_object

			self.object = ob.name
			self.window.set_title( ob.name )
			self.window.remove( self.modal )
			#self.modal.destroy()

			self.modal = note = gtk.Notebook()
			self.window.add( self.modal )
			note.set_tab_pos( gtk.POS_LEFT )

			########## moved to left tools #########

			self.modal.show_all()





	def toggle_popup( self, button ):
		if button.get_active(): self.window.show_all()
		else: self.window.hide()


#####################################################

class Target(object):
	'''
	target to object,
	driven by axis or button
		if by axis:
			button is optional
			drop secondary axis controls extra local force axis
		if by button - force is constant

	on contact, if over thresh:
		"hold" - drop button
		"sound" - drop audio

	can boolean mod be used to inflict damage?
		on contact, if over thresh:
			create cutting object at place of impact,
			parent cutting object to target (or bone in armature)
			create boolean mod on target, set cutting

	'''
	def __init__(self,ob, weight=0.0, raw_power=1.0, normalized_power=0.0, x=1.0, y=1.0, z=1.0, bidirectional=False, bidirectional_power=0.1):
		self.name = ob.name				# could change target on the fly by scripting
		if ob.type=='ARMATURE': pass		# could target nearest bone as rule
		self.weight = weight
		self.raw_power = raw_power
		self.norm_power = normalized_power
		self.driver = None
		self.xmult = x
		self.ymult = y
		self.zmult = z
		self.bidirectional = bidirectional
		self.bidirectional_power = bidirectional_power
		self.target_start_matrix = ob.matrix_world.copy()
		self._modal = None
		self.dynamic = False

	def reset(self):
		if self.bidirectional:
			target = bpy.data.objects[ self.name ]
			target.matrix_world = self.target_start_matrix

	def get_widget(self):
		if self.dynamic:
			ex = gtk.Expander( '%s (dynamic)' %self.name )
			ex.set_tooltip_text( 'some properties are controlled from python and set dynamically' )
		else:
			ex = gtk.Expander( self.name )
			DND.make_destination( ex )
			ex.connect( 'drag-drop', self.cb_drop_target_driver )
		self.rebuild_widget( ex )
		return ex

	def rebuild_widget(self,ex):
		if self._modal: ex.remove( self._modal )
		self._modal = root = gtk.VBox()
		ex.add( root )

		if self.driver:
			widget = self.driver.get_widget( expander=False )
			root.pack_start( widget, expand=False )

		slider = Slider( self, name='weight', title=icons.WEIGHT, tooltip='weight', min=.0, max=200 )
		root.pack_start( slider.widget, expand=False )

		slider = Slider( self, name='raw_power', title=icons.RAW_POWER, tooltip='raw power', min=.0, max=2 )
		root.pack_start( slider.widget, expand=False )

		slider = Slider( self, name='norm_power', title=icons.NORMALIZED_POWER, tooltip='normalized power', min=.0, max=10 )
		root.pack_start( slider.widget, expand=False )

		for idx,tag in enumerate('xmult ymult zmult'.split()):
			slider = Slider( self, name=tag, title='xyz'[idx], min=-1, max=1 )
			root.pack_start( slider.widget, expand=False )

		b = CheckButton( 'enable bidirectional target' )
		b.connect( self, 'bidirectional' )
		root.pack_start( b.widget, expand=False )

		slider = Slider( self, name='bidirectional_power', title=icons.BIDIRECTIONAL, tooltip='power of bidirectional target', max=0.25 )
		root.pack_start( slider.widget, expand=False )


		ex.show_all()

	def cb_drop_target_driver(self, ex, context, x, y, time):
		ex.set_expanded(True)
		output = DND.source_object
		self.driver = driver = output.bind( 'TARGET', target=self, path='weight', mode='=' )
		#widget = driver.get_widget( expander=False )
		#ex.add( widget )
		#widget.show_all()
		self.rebuild_widget(ex)


	def update(self, projectiles):
		'''
		un-normalized delta reaches target and sticks, but can use too much force if far away.
		normalized delta is constant in force, but always overshoots target.
		'''
		target = bpy.data.objects[ self.name ]
		vec = target.matrix_world.to_translation()
		W = self.weight

		for p in projectiles:
			delta = vec - p.matrix_world.to_translation()
			x1,y1,z1 = delta
			x2,y2,z2 = delta.normalized()

			x = (x1*self.raw_power) + (x2*self.norm_power)
			y = (y1*self.raw_power) + (y2*self.norm_power)
			z = (z1*self.raw_power) + (z2*self.norm_power)


			wrap = ENGINE.get_wrapper(p)
			wrap.body.AddForce( 
				x * self.xmult * W, 
				y * self.ymult * W, 
				z * self.zmult * W, 
			)

			if self.bidirectional:
				m = target.matrix_world.copy()
				m[0][3] -= x1 * self.bidirectional_power
				m[1][3] -= y1 * self.bidirectional_power
				m[2][3] -= z1 * self.bidirectional_power
				target.matrix_world = m


class Bone(object):
	'''
	contains at least two physics bodies: shaft and tail
	head is optional
	'''

	def save_transform(self):
		for bo in (self.head, self.shaft, self.tail):
			if not bo: continue
			wrap = ENGINE.get_wrapper( bo )
			wrap.save_transform( bo )

		x,y,z = self.shaft.matrix_world.to_translation()
		self.start_location = (x,y,z)
		self.rest_height = z				# used by biped solver

	def set_transform(self, matrix, tail):
		loc,rot,scl = matrix.decompose()
		if self.head: ENGINE.get_wrapper( self.head ).set_transform( loc, rot )
		mid = tail - loc; mid *= 0.5	# midpoint
		ENGINE.get_wrapper( self.shaft ).set_transform( loc+mid, rot )
		ENGINE.get_wrapper( self.tail ).set_transform( tail, rot )

	def save_pose( self, name, matrix, tail ):
		self.poses[ name ] = {'matrix':matrix, 'tail':tail, 'weight':0.0}
	def adjust_pose( self, name, weight=0.0 ):
		if not weight: return
		pose = self.poses[ name ]
		self.set_transform( pose['matrix'], pose['tail'] )


	## this failed because even with no ERP/CFM the joint still has an effect ##
	## ODE lacks a joint strength option, this was probably a bad idea anyways ##
	#def save_pose( self, name, objects ):
	#	if not self.parent: return
	#	joints = []
	#	self.poses[ name ] = {'joints':joints, 'weight':0.0, 'objects':objects}
	#	parent = ENGINE.get_wrapper( self.parent.tail )
	#	for child in self.get_wrapper_objects():
	#		joint = child.new_joint( parent, name='POSE:%s'%name, type='fixed' )
	#		joints.append( joint )
	#	if objects: print('pose objects', objects)
	#	self.adjust_pose( name, weight=0.0 )
	#def adjust_pose( self, name, weight=0.0 ):
	#	if name not in self.poses: return
	#	p = self.poses[ name ]
	#	if weight != p['weight']:
	#		p['weight'] = weight
	#		for joint in p['joints']:
	#			joint.set_param( 'CFM', 0.0) #1.0-weight )
	#			joint.set_param( 'ERP', weight )



	def get_location(self):
		return self.shaft.matrix_world.to_translation()

	def hide(self):
		for ob in (self.head, self.shaft, self.tail):
			if ob: ob.hide = True

	def show(self):
		for ob in (self.head, self.shaft, self.tail):
			if ob: ob.hide = False

	def get_objects(self):
		r = []
		for ob in (self.head, self.shaft, self.tail):
			if ob: r.append( ob )
		return r

	def get_wrapper_objects(self):
		r = []
		for ob in (self.head, self.shaft, self.tail):
			if ob: r.append( ENGINE.get_wrapper(ob) )
		return r

	def add_force( self, x,y,z ):
		for ob in self.get_objects():
			w = ENGINE.get_wrapper( ob )
			w.body.AddForce( x,y,z )
	def add_local_force( self, x,y,z ):
		for ob in self.get_objects():
			w = ENGINE.get_wrapper( ob )
			w.body.AddRelForce( x,y,z )
	def add_local_torque( self, x,y,z ):
		for ob in self.get_objects():
			w = ENGINE.get_wrapper( ob )
			w.body.AddRelTorque( x,y,z )

	def get_velocity_local( self ):
		w = ENGINE.get_wrapper( self.shaft )
		return w.get_linear_vel()
	def get_angular_velocity_local( self ):	# TODO what space is this?
		w = ENGINE.get_wrapper( self.shaft )
		return w.get_angular_vel()


	def __init__(self, arm, name, stretch=False, tension_CFM=0.5, tension_ERP=0.5, object_data=None, collision=True, external_children=[], disable_collision_with_other_bones=False, hybrid=False, gravity=True, info=None):
		self.armature = arm
		self.name = name
		self.stretch = stretch
		self.tension_CFM = tension_CFM
		self.tension_ERP = tension_ERP
		self.collision = collision
		self.external_children = tuple( external_children )	# not dynamic
		self.hybrid = hybrid
		self.gravity = gravity
		self.info = info
		self.poses = {}		# pose-name : joints
		self.head = None
		self.shaft = None
		self.tail = None
		self.breakable_joints = []
		self.fixed_parent_joint = None
		self.parent_joint = None
		self.parent = None

		ebone = arm.data.bones[ name ]
		pbone = arm.pose.bones[ name ]
		if pbone.parent:
			self.parent_name = pbone.parent.name
		else:
			self.parent_name = None


		if not ebone.parent or not ebone.use_connect:
			self.head = bpy.data.objects.new(name='HEAD.'+name,object_data=None)
			Pyppet.context.scene.objects.link( self.head )
			self.head.matrix_world = pbone.matrix.copy()
			#head.empty_draw_type = 'SPHERE'
			self.head.empty_draw_size = ebone.head_radius * 2.0


		################ body #################
		self.shaft = bpy.data.objects.new( name=name, object_data=object_data )
		self.shaft.hide_select = True
		self.shaft.rotation_mode = 'QUATERNION'
		if object_data:
			self.shaft.draw_type = 'WIRE'
			self.bullet_collision = self.shaft.modifiers.new(name='RIG', type='COLLISION' )
		else:
			self.shaft.empty_draw_type = 'CUBE'
			self.bullet_collision = None

		Pyppet.context.scene.objects.link(self.shaft)
		m = pbone.matrix.copy()
		delta = pbone.tail - pbone.head
		delta *= 0.5
		length = delta.length
		x,y,z = pbone.head + delta	# the midpoint
		m[0][3] = x	# blender2.61 style
		m[1][3] = y
		m[2][3] = z

		self.start_location = (x,y,z)
		self.rest_height = z				# used by biped solver

		avg = (ebone.head_radius + ebone.tail_radius) / 2.0
		self.shaft.matrix_world = m
		self.shaft.scale = (avg, length*0.6, avg)	# set scale in local space
		Pyppet.context.scene.update()			# syncs .matrix_world with local-space set scale

		self.shaft.ode_use_body = True
		self.shaft_wrapper = ENGINE.get_wrapper( self.shaft )

		if self.collision:
			self.shaft.ode_use_collision = True	# needs matrix_world to be in sync before this is set
			if disable_collision_with_other_bones:
				self.shaft_wrapper.no_collision_groups.append( self.armature.name )

		################ pole-target (up-vector) ##############
		self.pole = bpy.data.objects.new( name='POLE.'+name, object_data=None )
		#self.pole.empty_draw_type = 'CUBE'
		self.pole.hide_select = True
		Pyppet.context.scene.objects.link(self.pole)
		self.pole.location.z = -10.0
		self.pole.parent = self.shaft


		################# tail ###############
		self.tail = bpy.data.objects.new(name='TAIL.'+name,object_data=object_data)
		self.tail.show_x_ray = True
		Pyppet.context.scene.objects.link( self.tail )
		m = pbone.matrix.copy()
		x,y,z = pbone.tail
		m[0][3] = x	# blender2.61 style
		m[1][3] = y
		m[2][3] = z
		self.tail.matrix_world = m
		self.tail.scale = [ ebone.tail_radius * 1.75 ] * 3
		Pyppet.context.scene.update()			# syncs .matrix_world with local-space set scale

		if object_data:
			self.tail.draw_type = 'WIRE'
			self.bullet_collision2 = self.tail.modifiers.new(name='RIG', type='COLLISION' )

		else:
			self.tail.empty_draw_type = 'SPHERE'
			#self.tail.empty_draw_size = ebone.tail_radius * 1.75



		#### make ODE bodies ####
		if self.head: self.head.ode_use_body = True
		if self.tail: self.tail.ode_use_body = True



		## bind tail to body ##
		parent = ENGINE.get_wrapper( self.shaft )
		child = ENGINE.get_wrapper( self.tail )
		joint = child.new_joint(
			parent, 
			name='FIXED2TAIL.'+parent.name,
			type='fixed'
		)
		#self.primary_joints[ ebone.name ] = {'body':joint}


		if self.head:	# must come before STRETCH_TO
			cns = pbone.constraints.new('COPY_LOCATION')
			cns.target = self.head

			## bind body to head ##
			parent = ENGINE.get_wrapper( self.head )
			child = ENGINE.get_wrapper( self.shaft )
			joint = child.new_joint(
				parent, 
				name='ROOT.'+parent.name,
				type='ball'
			)
			#self.primary_joints[ ebone.name ]['head'] = joint


		self.ik = None
		if stretch:
			self.stretch_to_constraint = cns = pbone.constraints.new('STRETCH_TO')
			cns.target = self.tail
			#cns.bulge = 1.5

		elif not self.info['ik-target']:
			if self.hybrid and self.info['ik-chain']:
				if  arm.pose.ik_solver == 'ITASC':	# itasc segfaults!
					self.ik = cns = pbone.constraints.new('IK')
					cns.target = self.tail
					cns.chain_count = 1
					#cns.iterations = 32
					#cns.pole_target = self.pole
					#cns.pole_angle = math.radians( -90 )

					cns.use_location = True
					cns.weight = 0.1
					cns.use_rotation = True
					cns.orient_weight = 0.25

					if self.info['ik-chain'] and self.info['ik-chain-info']:
						level = self.info['ik-chain-level']
						count = self.info['ik-chain-info']['ik-length'] - level
						if count > 0: cns.chain_count = count


				else:
					self.stretch_to_constraint = cns = pbone.constraints.new('STRETCH_TO')
					cns.target = self.tail
					cns.keep_axis = 'PLANE_Z'
					#if self.info['ik-chain']: cns.influence = 0.5	# makes flipping worse!

					self.limit_scale_constraint = cns = pbone.constraints.new('LIMIT_SCALE')
					cns.use_min_x = cns.use_min_y = cns.use_min_z = True
					cns.use_max_x = cns.use_max_y = cns.use_max_z = True
					cns.min_x = cns.min_y = cns.min_z = 1.0
					cns.max_x = cns.max_y = cns.max_z = 1.0

					############ not helping ###############
					#cns = pbone.constraints.new('TRACK_TO')
					#cns.target = self.tail
					#cns.influence = 0.5
					#cns = pbone.constraints.new('LOCKED_TRACK')
					#cns.target = self.pole
					#cns.track_axis = 'TRACK_Z'
					#cns.lock_axis = 'LOCK_Y'

			else:
				if self.info['ik-constraint']:
					self.ik = cns = self.info['ik-constraint']
				else:
					self.ik = cns = pbone.constraints.new('IK')
					cns.target = self.tail
					cns.chain_count = 1
					cns.iterations = 32

				if not cns.pole_target:
					cns.pole_target = self.pole
					cns.pole_angle = math.radians( -90 )

				if self.info['ik-chain'] and self.info['ik-chain-info']:
					cns.weight = 0.5
					level = self.info['ik-chain-level']
					count = self.info['ik-chain-info']['ik-length'] - level
					if count > 0: cns.chain_count = count

	
		for ob in self.get_objects():
			ob.ode_use_gravity = self.gravity

		if self.armature.parent:
			for ob in self.get_objects():
				if not ob.parent:
					ob.parent = self.armature.parent


	def set_parent( self, parent ):
		self.parent = parent	# Bone
		parent = ENGINE.get_wrapper( parent.tail )

		types = []
		if '{' in self.name and '}' in self.name:
			a = self.name.split('{')[-1].split('}')[0]
			for t in a.strip().split():		# allow multiple joint types
				types.append( t )

		if not types: types.append( 'universal' )

		jtype = types[0]
		print('set-parent joint type:', jtype)

		child = ENGINE.get_wrapper( self.shaft )
		self.parent_joint = child.new_joint( parent, name='body2parent.'+parent.name, type=jtype )

		self.fixed_parent_joint = joint = child.new_joint( parent, name='MAGIC-FIXED.'+parent.name, type='fixed' )
		joint.set_param( 'CFM', self.tension_CFM )
		joint.set_param( 'ERP', self.tension_ERP )

		self.parent_joint.slaves.append( self.fixed_parent_joint )
		self.breakable_joints.append( self.parent_joint )

		if self.head:		# if head, bind head to tail of parent - (helps breakable ragdoll)  #
			child = ENGINE.get_wrapper( self.head )
			joint = child.new_joint( parent, name='head2parent.'+parent.name, type=jtype )
			self.parent_joint.slaves.append( joint )

		## extra joints ##
		if len(types) > 1:
			child = ENGINE.get_wrapper( self.shaft )
			for i, jtype in enumerate(types[1:]):
				joint = child.new_joint(
					parent,
					name='ex.%s.%s'%(parent.name,i),
					type=jtype 
				)
				self.parent_joint.slaves.append( joint )



	def set_weakness( self, break_thresh, damage_thresh ):
		if break_thresh:
			for joint in self.breakable_joints:
				joint.breaking_threshold = break_thresh
				joint.damage_threshold = damage_thresh


class AbstractArmature(object):
	def reset(self):
		names = list(self.targets.keys())
		names.sort()		# TODO proper restore in order: parent->children
		for bname in names:
			for target in self.targets[bname]:
				target.reset()		# to reset bidirectional targets


	def get_widget_label(self): return gtk.Label( self.ICON )	# label may need to be a drop target
	def get_bones_upstream(self, child, lst):
		lst.append( child )
		if child.parent: self.get_bones_upstream( child.parent, lst )

	def __init__(self,name):
		self.name = name
		self.rig = {}
		self.active_pose_bone = None
		self.targets = {}		# bone name : [ Targets ]
		self.created = False
		self._targets_widget = None
		self._active_bone_widget = None
		self.broken = []
		self.poses = {}
		self.tension_CFM = 0.05
		self.tension_ERP = 0.85
		self._show_rig = True

	def any_ancestors_broken(self, child):
		broken = []
		self._get_ancestors_broken(child, broken)
		return len(broken)

	def _get_ancestors_broken(self, child, broken):		# recursive
		if child in self.broken: broken.append( child )
		if child.parent: self._get_ancestors_broken( child.parent, broken )

	def adjust_rig_tension(self, adj, mode):
		assert mode in ('CFM', 'ERP')
		if mode == 'CFM': self.tension_CFM = adj.get_value()
		else: self.tension_ERP = adj.get_value()

		for B in self.rig.values():
			if B.fixed_parent_joint:
				B.fixed_parent_joint.set_param(mode, adj.get_value())

	def get_create_widget(self):
		root = gtk.VBox()
		row = gtk.HBox(); root.pack_start( row, expand=False )

		stretch  = gtk.CheckButton('stretch-to constraints')
		breakable = gtk.CheckButton('breakable joints')

		hybrid = gtk.CheckButton('hybrid-IK')
		hybrid_weight = Slider( name='hybrid-IK weight', force_title_above=True, value=100, min=0.01, max=200 )
		hybrid_bd = gtk.CheckButton('hybrid-IK bidirectional targets')
		hybrid_bd.set_tooltip_text('IK targets are also affected by the physics rig')
		hybrid_bd_power = Slider( name='hybrid-IK bidirectional power', value=0.1, max=0.5 )

		gravity = gtk.CheckButton('use gravity')
		gravity.set_active(True)
		allow_unconnected = gtk.CheckButton('use unconnected bones')
		collision = gtk.CheckButton('use collision')
		collision.set_active(True)
		collides_with_self = gtk.CheckButton('use self collision')

		break_thresh = Slider( name='joint breaking threshold', value=200, min=0.01, max=420 )
		damage_thresh = Slider( name='joint damage threshold', value=150, min=0.01, max=420 )

		func = lambda button, s, b, bt, dt, hy, hyw, hybd, hybdp, g, a, c, cws: self.create(
			stretch = s.get_active(),
			breakable = b.get_active(),
			break_thresh = bt.get_value(),
			damage_thresh = dt.get_value(),
			hybrid_IK = hy.get_active(),
			hybrid_IK_weight = hyw.get_value(),
			hybrid_IK_bidirectional = hybd.get_active(),
			hybrid_IK_bidirectional_power = hybdp.get_value(),
			gravity = g.get_active(),
			allow_unconnected_bones = a.get_active(),
			collision = c.get_active(),
			collides_with_self = cws.get_active(),
		)

		b = gtk.Button('create %s' %self.__class__.__name__)
		b.set_border_width(5)
		row.pack_start( b, expand=True )
		b.connect(
			'clicked',
			func,
			stretch,
			breakable, 
			break_thresh.adjustment,
			damage_thresh.adjustment,
			hybrid,
			hybrid_weight.adjustment,
			hybrid_bd,
			hybrid_bd_power.adjustment,
			gravity,
			allow_unconnected,
			collision,
			collides_with_self,
		)

		split = gtk.HBox()
		root.pack_start( split )
		page1 = gtk.VBox()
		page2 = gtk.VBox()
		split.pack_start( page1 )
		split.pack_start( page2 )

		page1.pack_start( stretch, expand=False )
		page1.pack_start( breakable, expand=False )
		page2.pack_start( break_thresh.widget, expand=False )
		page2.pack_start( damage_thresh.widget, expand=False )

		page1.pack_start( hybrid, expand=False )
		page2.pack_start( hybrid_weight.widget, expand=False )
		page1.pack_start( hybrid_bd, expand=False )
		page2.pack_start( hybrid_bd_power.widget, expand=False )

		page1.pack_start( gravity, expand=False )
		page1.pack_start( allow_unconnected, expand=False )
		page1.pack_start( collision, expand=False )
		page1.pack_start( collides_with_self, expand=False )
		return root


	def use_bone_in_rig( self, bone ): return False	# overload

	def build_bones(self, bone, data=None, broken_chain=False):
		info = self.bone_info[bone.name]
		connected = info['connected']
		ik = info['ik-chain']
		deform = info['deform']
		if not connected and bone.parent: broken_chain = True
		if not bone.parent or self.use_bone_in_rig(bone) or connected or self.allow_unconnected_bones:
			if (not ik or self.hybrid_IK) and deform:
				if self.collision and (not broken_chain or not bone.children):
					collision = True
				else:
					collision = False


				self.rig[ bone.name ] = Bone(
					self.armature,
					bone.name, 
					stretch=self.stretchable,
					tension_CFM = self.tension_CFM,
					tension_ERP = self.tension_ERP,
					object_data = data,
					collision = collision,
					disable_collision_with_other_bones = not self.collides_with_self,
					external_children = info['external-children'],
					hybrid = self.hybrid_IK,
					gravity = self.gravity,
					info = info,
				)
				for child in bone.children:	# recursive
					self.build_bones( child, data, broken_chain )

	def create( self, stretch=False, breakable=False, break_thresh=None, damage_thresh=None, hybrid_IK=False, hybrid_IK_weight=100,  hybrid_IK_bidirectional=False, hybrid_IK_bidirectional_power=0.1, gravity=True, allow_unconnected_bones=False, collision=True, collides_with_self=False):

		self.created = True

		self.hybrid_IK = hybrid_IK
		self.hybrid_IK_weight = hybrid_IK_weight
		self.hybrid_IK_bidirectional = hybrid_IK_bidirectional
		self.hybrid_IK_bidirectional_power = hybrid_IK_bidirectional_power
		self.hybrid_IK_targets = []
		self.gravity = gravity
		self.stretchable = stretch
		self.breakable = breakable
		self.allow_unconnected_bones = allow_unconnected_bones
		self.collision = collision
		self.collides_with_self = collides_with_self

		self.armature = arm = bpy.data.objects[ self.name ]
		self.spawn_matrix = arm.matrix_world.copy()
		arm.matrix_world = mathutils.Matrix()				# zero transform

		self.itasc = arm.pose.ik_solver == 'ITASC'

		arm.pyppet_model = self.__class__.__name__		# pyRNA
		Pyppet.AddEntity( self )
		Pyppet.refresh_selected = True


		#self.primary_joints = {}
		#self.breakable_joints = []
		self.initial_break_thresh = break_thresh
		self.initial_damage_thresh = damage_thresh

		## collect bone info first ##
		self.bone_info = {}
		IK_info = []
		for bone in arm.data.bones:
			self.bone_info[ bone.name ] = info = {}
			if bone.parent: info['parent'] = bone.parent.name
			else: info['parent'] = None
			info['connected'] = bone.use_connect
			info['deform'] = bone.use_deform
			pbone = arm.pose.bones[ bone.name ]
			info['ik-chain'] = pbone.is_in_ik_chain
			info['ik-constraint'] = None
			info['ik-target'] = None
			info['ik-chain-info'] = None
			info['location-target'] = None
			info['external-children'] = []
			info['joints'] = []
			info['constraints'] = []
			for cns in pbone.constraints:
				info['constraints'].append( cns )
				if cns.type == 'IK':
					info['ik-constraint'] = cns
					info['ik-target'] = cns.target
					info['ik-length'] = cns.chain_count
				elif cns.type == 'COPY_LOCATION':
					info['location-target'] = cns.target

			if info['ik-target']:
				IK_info.append( info )

		for infoIK in IK_info:
			level = 0
			parent = infoIK['parent']
			while parent:
				level += 1
				info = self.bone_info[ parent ]
				if info['ik-chain']:
					#if info['ik-chain-info']: print('TODO warn?')
					info['ik-chain-info'] = infoIK
					info['ik-chain-level'] = level
					parent = info['parent']
				else:
					break

		## collect POSE INFO ##
		context = Pyppet.context
		context.scene.frame_set( 1 )
		self.poses_bias = {}	# constraint-target: matrix
		for info in self.bone_info.values():
			for cns in info['constraints']:
				if cns.target and cns.target not in self.poses_bias:
					self.poses_bias[ cns.target ] = cns.target.matrix_world.copy()


		self.poses = {}
		self.poses_state = {}
		for marker in context.scene.timeline_markers:
			#context.scene.frame_current = marker.frame
			#Pyppet.context.scene.update()
			context.scene.frame_set( marker.frame )

			self.poses[ marker.name ] = pose = {}
			self.poses_state[ marker.name ] = 0.0

			for bone in arm.pose.bones:
				pinfo = {'matrix':bone.matrix.copy(), 'tail':bone.tail.copy()}
				pose[ bone.name ] = pinfo

				pinfo['constraints'] = constraints = {}
				info = self.bone_info[ bone.name ]
				if info['ik-target']:
					bo = info['ik-target']
					#bo = bpy.data.objects[ bo.name ]
					constraints[ bo ] = bo.matrix_world.copy()
				if info['location-target']:
					bo = info['location-target']
					constraints[ bo ] = bo.matrix_world.copy()


		context.scene.frame_set( 1 )


		## collect external objects that are children of the bones ##
		for ob in bpy.data.objects:
			if ob.parent_type=='BONE' and ob.parent == arm:
				info = self.bone_info[ ob.parent_bone ]
				info['external-children'].append( ob )

				## bones not allowed to have RigidBody Constraint, defer to external children.
				for cns in ob.constraints:
					if cns.type == 'RIGID_BODY_JOINT':
						type = None
						if '{' in cns.name and '}' in cns.name:
							type = cns.name.split('{')[-1].split('}')[0].strip()
						elif cns.pivot_type == 'BALL': type = 'ball'
						elif cns.pivot_type == 'HINGE': type = 'hinge'
						elif cns.pivot_type == 'CONE_TWIST': pass
						elif cns.pivot_type == 'GENERIC_6_DOF': pass

						if type and (cns.target or cns.child):
							info['joints'].append(
								{'type':type, 'child': cns.target or cns.child}
							)


		if breakable:
			print('making breakable',arm)
			# arm needs to be in edit mode to get to .edit_bones
			bpy.context.scene.objects.active = arm
			bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
			bpy.ops.object.mode_set(mode='EDIT', toggle=False)
			for bone in arm.data.edit_bones:
				if self.is_bone_breakable( bone ):
					bone.use_connect = False
			bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

		if stretch: 	#or self.hybrid_IK:
			for bone in arm.data.bones:
				bone.use_inherit_rotation = False
				bone.use_inherit_scale = False


		## build rig from roots ##
		#cube = create_cube()
		for bone in arm.data.bones:
			if not bone.parent: self.build_bones( bone )
		#Pyppet.context.scene.objects.unlink(cube)
		#cube.user_clear()


		## bind body to tail of parent ##
		for name in self.rig:
			child = self.rig[name]
			if child.parent_name and child.parent_name in self.rig:
				parent = self.rig[ child.parent_name ]
				child.set_parent( parent )

		## update weakness ##
		if break_thresh:
			for b in self.rig.values():
				b.set_weakness( break_thresh, damage_thresh )

		## check for external children and make them sub-geoms ##
		for b in self.rig.values():
			for ob in b.external_children:
				if ob.game.use_collision_bounds:
					ob.ode_use_collision = True
					child = ENGINE.get_wrapper( ob )
					b.shaft_wrapper.append_subgeom( child )

		## create hybrid-IK targets and joints for external objects ##
		for b in self.rig.values():
			info = self.bone_info[ b.name ]

			if self.hybrid_IK and (info['ik-target'] or info['location-target']):
				if info['ik-target']: ob = info['ik-target']
				else: ob = info['location-target']

				target = self.create_target(
					b.name, 
					ob,
					weight = self.hybrid_IK_weight,
					normalized_power = 0.75,
					bidirectional = self.hybrid_IK_bidirectional,
					bidirectional_power = self.hybrid_IK_bidirectional_power,
				)
				self.hybrid_IK_targets.append( target )

			for d in info['joints']:
				ob = d['child']

				if ob.parent_type=='BONE' and ob.parent.type == 'ARMATURE':
					if ob.parent.pyppet_model:
						e = Pyppet.GetEntity( ob.parent )
						c = e.rig[ ob.parent_bone ]
						ob = c.shaft

					else:
						print('WARNING: you must initialize the sub-armature first, as a ragdoll, etc.')


				if not ob.ode_use_body: ob.ode_use_body = True
				wrap = ENGINE.get_wrapper( ob )
				wrap.new_joint(
					name = '%s2%s' %(ob.name,b.name),
					parent=b.shaft_wrapper, 
					type=d['type']
				)

		self.setup()		# call subclass setup

		## setup poses ##
		for pose_name in self.poses:
			pose = self.poses[ pose_name ]
			for name in pose:
				if name not in self.rig: continue
				b = self.rig[ name ]
				matrix = pose[name]['matrix']
				tail = pose[name]['tail']
				#b.set_transform( matrix, tail )
				#b.save_pose( pose_name, pose[name]['constraints'] )
				b.save_pose( pose_name, matrix, tail )

		## restore spawn point ##
		self.armature_root = root = bpy.data.objects.new(
			name='ARM-ROOT.%s'%self.name,
			object_data=None
		)
		Pyppet.context.scene.objects.link( root )
		self.armature.parent = root
		root.empty_draw_type = 'CONE'
		for b in self.rig.values():
			for ob in b.get_objects():
				ob.parent = root
		root.matrix_world = self.spawn_matrix
		Pyppet.context.scene.update()			# syncs .matrix_world with local-space set scale

		self.save_transform()


	def adjust_rig_pose( self, adjust, name ):
		self.poses_state[ name ] = adjust.get_value()

	def update_poses(self):
		touched = []

		for name in self.poses_state:
			value = self.poses_state[ name ]
			if value <= 0.0: continue

			pose = self.poses[ name ]
			for bone_name in pose:
				if bone_name in self.rig: self.rig[ bone_name ].adjust_pose( name, value )
				p = pose[ bone_name ]
				for bo in p['constraints']:
					mat = p['constraints'][ bo ]
					if bo not in touched:
						touched.append( bo )
						bo.matrix_world = self.poses_bias[ bo ].copy()
					bo.matrix_world = bo.matrix_world.lerp( mat, value )


	def setup(self): pass	# override
	def is_bone_breakable( self, bone ): return True	# override

	def update(self, context ):

		for bname in self.targets:
			for target in self.targets[bname]:
				#target.driver.update()	# DriverManager.update takes care of this
				B = self.rig[ bname ]
				if B not in self.broken:
					target.update( self.rig[ bname ].get_objects() )

		for B in self.rig.values():
			#if not B.shaft_wrapper.touching: continue

			for joint in B.breakable_joints:
				if joint.broken: continue
				if joint.breaking_threshold is None: continue
				stress = joint.get_stress()
				if stress > joint.breaking_threshold:
					joint.break_joint()
					print('-----breaking joint stress', stress)
					if B not in self.broken:
						self.broken.append( B )
						if B.parent and not hasattr(B,'broken_target'):
							B.broken_target = Target( B.parent.shaft, weight=100, normalized_power=0.5 )

				elif stress > joint.damage_threshold:
					joint.damage(0.5)
					print('-----damage joint stress', stress)

	def create_target( self, name, ob, **kw ):
		target = Target( ob, **kw )
		target.dynamic = True
		if name not in self.targets: self.targets[ name ] = []
		self.targets[ name ].append( target )
		return target

	def cb_drop_target(self, wid, context, x, y, time):
		if not self.active_pose_bone: return

		wrap = DND.source_object
		target = Target( wrap )
		if self.active_pose_bone not in self.targets: self.targets[ self.active_pose_bone ] = []
		self.targets[ self.active_pose_bone ].append( target )

		widget = target.get_widget()
		self._modal.pack_start( widget, expand=False )
		widget.show_all()


	def get_targets_widget(self):
		self._targets_widget = gtk.Frame('selected bone')
		self._modal = gtk.Label('targets')
		self._targets_widget.add( self._modal )
		DND.make_destination( self._targets_widget )
		self._targets_widget.connect( 'drag-drop', self.cb_drop_target )
		return self._targets_widget

	def get_active_bone_widget(self):
		container = gtk.EventBox()
		child = gtk.VBox()
		self._active_bone_widget = (container,child)
		container.add( child )
		return container


	def toggle_rig_visible( self, button ):
		self._show_rig = button.get_active()
		if self._show_rig:
			for B in self.rig.values(): B.show()
		else:
			for B in self.rig.values(): B.hide()

	def update_ui( self, context ):
		if not context.active_pose_bone and self.active_pose_bone:
			self.active_pose_bone = None
			if self._show_rig:
				for B in self.rig.values(): B.show()

		elif context.active_pose_bone and context.active_pose_bone.name != self.active_pose_bone:
			bone = context.active_pose_bone
			if bone.name in self.rig:
				self.active_pose_bone = bone.name	# get bone name, not bone instance

				for B in self.rig.values(): B.hide()
				self.rig[ bone.name ].show()

				self.update_targets_widget( bone )
				self.update_active_bone_widget( bone )

	def heal_broken_joints(self,b):
		for B in self.rig.values():
			if B in self.broken: self.broken.remove( B )
			for joint in B.breakable_joints:
				if joint.broken: joint.restore()

	def get_widget(self):
		root = gtk.VBox()

		row = gtk.HBox()
		root.pack_start( row, expand=False )
		b = gtk.Button('heal joints')
		b.connect('clicked', self.heal_broken_joints)
		row.pack_start( b, expand=False )
		b = gtk.Button('reset transform')
		b.connect('clicked', self.save_transform)
		row.pack_start( b, expand=False )

		frame = gtk.Frame('rig parent/child tension')
		root.pack_start( frame, expand=False )
		bx = gtk.VBox(); frame.add( bx )
		s = Slider( title='ERP', value=self.tension_ERP, tooltip='joint error reduction' )
		s.connect( self.adjust_rig_tension, 'ERP' )
		bx.pack_start( s.widget, expand=False )

		s = Slider( title='CFM', value=self.tension_CFM, tooltip='joint constant force mixing (stretch)' )
		s.connect( self.adjust_rig_tension, 'CFM' )
		bx.pack_start( s.widget, expand=False )

		if self.poses:
			ex = DetachableExpander( 'Poses' )
			root.pack_start( ex.widget )
			box = gtk.VBox(); ex.add( box )
			for name in self.poses:
				s = Slider( title=name, value=0.0, tooltip='set pose weight for all bones' )
				s.connect( self.adjust_rig_pose, name )
				box.pack_start( s.widget, expand=False )

		return root


	def save_transform(self, button=None):
		for B in self.rig.values(): B.save_transform()


	def update_targets_widget(self, bone):
		if not self._targets_widget: return
		self._targets_widget.set_label( bone.name )
		self._targets_widget.remove( self._modal )
		self._modal = root = gtk.VBox()
		self._targets_widget.add( root )

		root.set_border_width(6)
		if bone.name in self.targets:
			for target in self.targets[ bone.name ]:
				root.pack_start( target.get_widget(), expand=True )
		root.show_all()


	def update_active_bone_widget(self, bone):
		B = self.rig[ bone.name ]
		bo = B.tail	# tail is a blender object
		container,root = self._active_bone_widget
		container.remove( root )
		root = gtk.VBox()
		container.add( root )
		self._active_bone_widget = (container,root)

		root.pack_start( gtk.Label(bone.name), expand=False )

		slider = Slider(
			bo, name='ode_constant_global_force', title='lift',
			tooltip='global force on Z', 
			target_index=2,
			min=-100, max=500,
		)
		root.pack_start( slider.widget )

		ex = gtk.Expander( 'Local Force' )
		root.pack_start( ex, expand=False )
		bx = gtk.VBox(); ex.add( bx )
		for i in range(3):
			slider = Slider(
				bo, 'ode_constant_local_force', title='xyz'[i], 
				target_index=i,
				min=-500, max=500,
			)
			bx.pack_start( slider.widget, expand=False )

		ex = gtk.Expander( 'Local Torque' )
		root.pack_start( ex, expand=False )
		bx = gtk.VBox(); ex.add( bx )
		for i in range(3):
			slider = Slider(
				bo, 'ode_constant_local_torque', title='xyz'[i], 
				target_index=i,
				min=-500, max=500,
			)
			bx.pack_start( slider.widget, expand=False )

		root.show_all()

class Rope( AbstractArmature ):
	ICON = icons.ROPE
	def GetRopeWidget(self):
		return self.get_widget()



class Ragdoll( AbstractArmature ):
	ICON = icons.RAGDOLL
	def GetRagdollWidget(self):
		if not self.created:
			return self.get_create_widget()
		else:
			return self.get_widget()




class Biped( AbstractArmature ):
	ICON = icons.BIPED

	def is_bone_breakable( self, bone):
		name = bone.name.lower()
		if 'head' in name or 'neck' in name: return False
		else: return True

	def GetBipedWidget(self):
		if not self.created: return self.get_create_widget()

		root = gtk.VBox()

		ex = Expander('Settings')
		root.pack_start(ex.widget, expand=False)
		widget = self.get_widget()
		ex.pack_start( widget, expand=False )

		b = CheckButton( 'flip knee', tooltip='reverse knee direction' )
		b.connect( self, 'flip_knee' )
		ex.append( b.widget )

		slider = Slider( self, name='primary_heading', title='heading', min=-180, max=180, tooltip='direction character faces' )
		ex.pack_start( slider.widget, expand=False )

		slider = Slider( self, name='stance', max=10, tooltip='distance legs will spead apart' )
		ex.pack_start( slider.widget, expand=False )

		slider = Slider(
			self, name='standing_height_threshold', title='standing thresh', max=1.0, 
			tooltip='adjust how much height will be used to determine if the character is standing'
		)
		ex.pack_start( slider.widget, expand=False )

		ex = Expander( 'Standing Solver' )
		root.pack_start( ex.widget, expand=False )
		box = gtk.VBox(); ex.add( box )

		slider = Slider( self, name='when_standing_head_lift', title='head lift', max=500 )
		box.pack_start( slider.widget, expand=False )

		slider = Slider(
			self, name='toe_height_standing_threshold', title='head lift - threshold', max=1.0,
			tooltip='if the "toe" of the foot is below this height then head lift becomes active',
		)
		box.pack_start( slider.widget, expand=False )


		s = Slider( self, name='leg_flex', title='leg flex', min=-100, max=400, tooltip='standing muscle tension' )
		box.pack_start( s.widget, expand=False )

		for tag in 'when_standing_foot_step_far_lift when_standing_foot_step_near_pull'.split():
			slider = Slider( self, name=tag, title=tag[14:], min=0, max=200 )
			box.pack_start( slider.widget, expand=False )

		slider = Slider( self, name='when_standing_foot_step_near_far_thresh', title='foot-step near/far', min=0.01, max=5 )
		box.pack_start( slider.widget, expand=False )

		slider = Slider( self, name='toe_downward_pull', title='toes down', min=0.0, max=200 )
		box.pack_start( slider.widget, expand=False )

		################## stepping #################
		ex = Expander( 'Stepping Solver' )
		root.pack_start( ex.widget, expand=False )
		box = gtk.VBox(); ex.add( box )

		row = gtk.HBox(); box.pack_start( row, expand=False )
		row.pack_start( gtk.Label('auto-step:') )
		b = CheckButton('left')
		b.connect( self, 'auto_left_step' )
		row.pack_start( b.widget, expand=False )
		b = CheckButton('right')
		b.connect( self, 'auto_right_step' )
		row.pack_start( b.widget, expand=False )

		row = gtk.HBox(); box.pack_start( row, expand=False )
		row.pack_start( gtk.Label('force-step:') )
		b = CheckButton('left')
		b.connect( self, 'force_left_step' )
		row.pack_start( b.widget, expand=False )
		b = CheckButton('right')
		b.connect( self, 'force_right_step' )
		row.pack_start( b.widget, expand=False )

		s = Slider( self, name='when_standing_foot_target_goal_weight', title='goal weight', min=0.0, max=200 )
		box.pack_start( s.widget, expand=False )

		s = Slider( self, name='when_stepping_leg_flex', title='leg flex', min=-10, max=400, tooltip='leg contraction on step' )
		box.pack_start( s.widget, expand=False )

		s = Slider(
			title='step power %s'%icons.RAW_POWER, 
			max=2.0, callback=self.adjust_foot_targets_raw_power,
			value = self.foot_solver_targets[0].raw_power,
		)
		box.pack_start( s.widget, expand=False )
		s = Slider( 
			title='step power %s'%icons.NORMALIZED_POWER, max=5.0, 
			callback=self.adjust_foot_targets_norm_power,
			value = self.foot_solver_targets[0].norm_power,			
		)
		box.pack_start( s.widget, expand=False )

		################ turn motion ##############

		ex = Expander( 'Dancing Solver' )
		root.pack_start( ex.widget, expand=False )

		s = Slider( self, name='on_motion_back_step', title='back step', max=2.0 )
		ex.append( s.widget )

		s = Slider( self, name='on_motion_back_step_rate_factor', title='back step rate factor', max=1.0 )
		ex.append( s.widget )

		s = Slider( self, name='on_motion_forward_step', title='forward step', max=2.0 )
		ex.append( s.widget )

		s = Slider( self, name='on_motion_fast_forward_thresh', title='fast forward threshold', max=10.0 )
		ex.append( s.widget )

		s = Slider( self, name='on_motion_fast_forward_step', title='fast forward step', max=2.0 )
		ex.append( s.widget )

		s = Slider( self, name='on_motion_fast_forward_step_rate_factor', title='fast forward step rate factor', max=1.0 )
		ex.append( s.widget )


		################## falling #####################
		ex = Expander( 'Falling Solver' )
		root.pack_start( ex.widget, expand=False )
		box = gtk.VBox(); ex.add( box )
		for tag in 'when_falling_and_hands_down_lift_head_by_tilt_factor when_falling_pull_hands_down_by_tilt_factor when_falling_head_curl when_falling_hand_target_goal_weight'.split():
			if tag=='when_falling_hand_target_goal_weight':
				slider = Slider( self, name=tag, min=0, max=200 )
			else:
				slider = Slider( self, name=tag, min=0, max=50 )
			box.pack_start( slider.widget, expand=False )

		return root

	def adjust_foot_targets_raw_power(self, adj):
		for target in self.foot_solver_targets: target.raw_power = adj.get_value()
	def adjust_foot_targets_norm_power(self, adj):
		for target in self.foot_solver_targets: target.norm_power = adj.get_value()


	def reset(self):
		x,y,z = self.pelvis.start_location
		self.pelvis.shadow.location = (x,y,z)

		rad = -math.radians(self.primary_heading+90)
		cx = math.sin( -rad ) * self.stance
		cy = math.cos( -rad ) * self.stance
		v = self.left_foot.shadow_parent.location
		v.x = x+cx
		v.y = y+cy
		v.z = .0
		self.left_foot_loc = v

		rad = math.radians(self.primary_heading+90)
		cx = math.sin( -rad ) * self.stance
		cy = math.cos( -rad ) * self.stance
		v = self.right_foot.shadow_parent.location
		v.x = x+cx
		v.y = y+cy
		v.z = .0
		self.right_foot_loc = v


	def setup(self):
		print('making biped...')

		self.dead = False
		self.death_twitches = 200

		self.auto_left_step = False
		self.auto_right_step = False
		self.force_left_step = False
		self.force_right_step = False

		self.solver_objects = []
		self.smooth_motion_rate = 0.0
		self.prev_heading = .0
		self.primary_heading = 0.0
		self.stance = 0.1

		self.head = None
		self.chest = None
		self.pelvis = None
		self.left_foot = self.right_foot = None
		self.left_toes = []
		self.right_toes = []

		self.left_shoulder = self.right_shoulder = None

		self.left_hand = self.right_hand = None
		self.foot_solver_targets = []
		self.hand_solver_targets = []
		self.left_foot_loc = None
		self.right_foot_loc = None

		############################## solver basic options ##############################
		self.flip_knee = False
		self.leg_flex = 50
		self.stance = 1.0
		self.toe_height_standing_threshold = 0.1
		self.toe_downward_pull = 50

		self.on_motion_back_step = 0.5
		self.on_motion_back_step_rate_factor = 0.25
		self.on_motion_forward_step = 0.2
		self.on_motion_fast_forward_thresh = 2.0
		self.on_motion_fast_forward_step = 0.5
		self.on_motion_fast_forward_step_rate_factor = 0.25

		self.standing_height_threshold = 0.75
		self.when_standing_foot_target_goal_weight = 100.0
		self.when_standing_head_lift = 100.0			# magic - only when foot touches ground lift head
		self.when_standing_foot_step_far_lift = 80		# if foot is far from target lift it up
		self.when_standing_foot_step_near_pull = 10	# if foot is near from target pull it down
		self.when_standing_foot_step_near_far_thresh = 0.25

		self.when_stepping_leg_flex = 50

		self.when_falling_and_hands_down_lift_head_by_tilt_factor = 4.0
		self.when_falling_pull_hands_down_by_tilt_factor = 10.0
		self.when_falling_head_curl = 10.0
		self.when_falling_hand_target_goal_weight = 100.0
		################################################################################

		for name in self.rig:
			_name = name.lower()
			if 'pelvis' in _name or 'hip' in _name or 'root' in _name:
				self.pelvis = self.rig[ name ]

			elif 'head' in _name or 'skull' in _name:
				self.head = self.rig[ name ]

			elif 'foot' in _name:
				B = self.rig[ name ]
				x,y,z = B.get_location()
				if x > 0: self.left_foot = B
				elif x < 0: self.right_foot = B

			elif 'toe' in _name:
				B = self.rig[ name ]
				if B.collision:
					x,y,z = B.get_location()
					if x > 0: self.left_toes.append( B )
					elif x < 0: self.right_toes.append( B )

			elif 'hand' in _name:
				B = self.rig[ name ]
				x,y,z = B.get_location()
				if x > 0: self.left_hand = B
				elif x < 0: self.right_hand = B
				else: print( 'WARN: hand at zero X ->', name)

			elif 'shoulder' in _name:
				B = self.rig[ name ]
				x,y,z = B.get_location()
				if x > 0: self.left_shoulder = B
				elif x < 0: self.right_shoulder = B


			elif 'chest' in _name:
				self.chest = self.rig[ name ]

			else: continue

			self.solver_objects.append( self.rig[name] )

		assert self.pelvis
		assert self.head
		assert self.chest
		assert self.left_shoulder
		assert self.right_shoulder

		for B in self.rig.values(): B.biped_solver = {}

		self.spine = []
		self.get_bones_upstream( self.head, self.spine )

		ob = bpy.data.objects.new(name='PELVIS-SHADOW',object_data=None)
		self.pelvis.shadow = ob
		Pyppet.context.scene.objects.link( ob )
		ob.empty_draw_type = 'SINGLE_ARROW'
		ob.empty_draw_size = 5.0

		cns = ob.constraints.new('TRACK_TO')		# points on the Y
		cns.target = self.head.shaft
		cns.track_axis = 'TRACK_Z'
		cns.up_axis = 'UP_Y'
		cns.use_target_z = True

		## foot and hand solvers ##
		self.helper_setup_foot( self.left_foot, toes=self.left_toes )
		self.helper_setup_foot( self.right_foot, toes=self.right_toes, flip=True )

		if self.left_hand: self.helper_setup_hand( self.left_hand, self.left_foot )
		if self.right_hand: self.helper_setup_hand( self.right_hand, self.right_foot )

		self.head_center_target = self.create_target( self.head.name, self.pelvis.shaft, weight=100, z=0.0 )



	def helper_setup_hand( self, hand, foot ):
		ob = bpy.data.objects.new(
			name='HAND-TARGET.%s'%hand.name,
			object_data=None
		)
		hand.biped_solver['swing-target'] = ob
		ob.empty_draw_type = 'CUBE'
		ob.empty_draw_size = 0.1
		Pyppet.context.scene.objects.link( ob )
		ob.parent = foot.biped_solver['target-parent']
		target = self.create_target( hand.name, ob, weight=30, z=0.0 )
		self.hand_solver_targets.append( target )


	def helper_setup_foot( self, foot, toes=[], flip=False ):
		for joint in foot.breakable_joints:
			joint.breaking_threshold = None

		ob = bpy.data.objects.new(
			name='RING.%s'%foot.name,
			object_data=None
		)
		#ob.empty_draw_type = 'CONE'
		foot.shadow_parent = ob
		foot.biped_solver[ 'target-parent' ] = ob
		Pyppet.context.scene.objects.link( ob )
		cns = ob.constraints.new('TRACK_TO')		# points on the Y

		cns.target = self.pelvis.shadow

		if flip: cns.track_axis = 'TRACK_NEGATIVE_Z'
		else: cns.track_axis = 'TRACK_Z'
		cns.up_axis = 'UP_Y'
		cns.use_target_z = True


		ob = bpy.data.objects.new(
			name='FOOT-TARGET.%s'%foot.name,
			object_data=None
		)
		foot.shadow = ob
		foot.biped_solver[ 'target' ] = ob

		ob.empty_draw_type = 'SINGLE_ARROW'
		ob.empty_draw_size = 2.5

		Pyppet.context.scene.objects.link( ob )
		ob.parent = foot.shadow_parent

		target = self.create_target(
			foot.name, ob, weight=30, 
			raw_power=float(len(toes)), 
			normalized_power=0.0, 
			z=.0 
		)
		self.foot_solver_targets.append( target )	# standing or falling modifies all foot targets
		foot.biped_solver[ 'TARGET' ] = target

		if foot.parent:	# pull leg to chest when fallen
			target = self.create_target( foot.parent.name, self.chest.shaft, weight=0, z=.0 )
			foot.parent.biped_solver[ 'TARGET:chest' ] = target

		cns = ob.constraints.new('TRACK_TO')
		cns.target = self.pelvis.shaft
		cns.track_axis = 'TRACK_Z'
		cns.up_axis = 'UP_Y'
		cns.use_target_z = True

		foot.toes = []
		for toe in toes:
			for joint in toe.breakable_joints:
				joint.breaking_threshold = None

			foot.toes.append( toe )
			target = self.create_target( toe.name, ob, weight=0, z=.0 )
			toe.biped_solver['TARGET'] = target
			self.foot_solver_targets.append( target )

		print('FOOT TOES', foot.toes)


	def update(self, context):
		AbstractArmature.update(self,context)

		step_left = step_right = False
		if not self.left_foot_loc:
			self.left_foot_loc = self.left_foot.shadow_parent.location
			step_left = True
		if not self.right_foot_loc:
			self.right_foot_loc = self.right_foot.shadow_parent.location
			step_right = True

		x,y,z = self.chest.get_velocity_local()

		sideways = None
		sideways_rate = abs( x )
		if x < -2: sideways = 'RIGHT'
		elif x > 2: sideways = 'LEFT'

		moving = None
		#motion_rate = abs( y )
		delta = y - self.smooth_motion_rate
		self.smooth_motion_rate += delta*0.1
		motion_rate = abs( self.smooth_motion_rate )
		#print('mrate', motion_rate)
		if self.smooth_motion_rate < -0.2: moving = 'FORWARD'
		elif self.smooth_motion_rate > 0.2: moving = 'BACKWARD'

		loc,rot,scl = self.pelvis.shadow.matrix_world.decompose()
		euler = rot.to_euler()
		tilt = sum( [abs(math.degrees(euler.x)), abs(math.degrees(euler.y))] ) / 2.0		# 0-45


		x,y,z = self.pelvis.get_location()
		current_pelvis_height = z
		falling = current_pelvis_height < self.pelvis.rest_height * (1.0-self.standing_height_threshold)
		standing = not falling

		head_lift = self.when_standing_head_lift
		head_is_attached = not self.any_ancestors_broken(self.head)
		if not head_is_attached:
			self.dead = True
			if self.death_twitches:
				if random() > 0.95:
					self.death_twitches -= 1
					if random() > 0.5:
						self.pelvis.add_local_torque( random()*500, 0, 0 )
					else:
						self.pelvis.add_local_torque( 0, random()*500, 0 )
			return

		hx,hy,hz = self.head.get_location()
		#x = (x+hx)/2.0
		#y = (y+hy)/2.0
		dx = hx - x
		dy = hy - y
		if moving == 'FORWARD':
			x += dx * 1.1
			y += dy * 1.1
		elif moving == 'BACKWARD':
			x += dx * 0.1
			y += dy * 0.1

		ob = self.pelvis.shadow
		if random() > 0.99: ob.location = (x,y,-0.5)
		Xcenter = ob.location.x
		Ycenter = ob.location.y

		loc,rot,scale = ob.matrix_world.decompose()
		euler = rot.to_euler()

		heading = math.degrees( euler.z )
		spin = self.prev_heading - heading
		self.prev_heading = heading
		turning = None
		turning_rate =  abs(spin) #/ 360.0
		if abs(spin) < 300:	# ignore euler flip
			if spin < -1.0: turning = 'LEFT'
			elif spin > 1.0: turning = 'RIGHT'


		if turning == 'LEFT':
			if moving == 'BACKWARD':
				self.left_foot.shadow.location.x = -(motion_rate * self.on_motion_back_step_rate_factor)
				self.right_foot.shadow.location.x = -self.on_motion_back_step

			elif moving == 'FORWARD':
				self.left_foot.shadow.location.x = 0.1
				self.right_foot.shadow.location.x = self.on_motion_forward_step
				if motion_rate > self.on_motion_fast_forward_thresh:
					if random() > 0.8:
						step_right = True
						self.left_foot.shadow.location.x = -(motion_rate * 0.25)
					self.right_foot.shadow.location.x = motion_rate * self.on_motion_fast_forward_step_rate_factor
					self.right_foot.shadow.location.x += self.on_motion_fast_forward_step


			if not step_right and random() > 0.99:
				if random() > 0.1: step_left = True
				else: step_right = True

		elif turning == 'RIGHT':
			if moving == 'BACKWARD':
				self.right_foot.shadow.location.x = -(motion_rate * self.on_motion_back_step_rate_factor)
				self.left_foot.shadow.location.x = -self.on_motion_back_step

			elif moving == 'FORWARD':
				self.right_foot.shadow.location.x = 0.1
				self.left_foot.shadow.location.x = self.on_motion_forward_step
				if motion_rate > self.on_motion_fast_forward_thresh:
					if random() > 0.8:
						step_left = True
						self.right_foot.shadow.location.x = -(motion_rate * 0.25)
					self.left_foot.shadow.location.x = motion_rate * self.on_motion_fast_forward_step_rate_factor
					self.left_foot.shadow.location.x += self.on_motion_fast_forward_step

			if not step_left and random() > 0.99:
				if random() > 0.1: step_right = True
				else: step_left = True


		hand_swing_targets = []
		if self.left_hand:
			hand = self.left_hand
			v = hand.biped_solver['swing-target'].location
			hand_swing_targets.append( v )
			v.x = -( self.left_foot.biped_solver['target'].location.x )

			## reach hand to last broken joint ##
			if self.broken and not self.any_ancestors_broken(hand):
				broken = list( self.broken )
				broken.reverse()
				for broke in broken:
					if not self.any_ancestors_broken(broke):
						broke.broken_target.update( hand.get_objects() )
						break


		if self.right_hand:
			hand = self.right_hand
			v = hand.biped_solver['swing-target'].location
			hand_swing_targets.append( v )
			v.x = -( self.right_foot.biped_solver['target'].location.x )

			## reach hand to last broken joint ##
			if self.broken and not self.any_ancestors_broken(hand):
				broken = list( self.broken )
				broken.reverse()
				for broke in broken:
					if not self.any_ancestors_broken(broke):
						broke.broken_target.update( hand.get_objects() )
						break



		if 0:	# looks bad?
			v = self.left_foot.biped_solver['target'].location
			if v.x < 0:		# if foot moving backward only pull on heel/foot
				self.left_toe.biped_solver['TARGET'].weight = 0.0
			elif v.x > 0:	# if foot moving forward only pull on toe
				self.left_foot.biped_solver['TARGET'].weight = 0.0

			v = self.right_foot.biped_solver['target'].location
			if v.x < 0:		# if foot moving backward only pull on heel/foot
				self.right_toe.biped_solver['TARGET'].weight = 0.0
			elif v.x > 0:	# if foot moving forward only pull on toe
				self.right_foot.biped_solver['TARGET'].weight = 0.0


		if moving == 'BACKWARD':	# hands forward if moving backwards
			for v in hand_swing_targets: v.x += 0.1




		force_right_step = False
		if (step_left and self.auto_left_step) or self.force_left_step:
			print('step LEFT')
			force_right_step = True
			rad = euler.z - math.radians(self.primary_heading+90)
			cx = math.sin( -rad ) * self.stance
			cy = math.cos( -rad ) * self.stance
			v = self.left_foot.shadow_parent.location
			v.x = Xcenter + cx
			v.y = Ycenter + cy
			v.z = .0
			self.left_foot_loc = v


			foot = self.left_foot

			foot.biped_solver[ 'TARGET' ].zmult = 0.0
			for toe in foot.toes:
				toe.biped_solver[ 'TARGET' ].zmult = 0.0

			if not self.any_ancestors_broken(foot):

				## MAGIC: lift head ##
				v1 = foot.get_location().copy()
				if v1.z < self.toe_height_standing_threshold or v1.z < foot.rest_height:
					if standing and head_is_attached:
						self.apply_head_lift( head_lift*0.5, left=True )

				v2 = self.left_foot_loc.copy()
				v1.z = .0; v2.z = .0
				dist = (v1 - v2).length
				if dist > self.when_standing_foot_step_near_far_thresh:
					foot.add_force( 0, 0, self.when_standing_foot_step_far_lift)
				elif dist < self.when_standing_foot_step_near_far_thresh:
					foot.add_force( 0, 0, -self.when_standing_foot_step_near_pull)

				if self.flip_knee:
					foot.parent.add_local_torque( self.when_stepping_leg_flex, 0, 0 )
					foot.parent.parent.add_local_torque( -self.when_stepping_leg_flex, 0, 0 )
				else:
					foot.parent.add_local_torque( -self.when_stepping_leg_flex, 0, 0 )
					foot.parent.parent.add_local_torque( self.when_stepping_leg_flex, 0, 0 )

		else:
			foot = self.left_foot
			if not self.any_ancestors_broken(foot):

				## MAGIC: lift head ##
				v1 = foot.get_location()
				if v1.z < self.toe_height_standing_threshold or v1.z < foot.rest_height:
					if standing and head_is_attached:
						self.apply_head_lift( head_lift*0.5, left=True )

				if self.flip_knee:
					foot.add_local_torque( self.leg_flex*0.25, 0, 0 )
					foot.parent.add_local_torque( -self.leg_flex, 0, 0 )
					foot.parent.parent.add_local_torque( self.leg_flex*0.5, 0, 0 )
				else:
					foot.add_local_torque( -self.leg_flex*0.25, 0, 0 )
					foot.parent.add_local_torque( self.leg_flex, 0, 0 )
					foot.parent.parent.add_local_torque( -self.leg_flex*0.5, 0, 0 )

				foot.add_force( 0,0, -self.toe_downward_pull )
				foot.biped_solver[ 'TARGET' ].zmult = 1.0
				for toe in foot.toes:
					toe.biped_solver[ 'TARGET' ].zmult = 1.0
					toe.add_force( 0,0, -self.toe_downward_pull )

		if (step_right and self.auto_right_step) or self.force_right_step or force_right_step:
			print('step RIGHT')
			rad = euler.z + math.radians(self.primary_heading+90)
			cx = math.sin( -rad ) * self.stance
			cy = math.cos( -rad ) * self.stance
			v = self.right_foot.shadow_parent.location
			v.x = Xcenter + cx
			v.y = Ycenter + cy
			v.z = .0
			self.right_foot_loc = v

			foot = self.right_foot

			foot.biped_solver[ 'TARGET' ].zmult = 0.0
			for toe in foot.toes:
				toe.biped_solver[ 'TARGET' ].zmult = 0.0

			if not self.any_ancestors_broken(foot):

				## MAGIC: lift head ##
				v1 = foot.get_location().copy()
				if v1.z < self.toe_height_standing_threshold or v1.z < foot.rest_height:
					if standing and head_is_attached:
						self.apply_head_lift( head_lift*0.5, right=True )

				v2 = self.right_foot_loc.copy()
				v1.z = .0; v2.z = .0
				dist = (v1 - v2).length
				if dist > self.when_standing_foot_step_near_far_thresh:
					foot.add_force( 0, 0, self.when_standing_foot_step_far_lift)
				elif dist < self.when_standing_foot_step_near_far_thresh:
					foot.add_force( 0, 0, -self.when_standing_foot_step_near_pull)


				if self.flip_knee:
					foot.parent.add_local_torque( self.when_stepping_leg_flex, 0, 0 )
					foot.parent.parent.add_local_torque( -self.when_stepping_leg_flex, 0, 0 )
				else:
					foot.parent.add_local_torque( -self.when_stepping_leg_flex, 0, 0 )
					foot.parent.parent.add_local_torque( self.when_stepping_leg_flex, 0, 0 )

		else:
			foot = self.right_foot
			if not self.any_ancestors_broken(foot):

				## MAGIC: lift head ##
				v1 = foot.get_location()
				if v1.z < self.toe_height_standing_threshold or v1.z < foot.rest_height:
					if standing and head_is_attached:
						self.apply_head_lift( head_lift*0.5, right=True )



				if self.flip_knee:
					foot.add_local_torque( self.leg_flex*0.25, 0, 0 )
					foot.parent.add_local_torque( -self.leg_flex, 0, 0 )
					foot.parent.parent.add_local_torque( self.leg_flex*0.5, 0, 0 )
				else:
					foot.add_local_torque( -self.leg_flex*0.25, 0, 0 )
					foot.parent.add_local_torque( self.leg_flex, 0, 0 )
					foot.parent.parent.add_local_torque( -self.leg_flex*0.5, 0, 0 )

				foot.add_force( 0,0, -self.toe_downward_pull )
				foot.biped_solver[ 'TARGET' ].zmult = 1.0
				for toe in foot.toes:
					toe.biped_solver[ 'TARGET' ].zmult = 1.0
					toe.add_force( 0,0,-self.toe_downward_pull )

		#if not step_left or step_right: print('no STEP')


		#################### falling ####################
		if falling:

			if current_pelvis_height < 0.2:
				for foot in (self.left_foot, self.right_foot):
					if foot not in self.broken: foot.add_local_torque( -30, 0, 0 )

					if foot.parent:
						target = foot.parent.biped_solver[ 'TARGET:chest' ]
						if target.weight < 50: target.weight += 1.0

			else:
				for foot in (self.left_foot, self.right_foot):
					if foot.parent:
						target = foot.parent.biped_solver[ 'TARGET:chest' ]
						target.weight *= 0.9


			for target in self.foot_solver_targets:	# reduce foot step force
				target.weight *= 0.99

			#for target in self.hand_solver_targets:	# increase hand plant force
			#	if target.weight < self.when_falling_hand_target_goal_weight:
			#		target.weight += 1

			for hand in (self.left_hand, self.right_hand):
				if not hand or hand in self.broken: continue

				self.head.add_local_torque( -self.when_falling_head_curl, 0, 0 )
				u = self.when_falling_pull_hands_down_by_tilt_factor * tilt
				hand.add_force( 0,0, -u )

				x,y,z = hand.get_location()
				if z < 0.1:
					self.head.add_force( 
						0,
						0, 
						tilt * self.when_falling_and_hands_down_lift_head_by_tilt_factor
					)
					hand.add_local_force( 0, -10, 0 )
				else:
					hand.add_local_force( 0, 3, 0 )

		elif standing:

			for foot in (self.left_foot, self.right_foot):
				if foot.parent:
					target = foot.parent.biped_solver[ 'TARGET:chest' ]
					target.weight *= 0.9

				## MAGIC: if the toes are touching the ground, lift up the head ##
				toes = []
				for toe in foot.toes:
					x,y,z = toe.get_location()
					if z < self.toe_height_standing_threshold or z < toe.rest_height:
						if head_is_attached and not self.any_ancestors_broken(toe):
							toes.append( toe )

				if not toes: continue
				force = head_lift / float(len(toes))
				self.apply_head_lift( force*0.5 )


			for target in self.foot_solver_targets:
				if target.weight < self.when_standing_foot_target_goal_weight:
					target.weight += 1

			#for target in self.hand_solver_targets:	# reduce hand plant force
			#	target.weight *= 0.9


	def apply_head_lift( self, force, left=False, right=False ):
		head = self.head
		x,y,z = head.get_location()
		if z > head.rest_height: return
		delta = head.rest_height - z
		if delta < 1.0: force *= delta + 0.25	## Extra Magic ##

		head.add_force( 0,0, force*0.75 )
		if left: self.left_shoulder.add_force( 0,0, force*0.5 )
		if right: self.right_shoulder.add_force( 0,0, force*0.5 )

		if head.parent:
			head.parent.add_force( 0,0, force*0.75 )
			if head.parent.parent:
				head.parent.parent.add_force( 0,0, force*0.5 )
				if head.parent.parent.parent:
					head.parent.parent.parent.add_force( 0,0, force*0.25 )
					if head.parent.parent.parent.parent:
						head.parent.parent.parent.parent.add_force( 0,0, force*0.125 )

		#force /= float( len(self.spine) )
		#force *= 0.25
		#[ b.add_force( 0,0, force ) for b in self.spine ]

##########################################################
bpy.types.Object.pyppet_model = bpy.props.StringProperty( name='pyppet model type', default='' )

#class PyppetAPI( BlenderHackLinux ):
class PyppetAPI( server_api.BlenderServer ):
	'''
	Public API
	'''
	MODELS = ['Ragdoll', 'Biped', 'Rope']

	def GetRagdoll( self, arm ):
		if type(arm) is str: name = arm
		else: name = arm.name
		if name not in self.ragdolls: self.ragdolls[ name ] = Ragdoll( name )
		return self.ragdolls[ name ]

	def GetBiped( self, arm ):
		if type(arm) is str: name = arm
		else: name = arm.name
		if name not in self.bipeds: self.bipeds[ name ] = Biped( name )
		return self.bipeds[ name ]

	def GetRope( self, arm ):
		if type(arm) is str: name = arm
		else: name = arm.name
		if name not in self.ropes: self.ropes[ name ] = Rope( name )
		return self.ropes[ name ]

	def AddEntity( self, model ):
		self.entities[ model.name ] = model
	def GetEntity( self, arm ):
		return self.entities[ arm.name ]

	def reset_models(self):
		self.entities = {}
		self.ragdolls = {}
		self.bipeds = {}
		self.ropes = {}
	######################################
	def reset( self ):
		self.selected = None
		self.edit_mode = None
		self.on_active_object_changed_callbacks = []
		self.reset_models()

	def register(self, func):
		self.on_active_object_changed_callbacks.append( func )

	refresh_selected = False
	def update_callbacks(self):
		if self.context.active_object:
			if (self.context.mode != self.edit_mode) or (self.context.active_object.name != self.selected) or self.refresh_selected:
				self.edit_mode = self.context.mode
				self.selected = self.context.active_object.name
				ob = bpy.data.objects[ self.selected ]

				for func in self.on_active_object_changed_callbacks:
					func( ob )

				self.refresh_selected = False


	########### recording/baking ###########
	def set_recording_shape_keys_cache( self, ob, blocks ):
		self._rec_shape_keys_cache[ ob ] = blocks


	def clear_recording(self, button=None):
		self._rec_saved_objects = {}
		self._rec_saved_shape_keys = {}

	def commit_recording(self, button=None):
		for ob in self._rec_current_objects:
			buff = self._rec_current_objects[ ob ]
			self._rec_saved_objects[ ob ] = buff
			print('commit animation', ob, len(buff))

		for ob in self._rec_current_shape_keys:
			buff = self._rec_current_shape_keys[ ob ]
			self._rec_saved_shape_keys[ ob ] = buff
			print('commit shape animation', ob, buff)

		self._rec_current_objects = {}
		self._rec_current_shape_keys = {}

	def start_record(self, selected_only=False, record_physics=True, record_objects=True, record_shapes=True):
		self.recording = True
		self._rec_start_frame = self.context.scene.frame_current
		self._rec_current_objects = {}
		self._rec_blender_objects = {}
		self._rec_current_shape_keys = {}

		objects = []
		if selected_only:
			for ob in self.context.selected_objects:
				if ob not in self._rec_saved_objects:
					objects.append( ob )
		else:
			for ob in self.context.scene.objects:
				if ob not in self._rec_saved_objects:
					objects.append( ob )

		for ob in objects:
			if ob.name in ENGINE.objects:
				w = ENGINE.objects[ ob.name ]
				if record_physics and (w.body or w.geom):
					print('new record buffer on ODE-object:', ob.name)
					ob.animation_data_clear()
					self._rec_objects[ ob.name ] = buff = []
					w.reset_recording( buff )
					self._rec_current_objects[ ob ] = buff
				elif record_objects:
					print('setup record buffer on BLENDER-object:', ob.name)
					ob.animation_data_clear()
					self._rec_blender_objects[ ob ] = buff = []
					self._rec_current_objects[ ob ] = buff

			elif record_objects:		# if user hasn't toggled physics once
				print('setup record buffer on BLENDER-object:', ob.name)
				ob.animation_data_clear()
				self._rec_blender_objects[ ob ] = buff = []
				self._rec_current_objects[ ob ] = buff

			if record_shapes and ob in self._rec_shape_keys_cache:
				buff = { block:[] for block in self._rec_shape_keys_cache[ob] }
				print('setup rec buff on for shape-anim', ob, buff)
				self._rec_current_shape_keys[ ob ] = buff

		self._rec_start_time = time.time()
		if self.play_wave_on_record and self.wave_speaker:
			self.start_wave()

	def end_record(self):
		self.recording = False
		if self.play_wave_on_record and self.wave_speaker: self.stop_wave()
		for name in ENGINE.objects:
			w = ENGINE.objects[ name ]
			w.transform = None


	def update_physics(self, now, drop_frame=False):
		ENGINE.sync( self.context, now, self.recording, drop_frame=drop_frame )
		models = self.entities.values()
		for mod in models:
			mod.update( self.context )

	def sort_objects_for_preview(self):
		'''
		this must be called once before update_preview,
		because setting matrix_world fails if children are set before their parents.
		'''
		rank = {}
		for ob in self._rec_saved_objects:
			nth = len( get_ancestors(ob) )
			if nth not in rank: rank[nth] = []
			rank[ nth ].append( ob )
		order = list(rank.keys())
		order.sort()
		print('ORDER', rank)
		self._rec_saved_objects_order = []
		for nth in order:
			self._rec_saved_objects_order += rank[ nth ]


	def update_preview(self, now):
		done = []

		for ob in self._rec_saved_shape_keys:
			M = self._rec_saved_shape_keys[ ob ]
			## TODO offset cache, since all blocks will have the same number of frames
			for block in M:
				buff = M[ block ]
				for i,F in enumerate(buff):
					if F[0] < now: continue
					frame_time, value = F
					block.value = value
					if i==len(buff)-1: done.append(True)
					else: done.append(False)
					break


		for ob in self._rec_saved_objects_order:
			buff = self._rec_saved_objects[ ob ]
			for i,F in enumerate(buff):
				if F[0] < now: continue
				frame_time, pos, rot = F
				set_transform( 
					ob, pos, rot, 
					set_body = self.recording
				)
				if i==len(buff)-1: done.append(True)
				else: done.append(False)
				break

			self.context.scene.update()	# required to make sure children are aware of their parent's new matrix

		if all(done): self._rec_preview_button.set_active(False); return True
		else: return False

	def bake_animation(self, button=None):
		for ob in self.context.scene.objects:
			ob.select = False

		for ob in self._rec_saved_objects:	# this should work even if objects are on hidden layers
			ob.hide = False
			ob.hide_select = False
			ob.select = True
			ob.rotation_mode = 'QUATERNION'	# prevents flipping

		if self._rec_saved_objects:
			self.sort_objects_for_preview()
			frame = 1
			self.context.scene.frame_set( frame )
			step = 1.0 / float(self.context.scene.render.fps / 3.0)
			now = 0.0
			done = False
			while not done:
				frame += 3
				self.context.scene.frame_set( frame )
				done = self.update_preview( now )
				now += step
				self.context.scene.update()
				bpy.ops.anim.keyframe_insert_menu( type='LocRot' )

		if self._rec_saved_shape_keys:
			for ob in self._rec_saved_shape_keys:
				M = self._rec_saved_shape_keys[ ob ]
				if not ob.data.shape_keys.animation_data:
					ob.data.shape_keys.animation_data_create()

				anim = ob.data.shape_keys.animation_data
				anim.action = None
				anim.action = bpy.data.actions.new( name='%s.SHAPE-ANIM'%ob.name )

				for block in M:
					curve = anim.action.fcurves.new( data_path='key_blocks["%s"].value'%block.name )
					buff = M[ block ]
					#curve.keyframe_points.add( len(buff) )
					for i in range(len(buff)):
						now, value = buff[i]
						frame = now * float( self.context.scene.render.fps )
						keyframe = curve.keyframe_points.insert( frame=frame, value=value )
						#keyframe.interpolation = 'CONSTANT'	# LINEAR, BEZIER
						#keyframe.co.y = value
						# FREE, VECTOR, ALIGNED, AUTO
						keyframe.handle_left_type = 'AUTO_CLAMPED'
						keyframe.handle_right_type = 'AUTO_CLAMPED'


			bpy.ops.anim.keyframe_insert_menu( type='LocRot' )

		print('Finished baking animation')


def set_transform( ob, pos, rot, set_body=False ):
	q = mathutils.Quaternion()
	qw,qx,qy,qz = rot
	q.w = qw; q.x=qx; q.y=qy; q.z=qz
	m = q.to_matrix().to_4x4()
	x,y,z = pos
	m[0][3] = x; m[1][3] = y; m[2][3] = z
	x,y,z = ob.scale	# save scale
	ob.matrix_world = m
	ob.scale = (x,y,z)	# restore scale
	if set_body and ob.name in ENGINE.objects:
		w = ENGINE.objects[ ob.name ]
		w.transform = (pos,rot)

######################################################




class PyppetUI( PyppetAPI ):

	def toggle_record( self, button, selected_only, preview, record_physics, record_objects, record_shapes ):
		if button.get_active():
			self.start_record( 
				selected_only = selected_only.get_active(),
				record_physics = record_physics.get_active(),
				record_objects = record_objects.get_active(),
				record_shapes = record_shapes.get_active(),
			)

			if preview.get_active():
				self._rec_preview_button.set_active(True)
		else:
			self.end_record()
			if preview.get_active():
				self._rec_preview_button.set_active(False)

	def toggle_preview( self, button ):
		self.preview = button.get_active()
		if self.preview:
			self.sort_objects_for_preview()
			self._rec_start_time = time.time()
			if self.play_wave_on_record: self.start_wave()
		else:
			if self.play_wave_on_record: self.stop_wave()


	def get_textures_widget(self):
		self._textures_widget_sw = sw = gtk.ScrolledWindow()
		self._textures_widget_container = frame = gtk.Frame()
		self._textures_widget_modal = root = gtk.VBox()
		sw.add_with_viewport( frame )
		sw.set_policy(True,False)
		frame.add( root )
		return sw

	def toggle_texture_slot(self,button, slot, opt, slider):
		setattr(slot, opt, button.get_active())
		if button.get_active(): slider.show()
		else: slider.hide()

	def load_texture(self,url, texture):
		print(url)
		if texture.type != 'IMAGE': texture.type = 'IMAGE'
		if not texture.image:
			texture.image = bpy.data.images.new(name=url.split('/')[-1], width=64, height=64)
			texture.image.source = 'FILE'
		texture.image.filepath = url
		#texture.image.reload()

	def update_footer(self, ob):
		if ob.type != 'MESH': return
		return # DEPRECATED
		print('updating footer')
		self._textures_widget_container.remove( self._textures_widget_modal )
		self._textures_widget_modal = root = gtk.VBox()
		self._textures_widget_container.add( root )

		if not ob.data.materials: ob.data.materials.append( bpy.data.materials.new(name=ob.name) )
		mat = ob.data.materials[0]

		for i in range(4):
			row = gtk.HBox(); root.pack_start( row )
			row.set_border_width(3)
			row.pack_start( gtk.Label('%s: '%(i+1)), expand=False )

			if not mat.texture_slots[ i ]: mat.texture_slots.add(); mat.texture_slots[ i ].texture_coords = 'UV'
			slot = mat.texture_slots[ i ]
			if not slot.texture: slot.texture = bpy.data.textures.new(name='%s.TEX%s'%(ob.name,i), type='IMAGE')

			gcolor = rgb2gdk( *slot.color )
			b = gtk.ColorButton(gcolor)
			b.set_relief( gtk.RELIEF_NONE )
			row.pack_start( b, expand=False )
			b.connect('color-set', color_set, gcolor, slot )

			combo = gtk.ComboBoxText()
			row.pack_start( combo, expand=False )
			for i,type in enumerate( 'MIX ADD SUBTRACT OVERLAY MULTIPLY'.split() ):
				combo.append('id', type)
				if type == slot.blend_type: gtk.combo_box_set_active( combo, i )
			combo.set_tooltip_text( 'texture blend mode' )
			combo.connect('changed', lambda c,s: setattr(s,'blend_type',c.get_active_text()), slot)

			for name,uname,fname in [('color','use_map_color_diffuse','diffuse_color_factor'), ('normal','use_map_normal','normal_factor'), ('alpha','use_map_alpha','alpha_factor'), ('specular','use_map_specular','specular_factor')]:

				slider = Slider( slot, name=fname, title='', max=1.0, driveable=False, border_width=0, no_show_all=True )
				b = gtk.CheckButton( name )
				b.set_active( getattr(slot,uname) )
				b.connect('toggled', self.toggle_texture_slot, slot, uname, slider.widget)
				row.pack_start( b, expand=False )
				row.pack_start( slider.widget )
				if b.get_active(): slider.widget.show()
				else: slider.widget.hide()

			row.pack_start( gtk.Label() )
			e = FileEntry( '', self.load_texture, slot.texture )
			row.pack_start( e.widget, expand=False )

		root.show_all()

	def get_wave_widget(self):
		frame = gtk.Frame()
		root = gtk.VBox(); frame.add( root )

		e = FileEntry( 'wave file: ', self.open_wave )
		root.pack_start( e.widget )

		e.widget.pack_start( gtk.Label() )

		self._wave_file_length_label = a = gtk.Label()
		e.widget.pack_start( a, expand=False )

		widget = self.audio.microphone.get_widget()
		e.widget.pack_start( widget, expand=False )

		bx = gtk.HBox(); root.pack_start( bx )

		b = gtk.ToggleButton( icons.PLAY )
		b.connect('toggled', self.toggle_wave )
		bx.pack_start( b, expand=False )

		b = gtk.CheckButton('loop')
		#b.set_active( self.play_wave_on_record )
		#b.connect('toggled', lambda b: setattr(self,'play_wave_on_record',b.get_active()))
		bx.pack_start( b, expand=False )


		bx.pack_start( gtk.Label() )

		self._wave_time_label = a = gtk.Label()
		bx.pack_start( a, expand=False )

		bx.pack_start( gtk.Label() )

		b = gtk.CheckButton('auto-play on record')
		b.set_active( self.play_wave_on_record )
		b.connect('toggled', lambda b: setattr(self,'play_wave_on_record',b.get_active()))
		bx.pack_start( b, expand=False )

		return frame

	def toggle_wave(self,button):
		if button.get_active(): self.start_wave()
		else: self.stop_wave()

	def start_wave(self):
		self.wave_playing = True
		if self.wave_speaker:
			self.wave_speaker.play()

	def stop_wave(self):
		self.wave_playing = False
		if self.wave_speaker:
			self.wave_speaker.stop()

	def open_wave(self, url):
		if url.lower().endswith('.wav'):
			print('loading wave file', url)
			self.wave_url = url
			wf = wave.open( url, 'rb')
			fmt = wf.getsampwidth()
			assert fmt==2	# 16bits
			chans = wf.getnchannels()
			self.wave_frequency = wf.getframerate()
			## cache to list of chunks (bytes) ##
			frames = wf.getnframes()
			samples = wf.readframes(frames)
			wf.close()
			print('wave file loaded')
			txt = 'seconds: %s' %(frames / self.wave_frequency)
			self._wave_file_length_label.set_text( txt )

			self.wave_speaker = Speaker( 
				frequency=self.wave_frequency, 
				stereo = chans==2,
				streaming=False,
			)
			self.wave_speaker.cache_samples( samples )

	def get_recording_widget(self):
		frame = gtk.Frame()
		root = gtk.VBox(); frame.add( root )

		bx = gtk.VBox(); root.pack_start( bx )

		p = gtk.CheckButton()
		p.set_active(True)
		p.set_tooltip_text('preview playback while recording (slower)')
		bx.pack_start( p, expand=False )

		self._rec_preview_button = b = gtk.ToggleButton( 'preview %s' %icons.PLAY )
		b.connect('toggled', self.toggle_preview)
		bx.pack_start( b, expand=False )

		bx.pack_start( gtk.Label() )
		self._rec_current_time_label = gtk.Label('-')
		bx.pack_start( self._rec_current_time_label, expand=False )
		bx.pack_start( gtk.Label() )

		c = gtk.CheckButton('selected')
		c.set_active(False)
		c.set_tooltip_text('only record selected objects')
		bx.pack_start( c, expand=False )

		h = gtk.CheckButton('physics')
		h.set_active(True)
		h.set_tooltip_text('record objects with physics')
		bx.pack_start( h, expand=False )


		t = gtk.CheckButton('transforms')
		t.set_active(True)
		t.set_tooltip_text('record object position and rotation')
		bx.pack_start( t, expand=False )

		s = gtk.CheckButton('shape-keys')
		s.set_tooltip_text('record mesh shape-keys')
		bx.pack_start( s, expand=False )


		b = gtk.ToggleButton( 'record %s' %icons.RECORD )
		b.set_tooltip_text('record selected objects')
		b.connect('toggled', self.toggle_record, c, p, h, t, s )
		bx.pack_start( b, expand=False )


		b = gtk.Button( 'commit %s' %icons.WRITE )
		b.set_tooltip_text('save animation pass for baking')
		b.connect('clicked', self.commit_recording)
		bx.pack_start( b, expand=False )

		bx.pack_start( gtk.Label() )

		b = gtk.Button( 'bake %s' %icons.SINE_WAVE )
		b.set_tooltip_text('bake all commited passes to animation curves')
		b.connect('clicked', self.bake_animation)
		bx.pack_start( b, expand=False )

		b = gtk.Button( 'reset %s' %icons.REFRESH )
		b.set_tooltip_text('delete animation commit buffer')
		b.connect('clicked', self.clear_recording)
		bx.pack_start( b, expand=False )



		root.pack_start( self.get_playback_widget() )

		return frame

	def toggle_blender_anim_playback( self, b ):
		if b.get_active(): bpy.ops.screen.animation_play()
		else: bpy.ops.screen.animation_cancel()

	def get_playback_widget(self):
		frame = gtk.Frame()
		root = gtk.HBox(); frame.add( root )

		b = gtk.ToggleButton( icons.PLAY )
		b.connect('toggled', self.toggle_blender_anim_playback)
		root.pack_start( b, expand=False )

		b = gtk.SpinButton()
		self._current_frame_adjustment = adj = b.get_adjustment()
		adj.configure( 
			value=self.context.scene.frame_current, 
			lower=self.context.scene.frame_start, 
			upper=self.context.scene.frame_end, 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		adj.connect('value-changed', lambda a,s: setattr(s.context.scene, 'frame_current',int(a.get_value())), self)
		scale = gtk.HScale( adj )
		root.pack_start( scale )
		scale.set_value_pos(gtk.POS_LEFT)
		scale.set_digits(0)
		root.pack_start( b, expand=False )

		b = gtk.SpinButton()
		root.pack_start( b, expand=False )
		self._start_frame_adjustment = adj = b.get_adjustment()
		adj.configure( 
			value=self.context.scene.frame_start, 
			lower=0, 
			upper=2**16, 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		adj.connect('value-changed', self.adjust_playback_range)

		b = gtk.SpinButton()
		root.pack_start( b, expand=False )
		self._end_frame_adjustment = adj = b.get_adjustment()
		adj.configure( 
			value=self.context.scene.frame_end, 
			lower=0, 
			upper=2**16, 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		adj.connect('value-changed', self.adjust_playback_range)

		return frame

	def adjust_playback_range(self, adj):
		self._current_frame_adjustment.configure( 
			value=self.context.scene.frame_current, 
			lower=self._start_frame_adjustment.get_value(), 
			upper=self._end_frame_adjustment.get_value(), 
			step_increment=1,
			page_increment=1,
			page_size=1,
		)
		self.context.scene.frame_start = self._start_frame_adjustment.get_value()
		self.context.scene.frame_end = self._end_frame_adjustment.get_value()




	def create_header(self, modal_frame=None):
		left = []; right = []
		toolbar = Toolbar( left, right, modal_frame=modal_frame )
		return toolbar

	def create_footer(self, modal_frame=None):
		left = []


		s = gtk.Switch()
		s.connect('button-press-event', self.cb_toggle_physics )
		s.set_tooltip_text( 'toggle physics' )
		left.append( s )

		b = gtk.ToggleButton( icons.PLAY_PHYSICS ); b.set_relief( gtk.RELIEF_NONE )
		b.connect('toggled', lambda b: ENGINE.toggle_pause(b.get_active()))
		left.append( b )

		b = gtk.CheckButton()
		b.connect('toggled', lambda b: setattr(self,'playback_blender_anim',b.get_active()))
		b.set_tooltip_text('playback blender animation when physics is on')
		left.append( b )

		right = []

		#b = gtk.Button( icons.BLENDER )
		#b.connect('clicked', self.embed_blender_window)
		#b.set_tooltip_text( 'embed blender window' )
		#right.append( b )
		if os.path.isfile( self._3dsmax.exe_path ):
			b = gtk.Button( '3dsMax' )
			b.connect('clicked', self.open_3dsmax)
			b.set_tooltip_text( 'open 3dsmax' )
			right.append( b )

		self._bottom_toggle_button = b = gtk.ToggleButton( icons.BOTTOM_UI ); b.set_relief( gtk.RELIEF_NONE )
		b.set_active(True)
		b.connect('toggled',self.toggle_footer)
		right.append( b )


		toolbar = Toolbar( left, right, modal_frame=modal_frame )
		return toolbar




	def toggle_header_views(self,b):
		if b.get_active(): self._header_views.show()
		else: self._header_views.hide()

	def toggle_overlay(self,b):
		if b.get_active(): self.window.set_opacity( 0.8 )
		else: self.window.set_opacity( 1.0 )

	def toggle_left_tools(self,b):
		if b.get_active(): self._left_tools.show()
		else: self._left_tools.hide()

	def toggle_right_tools(self,b):
		if b.get_active(): self.toolsUI.widget.show()
		else: self.toolsUI.widget.hide()

	def toggle_footer(self,b):
		if b.get_active(): self.footer.show()
		else: self.footer.hide()



	def create_tools( self, parent ):
		self._left_tools = gtk.VBox()
		self._left_tools.set_border_width( 2 )
		self._right_tools = gtk.VBox()
		self._right_tools.set_border_width( 2 )

		## add left tools to parent - in scrolled window
		sw = gtk.ScrolledWindow()
		sw.add_with_viewport( self._left_tools )
		sw.set_policy(True,False)
		#sw.set_size_request( 250, 200 )
		parent.pack_start( sw, expand=True )
		## add right tools to parent - PACK_END
		#parent.pack_end( self._right_tools, expand=False )


		#################### outliner ##################
		box = self._right_tools

		tool = ModifiersTool(
			icons.MODIFIERS, 
			short_name=icons.MODIFIERS_ICON 
		)
		box.pack_start( tool.widget, expand=True )

		tool = ConstraintsTool(
			icons.CONSTRAINTS, 
			short_name=icons.CONSTRAINTS_ICON 
		)
		box.pack_start( tool.widget, expand=True )

		box.pack_start( gtk.Label() )

		ex = DetachableExpander( icons.JOINTS, icons.JOINTS_ICON )
		box.pack_start( ex.widget, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'joints' ] = (ex,note)
		Pyppet.register( self.update_joints_widget )

		ex = DetachableExpander( icons.PHYSICS_RIG, icons.PHYSICS_RIG_ICON )
		box.pack_start( ex.widget, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'solver' ] = (ex,note)
		Pyppet.register( self.update_solver_widget )

		ex = DetachableExpander( icons.ACTIVE_BONE, icons.ACTIVE_BONE_ICON )
		box.pack_start( ex.widget, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'active-bone' ] = (ex,note)
		Pyppet.register( self.update_bone_widget )

		ex = DetachableExpander( icons.DYNAMIC_TARGETS, icons.DYNAMIC_TARGETS_ICON )
		box.pack_start( ex.widget, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'dynamic-targets' ] = (ex,note)
		Pyppet.register( self.update_dynamic_targets_widget )

		ex = DetachableExpander( icons.DRIVERS, icons.DRIVERS_ICON )
		box.pack_start( ex.widget, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'drivers' ] = (ex,note)
		Pyppet.register( self.update_drivers_widget )

		#######################################
		#					LEFT
		#######################################

		ex = DetachableExpander( icons.PHYSICS, icons.PHYSICS_ICON )
		self._left_tools.pack_start( ex.widget, expand=False )
		note = gtk.Notebook(); ex.add( note )
		self._left_tools_modals[ 'forces' ] = (ex,note)
		Pyppet.register( self.update_forces_widget )


		#################### webgl #####################
		ex = DetachableExpander( icons.WEBGL, short_name=icons.WEBGL_ICON, expanded=False )
		self._left_tools.pack_start( ex.widget, expand=False )
		note = gtk.Notebook(); ex.add( note )

		#widget = self.websocket_server.webGL.get_fx_widget_page1()
		#note.append_page( widget, gtk.Label( icons.FX_LAYERS1 ) )
		#widget = self.websocket_server.webGL.get_fx_widget_page2()
		#note.append_page( widget, gtk.Label( icons.FX_LAYERS2 ) )


		if 0:	# TODO get gui from players
			page = gtk.VBox()
			b = CheckButton( 'randomize', tooltip='toggle randomize camera' )
			b.connect( self, path='camera_randomize' )
			page.pack_start( b.widget, expand=False )

			b = CheckButton( 'godrays', tooltip='toggle godrays effect' )
			b.connect( self, path='godrays' )
			page.pack_start( b.widget, expand=False )

			for name in 'camera_focus camera_aperture camera_maxblur'.split():
				if name == 'camera_aperture':
					slider = Slider( self, name=name, title=name, max=0.2, driveable=True )
				else:
					slider = Slider( self, name=name, title=name, max=3.0, driveable=True )
				page.pack_start( slider.widget, expand=False )
			note.append_page(page, gtk.Label( icons.CAMERA) )


		ex = DetachableExpander( 'animation', short_name='animation', expanded=False )
		self._left_tools.pack_start( ex.widget, expand=False )
		note = gtk.Notebook()
		ex.add( note )
		note.set_tab_pos( gtk.POS_BOTTOM )

		page = gtk.Frame()
		note.append_page( page, gtk.Label(icons.RECORD) )
		page.add( self.get_recording_widget() )

		page = gtk.Frame()
		note.append_page( page, gtk.Label(icons.SINE_WAVE) )
		page.add( self.get_wave_widget() )

		page = gtk.Frame()
		note.append_page( page, gtk.Label(icons.TEXTURE) )
		page.add( self.get_textures_widget() )

		page = gtk.Frame()
		note.append_page( page, gtk.Label(icons.KEYBOARD) )

		if self.audio.synth:
			w = self.audio.synth.channels[0].get_widget()
			page.add( w )


		return self._left_tools, self._right_tools



	def update_drivers_widget( self, ob ):
		EX,root = self._left_tools_modals[ 'drivers' ]
		EX.remove( root )
		root = gtk.VBox(); EX.add( root )
		self._left_tools_modals[ 'drivers' ] = (EX,root)


		############# direct transform ##############
		ex = Expander( 'direct transform' )
		root.pack_start( ex.widget, expand=False )
		ex.append(
			NotebookVectorWidget(ob,'location', title='Location', expanded=False, min=-10, max=10).widget, 
		)
		ex.append(
			NotebookVectorWidget(ob,'rotation_euler', title='Rotation', expanded=False, min=-math.pi, max=math.pi).widget, 
		)
		ex.append(
			NotebookVectorWidget(ob,'scale', title='Scale', expanded=False, min=0, max=10).widget, 
		)


		############# physics driver forces ##############
		ex = Expander('force drivers')
		root.pack_start( ex.widget, expand=False )

		s = Slider(
			ob, name='ode_force_driver_rate', 
			title='additive-driver falloff', 
			min=0.0, max=1.0,
		)
		ex.append(s.widget)


		note = gtk.Notebook()
		ex.append( note )

		page = gtk.VBox(); page.set_border_width( 2 )
		note.append_page( page, gtk.Label('Global') )
		nice = {
			'ode_global_force':'Global Force',
			'ode_global_torque':'Global Torque',
		}
		tags='ode_global_force ode_global_torque'.split()
		for i,tag in enumerate(tags):
			page.pack_start(
				NotebookVectorWidget(ob,tag, title=nice[tag], expanded=i is 0, min=-400, max=400).widget, 
				expand=False
			)

		page = gtk.VBox(); page.set_border_width( 2 )
		note.append_page( page, gtk.Label('Local') )
		nice = {
			'ode_local_force':'Local Force',
			'ode_local_torque':'Local Torque',
		}
		tags='ode_local_force ode_local_torque'.split()
		for i,tag in enumerate(tags):
			page.pack_start(
				NotebookVectorWidget(ob,tag, title=nice[tag], expanded=i is 0, min=-400, max=400).widget, 
				expand=False
			)

		EX.show_all()

	def update_forces_widget( self, ob ):
		EX,root = self._left_tools_modals[ 'forces' ]
		EX.remove( root )
		root = gtk.VBox(); EX.add( root )
		self._left_tools_modals[ 'forces' ] = (EX,root)

		b = CheckButton( tooltip='use soft collision', frame=False)
		b.connect(ob, 'ode_use_soft_collision')
		ex = Expander('soft collision', append=b.widget)
		root.pack_start( ex.widget, expand=False )

		s = Slider( ob, name='ode_soft_collision_erp', title='ERP' )
		ex.append( s.widget )
		s = Slider( ob, name='ode_soft_collision_cfm', title='CFM' )
		ex.append( s.widget )

		ex = Expander('damping')
		root.pack_start( ex.widget, expand=False )
		bx = gtk.VBox(); ex.add( bx )

		s = Slider(
			ob, name='ode_linear_damping', title='linear',
			min=0.0, max=1.0,
		)
		bx.pack_start(s.widget, expand=False)

		s = Slider(
			ob, name='ode_angular_damping', title='angular',
			min=0.0, max=1.0,
		)
		bx.pack_start(s.widget, expand=False)

		ex = Expander('forces')
		root.pack_start( ex.widget, expand=False )
		note = gtk.Notebook(); ex.add( note )

		page = gtk.VBox(); page.set_border_width( 2 )
		note.append_page( page, gtk.Label( 'Global' ) )
		nice = {
			'ode_constant_global_force':'Constant Global Force', 
			'ode_constant_global_torque':'Constant Global Torque', 
		}
		tags='ode_constant_global_force ode_constant_global_torque'.split()
		for i,tag in enumerate(tags):
			frame = gtk.Frame( nice[tag] )
			page.pack_start( frame, expand=False )
			bx = gtk.VBox(); frame.add( bx )
			for i in range(3):
				slider = Slider(
					ob, tag, title='xyz'[i], 
					target_index=i, driveable=True,
					min=-500, max=500,
				)
				bx.pack_start( slider.widget, expand=False )

		page = gtk.VBox(); page.set_border_width( 2 )
		note.append_page( page, gtk.Label( 'Local' ) )
		nice = {
			'ode_constant_local_force':'Constant Local Force',
			'ode_constant_local_torque':'Constant Local Torque',
		}
		tags='ode_constant_local_force ode_constant_local_torque'.split()
		for i,tag in enumerate(tags):
			frame = gtk.Frame( nice[tag] )
			page.pack_start( frame, expand=False )
			bx = gtk.VBox(); frame.add( bx )
			for i in range(3):
				slider = Slider(
					ob, tag, title='xyz'[i], 
					target_index=i, driveable=True,
					min=-500, max=500,
				)
				bx.pack_start( slider.widget, expand=False )



		EX.show_all()

	def update_joints_widget( self, ob ):
		EX,root = self._left_tools_modals[ 'joints' ]
		EX.remove( root )
		root = gtk.VBox(); EX.add( root )
		self._left_tools_modals[ 'joints' ] = (EX,root)

		root.set_border_width( 2 )

		eb = gtk.EventBox(); root.pack_start( eb, expand=False )
		DND.make_destination( eb )
		eb.connect( 'drag-drop', self.cb_drop_joint, root )
		eb.add( gtk.Label( icons.DROP_HERE ) )
		eb.set_tooltip_text( 'drag and drop new child here' )

		for widget in get_joint_widgets( ob ):
			root.pack_start( widget, expand=False )

		EX.show_all()


	def cb_drop_joint(self, wid, context, x, y, time, page):
		wrap = DND.source_object
		widget = wrap.attach( self.selected )	# makes self.selected the joint-parent
		if widget:
			page.pack_start( widget, expand=False )
			widget.show_all()


	def update_solver_widget( self, ob ):

		########### physics joints: MODELS: Ragdoll, Biped, Rope ############
		if ob.type=='ARMATURE':
			EX,note = self._left_tools_modals[ 'solver' ]
			EX.remove( note )


			if ob.pyppet_model:
				root = gtk.VBox(); EX.add( root )
				root.set_border_width(3)
				self._left_tools_modals[ 'solver' ] = (EX,root)

				model = getattr(Pyppet, 'Get%s' %ob.pyppet_model)( ob.name )
				widget = getattr(model, 'Get%sWidget' %ob.pyppet_model)()
				root.pack_start( widget )


			else:
				note = gtk.Notebook(); EX.add( note )
				self._left_tools_modals[ 'solver' ] = (EX,note)

				for mname in Pyppet.MODELS:
					model = getattr(Pyppet, 'Get%s' %mname)( ob.name )
					label = model.get_widget_label()
					widget = getattr(model, 'Get%sWidget' %mname)()
					note.append_page( widget, label )


			EX.show_all()

	def update_bone_widget(self,ob):
		if ob.type=='ARMATURE':
			EX,note = self._left_tools_modals[ 'active-bone' ]
			EX.remove( note )
			if ob.pyppet_model:
				root = gtk.Frame(); EX.add( root )
				self._left_tools_modals[ 'active-bone' ] = (EX,root)
				model = getattr(Pyppet, 'Get%s' %ob.pyppet_model)( ob.name )
				widget = model.get_active_bone_widget()
				root.add( widget )
			EX.show_all()

	def update_dynamic_targets_widget(self,ob):
		if ob.type=='ARMATURE':
			EX,note = self._left_tools_modals[ 'dynamic-targets' ]
			EX.remove( note )
			if ob.pyppet_model:
				root = gtk.VBox(); EX.add( root )
				root.set_border_width(3)
				self._left_tools_modals[ 'dynamic-targets' ] = (EX,root)
				model = getattr(Pyppet, 'Get%s' %ob.pyppet_model)( ob.name )
				widget = model.get_targets_widget()
				root.pack_start( widget, expand=False )
			EX.show_all()




	def update_header(self,ob):
		modal1 = self.toolbar_header.reset()
		DND.make_source( modal1, ob )
		modal2 = self.toolbar_footer.reset()

		header = gtk.HBox()
		modal1.add( header )

		footer = root = gtk.HBox()
		modal2.add( footer )

		if ob.type == 'EMPTY':
			header.pack_start( gtk.Label(ob.name), expand=False )
			header.pack_start( gtk.Label() )
			slider = Slider(
				ob, name='empty_draw_size', title='size', tooltip='empty draw size',
				min=0.001, max=100.0,
			)
			header.pack_start( slider.widget )


		elif ob.type == 'ARMATURE':
			header.pack_start( gtk.Label(ob.name), expand=False )

			b = gtk.ToggleButton( icons.XRAY )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show xray')
			b.set_active(ob.show_x_ray)
			b.connect('toggled', lambda b,o: setattr(o,'show_x_ray',b.get_active()), ob)
			header.pack_start( b, expand=False )

			combo = gtk.ComboBoxText()
			header.pack_start( combo, expand=False )
			for i,type in enumerate( ['TEXTURED', 'SOLID', 'WIRE', 'BOUNDS'] ):
				combo.append('id', type)
				if type == ob.draw_type: gtk.combo_box_set_active( combo, i )
			combo.set_tooltip_text( 'view draw type' )
			combo.connect('changed', lambda c,o: setattr(o,'draw_type',c.get_active_text()), ob)


			b = gtk.ToggleButton( icons.MODE ); b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('toggle pose mode')
			header.pack_start( b, expand=False )
			b.set_active( self.context.mode=='POSE' )
			b.connect('toggled', self.toggle_pose_mode)

			header.pack_start( gtk.Label() )

			if ob.name not in self.entities:
				pass
			else:
				model = self.entities[ ob.name ]
				b = gtk.ToggleButton( icons.RIG_VISIBLE )
				b.set_relief( gtk.RELIEF_NONE )
				b.set_tooltip_text('show physics rig')
				b.set_active(model._show_rig)
				b.connect('toggled', model.toggle_rig_visible)
				header.pack_start( b, expand=False )





		elif ob.type=='LAMP':
			header.pack_start( gtk.Label(ob.name), expand=False )
			r,g,b = ob.data.color
			gcolor = rgb2gdk(r,g,b)
			b = gtk.ColorButton( gcolor )
			b.set_relief( gtk.RELIEF_NONE )
			header.pack_start( b, expand=False )
			b.connect('color-set', color_set, gcolor, ob.data )
			slider = Slider( ob.data, name='energy', title='', max=5.0, border_width=0, tooltip='light energy' )
			header.pack_start( slider.widget )

			slider = Slider( ob, name='webgl_lens_flare_scale', title='', max=2.0, border_width=0, tooltip='lens flare scale' )
			header.pack_start( slider.widget )

		elif ob.type == 'MESH' and self.context.mode=='EDIT_MESH':


			header.pack_start( gtk.Label() )

			b = gtk.Button( 'unwrap' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.uv.unwrap())

			b = gtk.Button( 'project' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.uv.smart_project())

			b = gtk.Button( 'subdivide' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.subdivide())

			b = gtk.Button( 'seam' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.mark_seam())

			b = gtk.Button( 'unseam' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.mark_seam(clear=True))

			b = gtk.Button( 'sharp' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.mark_sharp())

			b = gtk.Button( 'unsharp' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.mark_sharp(clear=True))

			b = gtk.Button( 'flip edge' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.edge_rotate())

			#b = gtk.Button( 'slide' )
			#root.pack_start( b, expand=False )
			#b.connect('clicked', lambda b: bpy.ops.mesh.edge_slide())

			b = gtk.Button( 'loop' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.loop_multi_select())

			b = gtk.Button( 'ring' )
			header.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.loop_multi_select(ring=True))

			header.pack_start( gtk.Label() )


			#root.pack_start( gtk.Label() )

			b = gtk.Button( 'merge' )
			root.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.merge())

			b = gtk.Button( 'split' )
			root.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.split())

			b = gtk.Button( 'extrude' )
			root.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.extrude_faces_move())

			b = gtk.Button( 'make' )
			root.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.edge_face_add())

			b = gtk.Button( 'fill' )
			root.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.fill())

			b = gtk.Button( 'triangulate' )
			root.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.quads_convert_to_tris())

			b = gtk.Button( 'quadragulate' )
			root.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.tris_convert_to_quads())

			b = gtk.Button( 'smooth' )
			root.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.faces_shade_smooth())

			b = gtk.Button( 'flat' )
			root.pack_start( b, expand=False )
			b.connect('clicked', lambda b: bpy.ops.mesh.faces_shade_flat())

		else:
			header.pack_start( gtk.Label(ob.name), expand=False )
			header.pack_start( gtk.Label('    '), expand=False )

			###################################################
			b = gtk.ToggleButton( icons.WIREFRAME )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show wireframe')
			b.set_active(ob.show_wire)
			b.connect('toggled', lambda b,o: setattr(o,'show_wire',b.get_active()), ob)
			header.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.NAME )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show name')
			b.set_active(ob.show_name)
			b.connect('toggled', lambda b,o: setattr(o,'show_name',b.get_active()), ob)
			header.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.AXIS )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show axis')
			b.set_active(ob.show_axis)
			b.connect('toggled', lambda b,o: setattr(o,'show_axis',b.get_active()), ob)
			header.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.XRAY )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show xray')
			b.set_active(ob.show_x_ray)
			b.connect('toggled', lambda b,o: setattr(o,'show_x_ray',b.get_active()), ob)
			header.pack_start( b, expand=False )

			combo = gtk.ComboBoxText()
			header.pack_start( combo, expand=False )
			for i,type in enumerate( ['TEXTURED', 'SOLID', 'WIRE', 'BOUNDS'] ):
				combo.append('id', type)
				if type == ob.draw_type: gtk.combo_box_set_active( combo, i )
			combo.set_tooltip_text( 'view draw type' )
			combo.connect('changed', lambda c,o: setattr(o,'draw_type',c.get_active_text()), ob)

			if ob.is_lod_proxy:	# prevent physics on LOD proxies
				pass
			elif ob.type == 'CURVE':
				slider = Slider(
					ob.data, name='bevel_depth', title='bevel', tooltip='bevel depth',
					min=0.0, max=1.0,
				)
				header.pack_start( slider.widget )

				slider = Slider(
					ob.data, name='bevel_resolution', title='resolution V', tooltip='bevel resolution',
					min=0, max=12, integer=True,
				)
				header.pack_start( slider.widget )

				slider = Slider(
					ob.data, name='resolution_u', title='resolution U', tooltip='resolution U (affecting all child splines)',
					min=1, max=24, integer=True,
				)
				footer.pack_start( slider.widget )

			elif ENGINE:
				wrapper = ENGINE.get_wrapper( ob )
				if not wrapper.is_subgeom:	# sub-geom not allowed to have a body

					g = gtk.ToggleButton( icons.GRAVITY ); g.set_relief( gtk.RELIEF_NONE )
					g.set_no_show_all(True)

					Mslider = Slider(
						ob, name='ode_mass', title='', tooltip='mass',
						min=0.001, max=100.0, no_show_all=True,
					)

					if ob.ode_use_body:
						g.show()
						Mslider.widget.show()
					else:
						g.hide()	# can't be in pose-mode bug! TODO fix me
						Mslider.widget.hide()

					b = gtk.ToggleButton( icons.BODY ); b.set_relief( gtk.RELIEF_NONE )
					b.set_tooltip_text('toggle body physics')
					header.pack_start( b, expand=False )
					b.set_active( ob.ode_use_body )
					b.connect('toggled', self.toggle_body, g, Mslider.widget)

					g.set_tooltip_text('toggle gravity')
					header.pack_start( g, expand=False )
					g.set_active( ob.ode_use_gravity )
					g.connect('toggled', self.toggle_gravity)

					header.pack_start(Mslider.widget, expand=True)



				combo = gtk.ComboBoxText()
				Fslider = Slider( ob, name='ode_friction', title='', max=2.0, border_width=0, no_show_all=True, tooltip='friction' )
				Bslider = Slider( ob, name='ode_bounce', title='', max=1.0, border_width=0, no_show_all=True, tooltip='bounce' )

				b = gtk.ToggleButton( icons.COLLISION ); b.set_relief( gtk.RELIEF_NONE )
				b.set_tooltip_text('toggle collision')
				footer.pack_start( b, expand=False )
				b.set_active( ob.ode_use_collision )
				b.connect('toggled', self.toggle_collision, combo, Fslider.widget, Bslider.widget)

				footer.pack_start( combo, expand=False )
				for i,type in enumerate( 'BOX SPHERE CAPSULE CYLINDER'.split() ):
					combo.append('id', type)
					if type == ob.game.collision_bounds_type:
						gtk.combo_box_set_active( combo, i )
				combo.set_tooltip_text( 'collision type' )
				combo.connect('changed',self.change_collision_type, ob )

				footer.pack_start( Fslider.widget )
				footer.pack_start( Bslider.widget )

				if ob.ode_use_collision:
					combo.show()
					Fslider.widget.show()
					Bslider.widget.show()

				else:
					combo.hide()
					Fslider.widget.hide()
					Bslider.widget.hide()

				combo.set_no_show_all(True)

			############################################################
			header.pack_start( gtk.Label() )

			b = gtk.ToggleButton( icons.STREAMING )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('stream mesh to webGL client')
			b.set_active(ob.webgl_stream_mesh)
			b.connect('toggled', lambda b,o: setattr(o,'webgl_stream_mesh',b.get_active()), ob)
			header.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.SUBSURF )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('auto subdivide in webGL client (only when camera is near mesh)')
			b.set_active(ob.webgl_auto_subdivison)
			b.connect('toggled', lambda b,o: setattr(o,'webgl_auto_subdivison',b.get_active()), ob)
			header.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.PROGRESSIVE_TEXTURES )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('use progressive texture loading (webgl)')
			b.set_active(ob.webgl_progressive_textures)
			b.connect('toggled', lambda b,o: setattr(o,'webgl_progressive_textures',b.get_active()), ob)
			header.pack_start( b, expand=False )


			footer.pack_start( gtk.Label() )
			slider = Slider( ob, name='webgl_normal_map', title='', max=5.0, border_width=0, tooltip='normal map scale' )
			footer.pack_start( slider.widget )

			b = gtk.Button( icons.REFRESH )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('rebake textures (webgl)')
			b.connect('clicked', self.reload_rebake, ob)
			header.pack_start( b, expand=False )



		modal1.show_all()
		modal2.show_all()


	def reload_rebake(self, button, ob ):
		for mat in ob.data.materials:
			for slot in mat.texture_slots:
				if slot and slot.texture and slot.texture.type=='IMAGE' and slot.texture.image:
					print('image reload', slot.texture.image)
					slot.texture.image.reload()

		if ob.name not in Server.GameManager.RELOAD_TEXTURES:
			print('rebake request', ob.name)
			Server.GameManager.RELOAD_TEXTURES.append( ob.name )


	def toggle_pose_mode(self,button):
		if button.get_active():
			bpy.ops.object.mode_set( mode='POSE' )
		else:
			bpy.ops.object.mode_set( mode='OBJECT' )

	def toggle_gravity(self, b):
		for ob in self.context.selected_objects: ob.ode_use_gravity = b.get_active()

	def toggle_collision(self, b, combo, fslider, bslider):
		for ob in self.context.selected_objects: ob.ode_use_collision = b.get_active()
		if b.get_active():
			combo.show()
			fslider.show()
			bslider.show()
		else:
			combo.hide()
			fslider.hide()
			bslider.hide()

	def toggle_body(self, b, gravity_button, mass_slider):
		for ob in self.context.selected_objects: ob.ode_use_body = b.get_active()
		if b.get_active():
			gravity_button.show()
			mass_slider.show()
		else:
			gravity_button.hide()
			mass_slider.hide()

	def change_collision_type(self,combo, ob):
		type = combo.get_active_text()
		ob.game.collision_bounds_type = type
		w = ENGINE.get_wrapper(ob)
		w.reset_collision_type()


	def create_ui(self, context):
		self._left_tools_modals = {}
		######################
		self.root = root = gtk.VBox()
		root.set_border_width( 10 )


		frame = gtk.Frame()
		popup = PopupWindow(
			child=root,
			toolbar=frame,
			deletable=True,
			on_close=self.exit,
			set_keep_above=False,
			fullscreen=True,
			width=800,
			height=480
		)
		self.window = popup.window

		################ HEADER ################
		self.toolbar_header = self.create_header( modal_frame=frame )
		root.pack_start( self.toolbar_header.widget, expand=False )
		#---------------------------------------------------------------

		#vpane = gtk.VPaned()
		#root.pack_start( vpane, expand=True )

		#---------------------------------------------------------------
		self._main_body_split = split = gtk.VBox()
		root.pack_start( split, expand=True )

		############ create tools popup  ###########
		self._tools_page = gtk.HBox()

		self.outlinerUI = OutlinerUI()
		ex = DetachableExpander( icons.OUTLINER, icons.OUTLINER_ICON )
		ex.add( self.outlinerUI.widget )
		self._tools_page.pack_start( ex.widget, expand=False )


		self.toolbar_footer = self.create_footer()

		left_tools, right_tools = self.create_tools( self._tools_page )
		_popup = PopupWindow(
			child= self._tools_page, 
			toolbar=self.toolbar_footer.widget,
			width=480,
			height=320
		)


		#_________________________________________
		## RIGHT TOOLS ##
		#self.root.pack_start( right_tools, expand=False )
		#root.pack_start( self.toolbar_footer.widget, expand=False )




		self.main_notebook = note = gtk.Notebook()		# TODO store blenders here
		#note.set_tab_pos( gtk.POS_BOTTOM )

		################# google chrome ######################
		#self._chrome_xsocket = gtk.Socket()
		#if not PYPPET_LITE:
		#self._chrome_xsocket, chrome_container = self.create_embed_widget(
		#	on_dnd = self.drop_on_view,
		#)
		self._main_view_split = gtk.HBox()
		self._main_body_split.pack_start( self._main_view_split, expand=True )
		#self._main_view_split.pack_start( chrome_container, expand=True )
		self._main_view_split.pack_start( right_tools, expand=False )

		############### Extra Tools #################
		#______________________________________________________#
		self.toolsUI = ToolsUI( self.lock, context )
		self.toolsUI.widget.set_border_width(2)
		right_tools.pack_end(
			self.toolsUI.devices_widget,
		)

		##############################
		##		right tools mini tools			#
		##############################
		left_tools.pack_start( self.toolsUI.widget )
		frame = gtk.Frame()


		############### Blender Embed Windows ##############
		if False:
			self._blender_embed_toolbar = gtk.VBox()
			self._blender_embed_toolbar.set_border_width( 10 )

			#if PYPPET_LITE:
			self._main_body_split.pack_start(
				self._blender_embed_toolbar,
				expand=True,
			)

			#else:
			#	vpane.add2(
			#		self._blender_embed_toolbar
			#	)
			self._blender_embed_toolbar.hide()
			self._blender_embed_toolbar.set_no_show_all(True)



		## FOOTER ##
		#self._tools_page.pack_start( right_tools, expand=False )
		

		##################################
		self.window.connect('destroy', self.exit )
		#self.window.show_all()
		popup.show()
		_popup.window.show_all()

		#for i in range(3): bpy.ops.screen.screen_set( delta=1 )
		#bpy.ops.wm.window_duplicate()
		#for i in range(3): bpy.ops.screen.screen_set( delta=-1 )

		#####################################
		#self._bottom_toggle_button.set_active(False)


		if False:
			if self.server.httpd:
				name = 'Mozilla Firefox' #'Chromium'
				xid = self.do_xembed( self._chrome_xsocket, name)
				if not xid:
					time.sleep(2)
					xid = self.do_xembed( self._chrome_xsocket, name)
					if not xid:
						msg = gtk.Label('ERROR [firefox browser not installed]' )
						self._main_body_split.pack_start( msg )
						msg.show()

			else:
				msg = gtk.Label('ERROR [port 8080] (streaming disabled)' )
				self._main_body_split.pack_start( msg )
				msg.show()

		##### OLD STUFF #####
		#self.do_xembed( bxsock, 'Blender' )
		#Blender.window_expand()
		#self.do_xembed( self._gimp_toolbox_xsocket, "Toolbox")
		#self.do_xembed( self._gimp_image_xsocket, "GNU Image Manipulation Program")
		#self.do_xembed( self._gimp_layers_xsocket, "Layers, Channels, Paths, Undo - Brushes, Patterns, Gradients")
		#self.do_xembed( self._nautilus_xsocket, "Home")
		#self.do_xembed( self._kivy_xsocket, "IcarusTouch")
		####################

		#self.webcam.start_thread( self.lock )
		return self.window

	## UNSTABLE
	def embed_blender_window_deprecated(self,button):
		button.set_no_show_all(True)	# only allow single embed
		button.hide()
		self._blender_embed_toolbar.set_no_show_all(False)
		self._blender_embed_toolbar.show()

		xsock, container = self.create_embed_widget(
			on_dnd = self.drop_on_view,
			on_resize = self.on_resize_blender,	# REQUIRED
			on_plug = self.on_plug_blender,		# REQUIRED
		)

		xsock.set_border_width(10)
		self._blender_embed_toolbar.pack_start(
			container
		)
		self._blender_embed_toolbar.show_all()
		self.do_xembed( xsock, 'Blender' )	# shows xsock


##########################################################
class App( PyppetUI ):
	#def start_webserver(self):
	#	self.server = Server.WebServer()
	#	#self.client = Client()
	#	self.websocket_server = Server.WebSocketServer( listen_host=Server.HOST_NAME, listen_port=8081 )
	#	self.websocket_server.start()	# polls in a thread


	def __init__(self):
		assert self.setup_blender_hack( bpy.context, use_gtk=True, use_3dsmax=True )		# moved to BlenderHack in core.py
		self._gtk_updated = False

		if '--debug' not in sys.argv:
			self.playback_blender_anim = False
			self.physics_running = False

			self.reset()		# PyppetAPI Public
			self.register( self.update_header ) # listen to active object change
			#self.register( self.update_footer )

			self.play_wave_on_record = True
			self.wave_playing = False
			self.wave_speaker = None

			self._rec_start_time = time.time()
			self._rec_shape_keys_cache = {}
			self._rec_objects = {}	# recording buffers
			self._rec_saved_objects = {}	# commited passes
			self._rec_saved_shape_keys = {}	# commited shape key passes

			self.preview = False
			self.recording = False
			self.active = True

			#self.lock = threading._allocate_lock()

			self.server = None
			self.websocket_server = None

			## EXPERIMENTAL - audio stuff ##
			if USE_OPENAL:
				self.audio = AudioThread()
				self.audio.start()
			else:
				self.audio = None

			########## webgl ############
			self.progressive_baking = True

			###########################

			self._blender_embed_windows = []
			self._blender_embed_toolbar = None

			self.blender_good_frames = 0
			self.blender_dropped_frames = 0
			self._mainloop_prev_time = time.time()
			print('------------init-complete---------------')




	def exit(self, arg):
		#os.system('killall chromium-browser')
		if hasattr(self,'webcam'): self.webcam.active = False

		self.audio.exit()
		self.active = False
		self.websocket_server.stop()
		self.server.close()
		sdl.Quit()
		print('...quit blender...')
		bpy.ops.wm.quit_blender()	# fixes hang on exit


	######################################################


	def cb_toggle_physics(self,button,event):
		if button.get_active(): self.toggle_physics(False)	# reversed
		else: self.toggle_physics(True)

	def toggle_physics(self,switch):
		self.physics_running = switch
		if switch:
			self.blender_start_time = time.time()
			self.blender_good_frames = 0
			self.blender_dropped_frames = 0

			ENGINE.start()
			if self.playback_blender_anim:
				bpy.ops.screen.animation_play()
		else:
			ENGINE.stop()
			for e in self.entities.values(): e.reset()
			if self.playback_blender_anim:
				bpy.ops.screen.animation_cancel()

			print('--blender good frames:', self.blender_good_frames)
			print('--blender dropped frames:', self.blender_dropped_frames)
			frames = self.blender_good_frames + self.blender_dropped_frames
			delta = (time.time() - self.blender_start_time) / float(frames)
			print('--blender average time per frame:', delta )
			print('--blender FPS:', 1.0 / delta )



	####################################################
	def debug_create_ui(self):
		'''
		the problem with the webcam must be in blender itself,
		something in blender is locking up V4L,
		TODO compile blender without BGE (BGE has videotexture)
			compile WITH_FFMPEG set to off should do the trick
		'''
		self.window = win = gtk.Window()
		root = gtk.VBox()
		win.add( root )
		root.pack_start( gtk.Label('hello world'), expand=False )

		#widget = Webcam.Widget( root )
		#self.webcam = widget.webcam
		#if self.webcam: self.webcam.start_thread()
		#DND.make_source( widget.dnd_container, 'WEBCAM' )	# make drag source to blender

		win.show_all()
		return win

	def debug_mainloop(self):
		while self.active:
			now = time.time()
			dt = 1.0 / ( now - self._mainloop_prev_time )
			self._mainloop_prev_time = now
			#print('FPS', dt)
			self.update_blender_and_gtk()
			self.websocket_server.update( self.context, timeout=0.3 )
			if not self._image_editor_handle: self.server.update( self.context )

	def mainloop(self):
		print('enter main')
		drops = 0
		while self.active:
			now = time.time()
			drop_frame = False
			dt = 1.0 / ( now - self._mainloop_prev_time )
			self._mainloop_prev_time = now
			#print('FPS', dt)

			if self.physics_running:

				#if drops > 15:	# force redraw
				#	drops = 0
				#	self.update_blender_and_gtk()
				#	self.blender_good_frames += 1

				if dt < 15.0:
					drop_frame = True
					drops += 1
					self.update_blender_and_gtk( drop_frame=True )
					self.blender_dropped_frames += 1
					#print('FPS', dt)
				else:
					self.update_blender_and_gtk()
					self.blender_good_frames += 1
			else:
				self.update_blender_and_gtk()

			############# update servers ##############
			#self.websocket_server.update( self.context )
			#if not self._image_editor_handle: # TODO replace this hack... could return no bytes (if not cached), and then client requests again after timeout.
			#	# ImageEditor redraw callback will update http-server,
			#	# if ImageEditor is now shown, still need to update the server.
			#	self.server.update( self.context )
			############################################



			################################
			now = now - self._rec_start_time
			if self.wave_playing and self.wave_speaker:
				self.wave_speaker.update()
				#print('wave time', self.wave_speaker.seconds)
				self._wave_time_label.set_text(
					'seconds: %s' %round(self.wave_speaker.seconds,2)
				)
				## use wave time if play on record is true ##
				if self.play_wave_on_record:
					now = self.wave_speaker.seconds

			models = self.entities.values()
			for mod in models: mod.update_poses()

			if ENGINE and ENGINE.active and not ENGINE.paused: self.update_physics( now, drop_frame )

			DriverManager.update()	# needs to come after solver updates and Dynamic Targets?

			if self.recording:
				for ob in self._rec_blender_objects:
					buff = self._rec_blender_objects[ ob ]
					pos,rot,scl = ob.matrix_world.decompose()
					px,py,pz = pos
					qw,qx,qy,qz = rot
					#sx,sy,sz = scl
					buff.append( (now, (px,py,pz), (qw,qx,qy,qz)) )

				for ob in self._rec_current_shape_keys:
					M = self._rec_current_shape_keys[ob]
					for block in M:
						buff = M[ block ]
						buff.append( (now, block.value) )


			#######################

			if drop_frame: continue

			win = Blender.Window( self.context.window )
			# grabcursor on click and drag (view3d only)
			#print(win, win.winid, win.grabcursor, win.windowstate, win.modalcursor)
			self.context.blender_has_cursor = bool( win.grabcursor )

			if self.physics_running and self.context.scene.frame_current==1:
				if self.context.screen.is_animation_playing:
					clear_cloth_caches()

			self.audio.update()		# updates gtk widgets

			if self.context.scene.frame_current != int(self._current_frame_adjustment.get_value()):
				self._current_frame_adjustment.set_value( self.context.scene.frame_current )

			self.update_callbacks()	# updates UI on active object changed
			self.toolsUI.iterate( self.context )
			self.outlinerUI.iterate( self.context )

			models = self.entities.values()
			for mod in models: mod.update_ui( self.context )


			if self.recording or self.preview:
				self._rec_current_time_label.set_text( 'seconds: %s' %round(now,2) )
			if self.preview: self.update_preview( now )









########## Cache for OutlinerUI and Joint functions ##########

def get_joint_widgets( parent ):
	r = []
	if parent.name in ObjectWrapper.OBJECTS:
		w = ObjectWrapper.OBJECTS[ parent.name ]
		for name in w.children:
			r.append( w.get_joint_widget(name) )
	return r

class ObjectWrapper( object ):
	OBJECTS = {}
	def __init__(self, ob):
		self.name = ob.name
		self.type = ob.type
		self.parents = {}
		self.children = {}
		ObjectWrapper.OBJECTS[ self.name ] = self

	def attach(self, parent):
		'''
		. from Gtk-Outliner drag parent to active-object,
		. active-object becomes child using ODE joint
		. pivot is relative to parent.
		'''
		assert parent != self.name		# can not attach to thy-self

		parent = bpy.data.objects[ parent ]
		child = bpy.data.objects[ self.name ]

		### store data here? 
		#cns = child.constraints.new('RIGID_BODY_JOINT')		# cheating
		#cns.show_expanded = False
		#cns.target = parent			# draws dotted connecting line in blender
		#cns.child = None			# child is None

		if parent.name not in ENGINE.bodies:
			parent.ode_use_body = True
		if child.name not in ENGINE.bodies:
			child.ode_use_body = True

		cw = ENGINE.get_wrapper(child)
		pw = ENGINE.get_wrapper(parent)
		joint = cw.new_joint( pw, name=parent.name )
		P = ObjectWrapper.OBJECTS[ parent.name ]
		P.children[ child.name ] = joint
		return P.get_joint_widget( child.name )


	############### joint widget ###########
	def get_joint_widget( self, child_name ):
		joint = self.children[ child_name ]

		ex = gtk.Expander( 'joint: ' + self.name ); ex.set_expanded(True)
		root = gtk.VBox(); ex.add( root )
		row = gtk.HBox(); root.pack_start( row, expand=False )

		b = gtk.CheckButton(); b.set_active(True)
		b.connect('toggled', lambda b,j: j.toggle(b.get_active()), joint)
		row.pack_start( b, expand=False )

		combo = gtk.ComboBoxText()
		row.pack_start( combo )
		for i,type in enumerate( Physics.JOINT_TYPES ):
			combo.append('id', type)
			if type == 'fixed':
				gtk.combo_box_set_active( combo, i )
		combo.set_tooltip_text( Physics.Joint.Tooltips['fixed'] )
		combo.connect('changed',self.change_joint_type, child_name )

		b = gtk.Button( icons.DELETE )
		b.set_tooltip_text( 'delete joint' )
		#b.connect('clicked', self.cb_delete, ex)
		row.pack_start( b, expand=False )

		#################################################
		###################### joint params ##############
		slider = Slider( name='ERP', value=joint.get_param('ERP') )
		root.pack_start( slider.widget, expand=False )
		slider.adjustment.connect(
			'value-changed', lambda adj, j: j.set_param('ERP',adj.get_value()),
			joint
		)
		slider = Slider( name='CFM', value=joint.get_param('CFM') )
		root.pack_start( slider.widget, expand=False )
		slider.adjustment.connect(
			'value-changed', lambda adj, j: j.set_param('CFM',adj.get_value()),
			joint
		)

		return ex

	def change_joint_type(self,combo, child):
		child = bpy.data.objects[ child ]
		type = combo.get_active_text()
		w = ENGINE.get_wrapper(child)
		w.change_joint_type( self.name, type )
		combo.set_tooltip_text( Physics.Joint.Tooltips[type] )


class OutlinerUI( object ):
	def __init__(self):
		self.objects = {}	# name : ObjectWrapper
		self.meshes = {}

		self.widget = sw = gtk.ScrolledWindow()
		sw.set_size_request( 180, 280 )
		self.lister = box = gtk.VBox()
		box.set_border_width(2)
		sw.add_with_viewport( box )
		sw.set_policy(True,False)


	def iterate(self, context):
		objects = context.scene.objects
		if len(objects) != len(self.objects): self.update_outliner(context)

	def update_outliner(self,context):
		names = context.scene.objects.keys()
		update = []
		for name in names:
			if name.startswith('127.'): continue
			if name not in self.objects: update.append( name )
		remove = []
		for name in self.objects:
			if name not in names: remove.append( name )

		update.sort()
		for name in update:
			ob = context.scene.objects[ name ]

			wrap = ObjectWrapper( ob )
			self.objects[ name ] = wrap

			wrap.gtk_outliner_container = eb = gtk.EventBox()
			root = gtk.HBox(); eb.add( root )
			self.lister.pack_start(eb, expand=False)
			#DND.make_source( eb, self.callback, name )

			b = gtk.Button(name)
			DND.make_source( b, wrap )		#self.callback, name )
			b.connect('clicked', lambda b,o: set_selection(o), ob)
			b.set_relief( gtk.RELIEF_NONE )
			root.pack_start( b, expand=False )

			root.pack_start( gtk.Label() )	# spacer

			b = gtk.ToggleButton( icons.VISIBLE ); root.pack_start( b, expand=False )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_active(ob.hide)
			b.set_tooltip_text('toggle visible')
			b.connect( 'toggled', lambda b,o: setattr(o,'hide',b.get_active()), ob)

			b = gtk.ToggleButton( icons.RESTRICT_SELECTION)
			root.pack_start( b, expand=False )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_active(ob.hide_select)
			b.set_tooltip_text('restrict selection')
			b.connect( 'toggled', lambda b,o: setattr(o,'hide_select',b.get_active()), ob)

			eb.show_all()


class MaterialsUI(object):
	## ob.material_slots	(missing .new or .add)
	### slot.link = 'DATA'
	### slot.material
	#ob.active_material_index = index	# works
	#ob.active_material = mat	# assigns material to active slot
	#bpy.ops.object.material_slot_assign()

	def __init__(self):
		self.widget = gtk.Frame()
		self.root = gtk.VBox()
		self.widget.add( self.root )
		Pyppet.register( self.on_active_object_changed )

	def on_active_object_changed(self, ob, expand_material=None):
		if ob.type not in ('MESH','META', 'CURVE'): return

		self.widget.remove( self.root )
		self.root = root = gtk.VBox()
		self.widget.add( self.root )
		root.set_border_width(2)

		if ob.type != 'CURVE':
			ex = gtk.Expander( 'webgl-tint' )
			ex.set_expanded(True)
			root.pack_start( ex, expand=False )
			hsv = gtk.HSV(); ex.add( hsv )
			r,g,b,a = ob.color
			hsv.set_color( *gtk.rgb2hsv(r,g,b) )
			hsv.connect('changed', self.color_changed, ob, 'color', None)

		if ob.type in ('MESH','CURVE'):
			exs = []
			for mat in ob.data.materials:
				if not mat: continue

				ex = gtk.Expander( mat.name ); exs.append( ex )
				eb = gtk.EventBox()	# expander background is colorized
				root.pack_start( eb, expand=False )
				eb.add( ex )

				subeb = gtk.Frame()	# not colorized
				bx = gtk.VBox(); subeb.add( bx )
				ex.add( subeb )
				#if mat == ob.active_material: ex.set_expanded(True)
				if mat.name == expand_material: ex.set_expanded(True)

				DND.make_source( ex, mat )

				color = rgb2gdk(*mat.diffuse_color)
				eb.modify_bg( gtk.STATE_NORMAL, color )

				#row = gtk.HBox(); bx.pack_start( row, expand=False )
				#row.pack_start( gtk.Label() )
				#b = gtk.ColorButton( color )
				#b.connect('color-set', self.color_set, color, mat, 'diffuse_color', eb)
				#row.pack_start( b, expand=False )
				#color = rgb2gdk(*mat.specular_color)
				#b = gtk.ColorButton( color )
				#b.connect('color-set', self.color_set, color, mat, 'specular_color', eb)
				#row.pack_start( b, expand=False )
				#row.pack_start( gtk.Label() )


				hsv = gtk.HSV()
				hsv.set_color( *gtk.rgb2hsv(*mat.diffuse_color) )
				hsv.connect('changed', self.color_changed, mat, 'diffuse_color', eb)
				bx.pack_start( hsv, expand=False )

				#hsv = gtk.HSV()		# some bug with GTK, two HSV's can not be used in tabs???
				#hsv.set_color( *gtk.rgb2hsv(*mat.specular_color) )
				#hsv.connect('changed', self.color_changed, mat, 'specular_color', eb)
				#note.append_page( hsv, gtk.Label('spec') )

				if ob.type == 'CURVE': continue

				subex = gtk.Expander( icons.SETTINGS )
				subex.set_border_width(2)
				bx.pack_start( subex, expand=False )
				bxx = gtk.VBox(); subex.add( bxx )

				slider = Slider( mat, name='diffuse_intensity', title='', max=1.0, driveable=True, tooltip='diffuse' )
				bxx.pack_start( slider.widget, expand=False )

				slider = Slider( mat, name='specular_intensity', title='', max=1.0, driveable=True, tooltip='specular' )
				bxx.pack_start( slider.widget, expand=False )

				slider = Slider( mat, name='specular_hardness', title='', max=500, driveable=True, tooltip='hardness' )
				bxx.pack_start( slider.widget, expand=False )

				slider = Slider( mat, name='emit', title='', max=1.0, driveable=True, tooltip='emission' )	# max is 2.0
				bxx.pack_start( slider.widget, expand=False )

				slider = Slider( mat, name='ambient', title='', max=1.0, driveable=True, tooltip='ambient' )
				bxx.pack_start( slider.widget, expand=False )

			#if len(exs)==1: exs[0].set_expanded(True)

			root.pack_start( gtk.Label() )
			b = gtk.Button('new material')
			b.connect('clicked', self.add_material, ob)
			root.pack_start( b, expand=False )

		self.root.show_all()

	def add_material(self,button, ob):
		bpy.ops.object.material_slot_add()
		index = len(ob.data.materials)-1
		mat = bpy.data.materials.new( name='%s.MAT%s' %(ob.name,index) )
		ob.data.materials[ index ] = mat
		self.on_active_object_changed( ob, expand_material=mat.name )

	#def color_set( self, button, color, mat, attr, eventbox ):
	#	button.get_color( color )
	#	r,g,b = gdk2rgb( color )
	#	vec = getattr(mat,attr)
	#	vec[0] = r
	#	vec[1] = g
	#	vec[2] = b
	#	if attr == 'diffuse_color': eventbox.modify_bg( gtk.STATE_NORMAL, color )

	def color_changed( self, hsv, mat, attr, eventbox ):
		r,g,b = get_hsv_color_as_rgb( hsv )
		vec = getattr(mat,attr)
		vec[0] = r
		vec[1] = g
		vec[2] = b
		if attr == 'diffuse_color':
			color = rgb2gdk(r,g,b)
			eventbox.modify_bg( gtk.STATE_NORMAL, color )

class Tool( object ):
	def update_modifiers(self, ob, force_update=False): assert None	# overload me

	def __init__(self, name, short_name=None):
		if not short_name: short_name = name
		self._pinned = False
		self._expander = ex = DetachableExpander(
			name, short_name=short_name
		)
		self._modal = gtk.EventBox()
		self._expander.add( self._modal )
		self.widget = ex.widget
		Pyppet.register( self.update )

class ConstraintsTool( Tool ):
	def update(self, ob, force_update=False):
		if self._pinned and not force_update: return

		self._expander.remove( self._modal )
		self._modal = root = gtk.VBox()
		self._expander.add( self._modal )

		frame = gtk.Frame()
		root.pack_start( frame, expand=False )
		row = gtk.HBox()
		row.set_border_width(4)
		frame.add( row )

		combo = gtk.ComboBoxText()

		b = gtk.Button( icons.PLUS )
		b.connect('clicked', self.add_constraint, combo, ob)
		row.pack_start( b, expand=False )

		row.pack_start( combo )
		for i,type in enumerate( CONSTRAINT_TYPES ): combo.append('id', type)
		gtk.combo_box_set_active( combo, 0 )


		b = gtk.ToggleButton( icons.PIN )
		b.set_relief( gtk.RELIEF_NONE ); b.set_tooltip_text( 'pin to active' )
		b.set_active( self._pinned )
		b.connect('toggled', lambda b,s: setattr(s,'_pinned',b.get_active()), self)
		row.pack_start( b, expand=False )


		stacker = VStacker()
		if USE_BLENDER_GREY:	stacker.widget.modify_bg( gtk.STATE_NORMAL, BG_COLOR )
		stacker.set_callback( self.reorder_constraint, ob )
		root.pack_start( stacker.widget )
		for cns in ob.constraints:
			e = Expander( cns.name, insert=gtk.Label(icons.DND) )
			R = RNAWidget( cns )
			e.add( R.widget )
			stacker.append( e.widget )

			b = gtk.ToggleButton( icons.VISIBLE )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('toggle constraint')
			b.set_active( not cns.mute )
			b.connect('toggled', lambda b,c: setattr(c,'mute',not b.get_active()), cns)
			e.header.pack_start( b, expand=False )

		self._expander.show_all()


	def add_constraint(self,b, combo, ob):
		mtype = combo.get_active_text()
		cns = ob.constraints.new( type=mtype )
		cns.name = mtype.lower()
		self.update( ob, force_update=True )

	def reorder_constraint( self, oldindex, newindex, ob ):
		'''
		ob.constraint is missing .insert method!
		workaround use bpy.ops.constraint.move_{up/down}
		TODO need to force ob to be active object
		'''
		name = ob.constraints[ oldindex ].name
		delta = oldindex - newindex
		for i in range( abs(delta) ):
			if delta < 0:
				bpy.ops.constraint.move_down( constraint=name, owner='OBJECT' )
			else:
				bpy.ops.constraint.move_up( constraint=name, owner='OBJECT' )


class ModifiersTool( Tool ):
	def update(self, ob, force_update=False):
		if self._pinned and not force_update: return

		self._expander.remove( self._modal )
		self._modal = root = gtk.VBox()
		self._expander.add( self._modal )

		frame = gtk.Frame()
		root.pack_start( frame, expand=False )
		row = gtk.HBox()
		row.set_border_width(4)
		frame.add( row )

		combo = gtk.ComboBoxText()

		b = gtk.Button( icons.PLUS )
		b.connect('clicked', self.add_modifier, combo, ob)
		row.pack_start( b, expand=False )

		row.pack_start( combo )
		for i,type in enumerate( MODIFIER_TYPES_MINI ): combo.append('id', type)
		gtk.combo_box_set_active( combo, 0 )

		b = gtk.ToggleButton( icons.PIN )
		b.set_relief( gtk.RELIEF_NONE ); b.set_tooltip_text( 'pin to active' )
		b.set_active( self._pinned )
		b.connect('toggled', lambda b,s: setattr(s,'_pinned',b.get_active()), self)
		row.pack_start( b, expand=False )


		stacker = VStacker()
		if USE_BLENDER_GREY:	stacker.widget.modify_bg( gtk.STATE_NORMAL, BG_COLOR )
		stacker.set_callback( self.reorder_modifier, ob )
		root.pack_start( stacker.widget )
		for mod in ob.modifiers:
			e = Expander( mod.name, insert=gtk.Label(icons.DND) )
			R = RNAWidget( mod )
			e.add( R.widget )
			stacker.append( e.widget )

			b = gtk.ToggleButton( icons.VISIBLE_RENDER )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show in render')
			b.set_active( mod.show_render )
			b.connect('toggled', lambda b,m: setattr(m,'show_render',b.get_active()), mod)
			e.header.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.VISIBLE )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show in viewport')
			b.set_active( mod.show_viewport )
			b.connect('toggled', lambda b,m: setattr(m,'show_viewport',b.get_active()), mod)
			e.header.pack_start( b, expand=False )

			b = gtk.ToggleButton( icons.VISIBLE_EDITMODE )
			b.set_relief( gtk.RELIEF_NONE )
			b.set_tooltip_text('show in edit-mode')
			b.set_active( mod.show_in_editmode )
			b.connect('toggled', lambda b,m: setattr(m,'show_in_editmode',b.get_active()), mod)
			e.header.pack_start( b, expand=False )

		self._expander.show_all()


	def add_modifier(self,b, combo, ob):
		mtype = combo.get_active_text()
		mod = ob.modifiers.new( name=mtype.lower(), type=mtype )
		self.update( ob, force_update=True )

	def reorder_modifier( self, oldindex, newindex, ob ):
		'''
		ob.modifiers is missing .insert method!
		workaround use bpy.ops.object.modifier_move_{up/down}
		TODO need to force ob to be active object
		'''
		name = ob.modifiers[ oldindex ].name
		delta = oldindex - newindex
		for i in range( abs(delta) ):
			if delta < 0:
				bpy.ops.object.modifier_move_down( modifier=name )
			else:
				bpy.ops.object.modifier_move_up( modifier=name )


class ToolsUI( object ):
	COLOR = gtk.GdkRGBA(0.96,.95,.95, 0.85)
	def new_page( self, title ):
		box = gtk.VBox()
		self.notebook.append_page( box, gtk.Label(title) )
		return box

	def __init__(self, lock, context):
		self.lock = lock
		self.widget = root = gtk.VBox()	# ROOT
		self.devices_widget = self.make_devices_widget()
		################### PHYSICS ###################
		ex = DetachableExpander( icons.PHYSICS, short_name=icons.PHYSICS_ICON )
		root.pack_start( ex.widget, expand=False )
		box = gtk.VBox()
		ex.add( box )
		self.engine = Physics.ENGINE
		self.physics_widget = PhysicsWidget( box, context )
		#############################################
		self._shape_pinned = False
		self._shape_expander = ex = DetachableExpander(
			icons.SHAPE_KEYS, 
			short_name=icons.SHAPE_KEYS_ICON 
		)
		root.pack_start( ex.widget, expand=False )
		self._shape_modal = gtk.EventBox()
		self._shape_expander.add( self._shape_modal )
		Pyppet.register( self.update_shape_keys )

		ex = DetachableExpander(
			icons.MATERIALS, 
			short_name=icons.MATERIALS_ICON,
			expanded=True
		)
		root.pack_start( ex.widget, expand=True )
		self.materials_UI = MaterialsUI()
		ex.add( self.materials_UI.widget )


	def make_devices_widget( self ):
		ex = DetachableExpander( icons.DEVICES, short_name=icons.DEVICES_ICON )
		self.devices_widget = ex.widget

		self.notebook = gtk.Notebook()
		ex.add( self.notebook )

		box = self.new_page( icons.GAMEPAD )	# gamepad page
		self.gamepads_widget = GamepadsWidget( box )

		if USE_OPENCV:
			box = self.new_page( icons.WEBCAM )	# webcam
			widget = Webcam.Widget( box )
			Pyppet.webcam = self.webcam = widget.webcam
			DND.make_source( widget.dnd_container, 'WEBCAM' )	# make drag source to blender embed window to assign to material

			#self.webcam.start_thread( self.lock )	# TODO fix me
			#self.webcam.lock = self.lock

			box = self.new_page( icons.KINECT )		# kinect page
			widget = Kinect.Widget( box )
			self.kinect = widget.kinect
			DND.make_source( widget.dnd_container, 'KINECT' )	# make drag source
			widget.start_threads( self.lock )

		box = self.new_page( icons.WIIMOTE )	# wiimote page
		self.wiimotes_widget = WiimotesWidget( box )

		box = self.new_page( icons.MICROPHONE )	# microphone page TODO move me
		widget = Pyppet.audio.microphone.get_analysis_widget()
		box.pack_start( widget )

		return self.devices_widget


	def update_shape_keys(self, ob, force_update=False):
		if self._shape_pinned and not force_update: return
		if ob.type not in ('MESH', 'LATTICE'): return

		self._shape_expander.remove( self._shape_modal )
		self._shape_modal = root = gtk.VBox()
		self._shape_expander.add( self._shape_modal )

		root.set_size_request( 240, 80 )
		frame = gtk.Frame()
		root.pack_start( frame, expand=False )
		row = gtk.HBox()
		frame.add( row )

		b = gtk.ToggleButton( icons.PIN )
		b.set_relief( gtk.RELIEF_NONE ); b.set_tooltip_text( 'pin to active' )
		b.set_active( self._shape_pinned )
		b.connect('toggled', lambda b,s: setattr(s,'_shape_pinned',b.get_active()), self)
		row.pack_start( b, expand=False )

		row.pack_start( gtk.Label(ob.name) )

		blocks = []
		if ob.data.shape_keys:
			for block in ob.data.shape_keys.key_blocks:
				if block.relative_key and block.relative_key != block:
					row = gtk.HBox(); root.pack_start( row, expand=False )
					row.pack_start( gtk.Label(block.name), expand=False )
					s = Slider(block, name='value', title='')
					row.pack_start( s.widget )
					blocks.append( block )

		Pyppet.set_recording_shape_keys_cache( ob, blocks )

		self._shape_expander.show_all()







	def iterate(self, context):
		self.physics_widget.update_ui( context )
		self.gamepads_widget.update()
		#self.engine.sync( context )

		if '_webcam_' in bpy.data.images:
			img = bpy.data.images['_webcam_']
			if img.bindcode:
				ptr = self.webcam.preview_image.imageData
				self.upload_texture_data( img, ptr )

		if '_kinect_' in bpy.data.images:
			img = bpy.data.images['_kinect_']
			if img.bindcode and self.kinect.PREVIEW_IMAGE:
				ptr = self.kinect.PREVIEW_IMAGE.imageData
				self.upload_texture_data( img, ptr )


	def upload_texture_data( self, img, ptr, width=240, height=180 ):
		## fast update raw image data into texture using image.bindcode
		## the openGL module must not load an external libGL.so/dll
		## BGL is not used here because raw pointers are not supported (bgl.Buffer is expected)

		bind = img.bindcode
		glBindTexture(GL_TEXTURE_2D, bind)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
		glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
		glTexImage2D(
			GL_TEXTURE_2D,		# target
			0, 						# level
			GL_RGB, 				# internal format
			width, 					# width
			height, 				# height
			0, 						# border
			GL_RGB, 				# format
			GL_UNSIGNED_BYTE, 	# type
			ptr						# pixels
		)




################################################
class PhysicsWidget(object):

	def __init__(self, parent, context):
		self.widget = note = gtk.Notebook()
		parent.add( self.widget )

		scn = context.scene

		page = gtk.VBox(); page.set_border_width( 3 )
		note.append_page( page, gtk.Label('settings') )

		#s = Slider(scn.game_settings, name='fps', title='FPS', min=1.0, max=120, tooltip='frames per second')
		#page.pack_start(s.widget, expand=False)

		s = Slider(scn.world, name='ode_speed', title='speed', min=0.01, max=0.1, precision=3, tooltip='physics speed')
		page.pack_start(s.widget, expand=False)

		s = Slider(scn.world, name='ode_ERP', title='ERP', min=0.0001, max=0.5, precision=3, tooltip='joint error reduction')
		page.pack_start(s.widget, expand=False)

		s = Slider(scn.world, name='ode_CFM', title='CFM', max=5, tooltip='joint constant mixing force')
		page.pack_start(s.widget, expand=False)

		## TODO - above was a bad idea, scn.world should not use callback driven RNA ##
		s = Slider(ENGINE, name='substeps', title='sub-steps', min=1, max=10, integer=True, tooltip='number of sub-steps (more steps yeild higher performance at the cost of acurate high-speed collisions')
		page.pack_start(s.widget, expand=False)


		page = gtk.VBox(); page.set_border_width( 3 )
		note.append_page( page, gtk.Label('damping') )

		s = Slider(scn.world, name='ode_linear_damping', title='linear', max=2, tooltip='linear damping', driveable=True)
		page.pack_start(s.widget, expand=False)

		s = Slider(scn.world, name='ode_angular_damping', title='angular', max=2, tooltip='angular damping', driveable=True)
		page.pack_start(s.widget, expand=False)


		page = gtk.VBox(); page.set_border_width( 3 )
		note.append_page( page, gtk.Label('gravity') )

		for i in range(3):
			s = Slider(
				context.scene.world, 
				name='ode_gravity', 
				title='xyz'[i],
				target_index=i,
				min=-20, max=20,
			)
			page.pack_start( s.widget, expand=False )

	def update_ui(self,context):
		#if context.active_object and context.active_object.name != self.selected:
		pass

########################## game pad #######################
class GamepadsWidget(object):
	def update(self):
		sdl.JoystickUpdate()
		for pad in self.gamepads: pad.update()
	def __init__(self, parent, context=None):
		self.gamepads = []
		root = gtk.VBox(); root.set_border_width( 2 )
		parent.add( root )
		note = gtk.Notebook(); root.pack_start( note, expand=True )
		note.set_tab_pos( gtk.POS_BOTTOM )
		for i in range( Gamepad.NUM_DEVICES ):
			pad = Gamepad(i); self.gamepads.append( pad )
			note.append_page( pad.widget, gtk.Label('%s'%i) )





class Gamepad( GameDevice ):	# class GameDevice see core.py
	'''
	SDL Gamepad wrapper
	'''
	NUM_DEVICES = sdl.NumJoysticks()
	def update(self):
		for i in range( self.num_axes ):
			value = self.dev.GetAxis(i) / 32767.0		# -32768 to 32767
			self.axes[i] = value
			self.axes_gtk[i].set_value(value)

		for i in range( self.num_buttons ):
			value = bool( self.dev.GetButton(i) )
			self.buttons[i] = value
			self.buttons_gtk[i].set_active( value )

		for i in range( self.num_hats ):
			self.hats[i] = self.dev.GetHat(i)

		#self.update_drivers()

	def __init__(self,index=0):
		self.index = index
		self.dev = sdl.JoystickOpen(index)
		self.configure_device(	# core API
			axes = self.dev.NumAxes(),
			buttons = self.dev.NumButtons(),
			hats = self.dev.NumHats(),
		)

		self.drivers = []
		self.widget = self.get_widget('gamepad')




#################### wiimote #################


class WiimotesWidget(object):
	def __init__(self, parent, context=None):
		self.manager = Wiimote.Manager( wiimotes=4 )
		self.root = root = gtk.VBox(); root.set_border_width( 2 )
		parent.add( root )
		self.connect_button = b = gtk.Button('connect wiimote(s)')
		b.connect('clicked', self.connect_wiimotes)
		root.pack_start( b, expand=False )

	def connect_wiimotes(self,b):
		found = self.manager.connect()
		if found:
			self.connect_button.hide()	# TODO connect and reconnect
			note = gtk.Notebook()
			self.root.pack_start( note, expand=True )
			note.set_tab_pos( gtk.POS_BOTTOM )
			for i,mote in enumerate(self.manager.wiimotes):
				note.append_page(
					mote.get_widget('wiimote'),
					gtk.Label('%s'%i)
				)
			note.show_all()



#####################################
if __name__ == '__main__':
	######## Pyppet Singleton #########
	Pyppet = App()

	import Server
	Server.set_api( user_api=Pyppet )
	Pyppet.setup_websocket_callback_api( server_api.API )
	Pyppet.start_server()

	#################################


	if '--debug' in sys.argv:
		win = Pyppet.debug_create_ui()
		Pyppet.setup_3dsmax( win.get_clipboard() )
		Pyppet.debug_mainloop()

	else:
		if not PYPPET_LITE:
			## chrome is already open by shell script, this only sets the page to localhost,
			## this is required otherwise python can not close the ports its listening on.
			#os.system('chromium-browser --app=http://localhost:8080 &')	# opens new window with name Untitled
			#os.system('chromium-browser localhost:8080 &')	# dbus opens a new tab
			time.sleep(0.1)
		print('-----create ui------')
		win = Pyppet.create_ui( bpy.context )	# bpy.context still valid before mainloop
		Pyppet.setup_3dsmax( win.get_clipboard() )
		print('-----main loop------')
		Pyppet.mainloop()



