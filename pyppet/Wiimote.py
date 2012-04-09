#!/usr/bin/python
# updated April 2012

import os,sys, time, ctypes
import wiiuse as wii

from core import *

class Wiimote(object):
	def __init__(self, index=0, pointer=None):
		self.index = index
		self.pointer = pointer
		assert pointer
		wii.motion_sensing(pointer, 1)
		wii.set_leds( pointer, wii.WIIMOTE_LED_2)

		self.buttons = {}
		for char in 'ABUDLR-+H': self.buttons[char] = 0
		self.x = .0
		self.y = .0
		self.z = .0
		self.force = [.0]*3

	def update( self, wm ):
		bs = self.buttons
		for tag in 'UDLR+H-12AB': bs[ tag ] = 0
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_A)): bs['A'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_B)): bs['B'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_UP)): bs['U'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_DOWN)): bs['D'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_LEFT)): bs['L'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_RIGHT)): bs['R'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_MINUS)): bs['-'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_PLUS)): bs['+'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_ONE)): bs['1'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_TWO)): bs['2'] = 1
		if (wii.IS_PRESSED(wm, wii.WIIMOTE_BUTTON_HOME)): bs['H'] = 1
		self.x = wm.contents.accel.x
		self.y = wm.contents.accel.y
		self.z = wm.contents.accel.z
		self.force[0] = self.x
		self.force[1] = self.y
		self.force[2] = self.z


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
				print( mote.force )
	else:
		print('failed to connect')


