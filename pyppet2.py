import bpy
import sys
sys.path.append( '../' )
import bpyge

class App(object):
	def __init__(self):
		self.ui = bpyge.UI( self )
		self.devices = bpyge.Devices( self )
		self.world = bpyge.World( self )
		self.levels = []

	def create_level(self, name, previous=None, next=None, branches=[] ):
		lvl = bpyge.Level( self, name )
		self.levels.append( lvl )
		return lvl

	def load_level( self, name ):
		pass

app = App()
print('pyppet exit')

