bpy = None

def create_database(api): return Database(api)

class Database(object):
	def __init__(self, api):
		self.objects = {}
		global bpy
		bpy = api

	def update_object(self, name, position, scale, quat, category=None, data=None):
		'''add new object - 3dsmax stream sends update first'''
		if name not in self.objects:
			self.add_object(name, position, scale, quat, category=category, data=data)
		print('<db update object>', name, position)
		ob = self.objects[name]
		ob.location = position
		ob.scale = scale
		ob.rotation_quaternion = quat

	def add_object(self, name, position, scale, quat, category=None, data=None):
		print('<db adding new object>', name)
		################ body #################
		self.objects[name] = ob = bpy.data.objects.new( name=name, object_data=data )
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
