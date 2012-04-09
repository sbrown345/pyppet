#!/usr/bin/python
# updated April 2012

import os,sys, time, ctypes
import wiiuse as wii

from core import *

class Wiimote( GameDevice ):
	WIIMOTE_BUTTONS = tuple('UDLR+-H12AB')
	_WIIUSE_BUTTONS_ORDER = (
		wii.WIIMOTE_BUTTON_UP,
		wii.WIIMOTE_BUTTON_DOWN,
		wii.WIIMOTE_BUTTON_LEFT,
		wii.WIIMOTE_BUTTON_RIGHT,
		wii.WIIMOTE_BUTTON_PLUS,
		wii.WIIMOTE_BUTTON_MINUS,
		wii.WIIMOTE_BUTTON_HOME,
		wii.WIIMOTE_BUTTON_ONE,
		wii.WIIMOTE_BUTTON_TWO,
		wii.WIIMOTE_BUTTON_A,
		wii.WIIMOTE_BUTTON_B,
	)
	def __init__(self, index=0, pointer=None):
		assert pointer
		self.index = index
		self.pointer = pointer
		wii.motion_sensing(pointer, 1)
		wii.set_leds( pointer, wii.WIIMOTE_LED_2)

		self.configure_device(
			axes=3,
			buttons=len(self.WIIMOTE_BUTTONS),
		)

	def update( self, wm ):
		for i,button in enumerate( self._WIIUSE_BUTTONS_ORDER ):
			if wii.IS_PRESSED(wm, button): self.buttons[ i ] = 1
			else: self.buttons[ i ] = 0

		self.axes[0] = (wm.contents.accel.x / 255.0) - 0.5
		self.axes[1] = (wm.contents.accel.y / 255.0) - 0.5
		self.axes[2] = (wm.contents.accel.z / 255.0) - 0.5


class Manager(object):
	def __init__( self, wiimotes=2 ):
		self._active = False
		self._nmotes = wiimotes
		self._pointer = wii.init( self._nmotes )	# returns array-like pointer
		self.wiimotes = []

	def exit( self ):
		self._active = False
		time.sleep(1)
		wii.cleanup( self._pointer, self._nmotes)

	def connect( self ):
		print('press 1+2 buttons on wiimote(s) now...')
		found = wii.find( self._pointer, self._nmotes, 5 )
		print( 'found wiimotes', found )
		if not found: return 0

		## NOT wii.connect - this is the raw bluetooth connect function
		connected = wii.wiiuse_connect( self._pointer, self._nmotes )
		assert connected
		print( 'connected wiimotes', connected )

		while len(self.wiimotes) < connected:
			index = len(self.wiimotes)
			mote = Wiimote(
				index = index,
				pointer = self._pointer[ index ]
			)
			self.wiimotes.append( mote )

		self._active = True
		return found

		
	def callback( self, state ):
		mote = self.wiimotes[ state.contents.uid - 1 ]
		mote.update( state )

	def iterate( self ):
		status = wii.update(
			self._pointer,
			self._nmotes,
			self.callback
		)

if __name__ == '__main__':
	w = Manager()
	if w.connect():
		while True:
			w.iterate()
			for mote in w.wiimotes:
				print( mote.axes )
	else:
		print('failed to connect')


