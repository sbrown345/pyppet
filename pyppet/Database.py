bpy = None

class Database(object):
	def __init__(self, api):
		self.objects = {}
		global bpy
		bpy = api

	def add_object(self, name, category, position, rotation, scale, replace=None):

		################ body #################
		self.objects[name] = ob = bpy.data.objects.new( name=name, object_data=replace )
		#ob.hide_select = True
		ob.rotation_mode = 'QUATERNION'
		#ob.draw_type = 'WIRE'
		#.empty_draw_type = 'CUBE'

		bpy.context.scene.objects.link( ob )

		m = ob.matrix.copy()
		x,y,z = position
		m[0][3] = x	# blender2.61 style
		m[1][3] = y
		m[2][3] = z

		ob.matrix_world = m

		## UPDATE in local space here, tested with scale
		#ob.scale = (avg, length*0.6, avg)	# set scale in local space

		bpy.context.scene.update()			# syncs .matrix_world with local-space set scale
