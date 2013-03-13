bpy = None

def create_database(api): return Database(api)


class PackedProxy( object ):
	def __call__(self, *args, **kw): pass

	def _proxy(self, ob):
		self.__proxy = ob

	def __getattr__(self, name):
		if hasattr( self, '_database'):
			return self._database.get_object_attribute(self.__uid, name=name)
		else:
			return getattr(self.__proxy, name)

	def __setattr__(self,name,value):
		assert not name.startswith('__')
		try: ## try to save on object, assume it has its own database layer
			setattr(self.__proxy,name,value)
		except AttributeError: ## else fallback to saving in the custom database, and cache attribute
			setattr(self,name,value)
			if hasattr(self,'_database'):
				self._database.save_object_attribute( self.__uid, name=name, value=value)




class Material(PackedProxy): pass
class Texture(PackedProxy): pass

class Object(PackedProxy):

	def __init__( name, position, scale, quat, category, data ):
		ob = bpy.data.objects.new( name=name, object_data=data )
		self._proxy( ob )  ## hooks into database

		#ob.hide_select = True
		ob.rotation_mode = 'QUATERNION'
		#ob.draw_type = 'WIRE'
		#.empty_draw_type = 'CUBE'

		bpy.context.scene.objects.link( ob )

		if 0:
			m = ob.matrix.copy()
			x,y,z = position
			m[0][3] = x	# blender2.61 style
			m[1][3] = y
			m[2][3] = z

			ob.matrix_world = m

		## UPDATE in local space here, tested with scale
		#ob.scale = (avg, length*0.6, avg)	# set scale in local space

		bpy.context.scene.update()			# syncs .matrix_world with local-space set scale

class Database(object):
	def __init__(self, api):
		self.objects = {}
		global bpy
		bpy = api

	def update_object(self, name, position, scale, quat, category=None, data=None, vertices=None):
		'''add new object - 3dsmax stream sends update first'''
		if name not in self.objects:
			self.add_object(name, position, scale, quat, category=category, data=data)
		print('<db update object>', name, position)
		ob = self.objects[name]
		ob.location = position
		ob.scale = scale
		ob.rotation_quaternion = quat

		## vertex mesh streaming ##
		if vertices and ob.data:
			mesh = ob.data
			n1 = len(mesh.vertices)
			n2 = len(vertices)
			if n1 != n2:
				print('missmatch', n1, n2)  ## this bug is caused by 3ds import
			if n2 >= n1:
				print('mesh update')
				for i,v in enumerate(mesh.vertices):
					x,y,z = vertices[i]
					v.co.x=x; v.co.y=y; v.co.z=z ## assign vertex location ##
		############################

	def add_object(self, name, position, scale, quat, category=None, data=None):
		print('<db adding new object>', name)
		################ body #################
		proxy = Object( name, position, scale, quat, category, data )
		self.objects[name] = proxy
