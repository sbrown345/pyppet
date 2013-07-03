#!/usr/bin/python
# Bender RNA - copyright 2013 - Brett Hartshorn
# License: "New" BSD

class RNA_Database(object):
	'''
	similar to Blender's bpy.data API
	'''
	def __init__(self, dna_db):
		self.objects = {}
		self.meshes = {}
		self.cameras = {}
		self.lamps = {}
		self.materials = {}
		self.textures = {}
		self.scenes = {}
		self.groups = {}
		self.material_texture_slots = []	# material texture slots do not have "IDProps"
		self.spaces = {}
		self.others = {}

		for name in dna_db:
			_name = name.lower()+'s'
			if hasattr(self,_name):
				d = getattr(self,_name)

			elif name == 'Mesh':
				d = self.meshes
			elif name == 'Tex':
				d = self.textures
			elif name == 'MTex':
				d = self.material_texture_slots

			elif name.startswith('Space'):
				self.spaces[name] = d = []
			else:
				self.others[name] = d = []

			objects = dna_db[ name ]
			if type(d) is dict:
				for ob in objects:
					## this is an example of a array-of-struct where we only want the first item
					assert type(ob.id) is tuple and len(ob.id) > 0
					#if not len(ob.id)==4:
					#	print('unexpected id struct length', len(ob.id))
					# this will most often be length 4, but can also be 1, 3, 7, 11, 32 
					ob.id = ob.id[ 0 ]
					ob.name = n = ob.id.name[2:]  ## clip blender's hidden prefix
					assert n not in d
					d[ n ] = ob

			elif type(d) is list:
				for ob in objects:
					d.append( ob )

		## bpy api style for mesh ##
		for mesh in self.meshes.values():

			mesh.vertices = mesh.mvert
			mesh.loops = mesh.mloop
			mesh.polygons = mesh.mpoly
			mesh.edges = mesh.medge

			## setup mesh.materials similar to bpy API ##
			## TODO how to iterate a dna link?
			mesh.materials = {}
			#link = mesh.mat  ## TODO - fixme
			#if link and link.next:
			#	mesh.materials[ link.next.name ] = link.next

