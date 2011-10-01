## setup RNA ballbacks on all, setup main interate on set-frame callback.
# setup MultiLOD: tundra jmonkey, 
import bpy
import gtk


class Database( object ):
	Levels = {}
	@classmethod
	def restore(self): pass
	@classmethod
	def save(self): pass

class Level( object ):
	def __init__(self, name='level1', engine='OGRE', renderer='REX', logic='HIVE'):
		self.name = name
		if name in Database.Levels:
			pass
		if engine == 'OGRE':
			import b2ogre
			self.b2ogre_config = b2ogre.load_config()
		if renderer == 'REX':	# 'JMONKEY'
			import realxtend
			self.renderer = realxtend.Tundra2(self) # socket
		if logic == 'HIVE':
			import hive
			self.logic = hive.Hive()

################################################
