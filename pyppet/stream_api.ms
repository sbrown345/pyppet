
global object_names = #()
global exported = #()
global export_queue = #()
global watching_transforms = #()
global mesh_cache = #()


setClipboardText( "" )

struct CachedMesh (name, verts, faces, edges, data)

function dump_object ob = (
	--print "dumping object: "
	--print ob.name

	path = "C:\\" + ob.name + ".3ds"
	exportFile path #noPrompt selectedonly:true
	print path

	if appendIfUnique exported ob.name do (
		c = CachedMesh name:ob.name verts:0 faces:0 edges:0 data:""
		append mesh_cache c
	)

)
function get_mesh_cache key = (
	result = undefined
	for pair in mesh_cache do (
		if pair.name == key do (
			result = pair
		)
	)
	result --# returns
)

function on_object_transformed ob = (
	--# the problem with dumping fbx here is that after export max is put back into select mode #--
	cname = getClassName ob
	txt = "@UPDATE:STREAM@" + cname + "@" + ob.name + "~" + ob.position as string + "|" + ob.scale as string + "|" + ob.rotation as string
	setClipboardText( txt )
)

function on_object_select ob = (
	--# when an object is first created it is already selected, and this wont be triggered until the
	--# selection changes, so we can watch here for ob.isSelected to be false,
	--# and then setup the watching of the transform.

	if ob.isSelected then (
		print "new sel"
		cname = getClassName ob
		txt = "@UPDATE:SELECT@" + cname + "@" + ob.name + "~" + ob.position as string + "|" + ob.scale as string + "|" + ob.rotation as string
		setClipboardText( txt )

	) else (
		if appendIfUnique watching_transforms ob.name do (
			when transform ob changes var do on_object_transformed var

			dump_object( ob )

			--# connection to Bender's database format: add_object, add_texture, add_material
			cname = getClassName ob
			txt = "@database:new_object@" + cname + "@" + ob.name + "~" + ob.position as string + "|" + ob.scale as string + "|" + ob.rotation as string
			setClipboardText( txt )

		)
	)
)


function redraw = (
	ob = $
	if (ob != undefined) do (
		if ob.category == #Standard_Primitives or ob.category == #Extended_Primitives or ob.category == #Editable_Objects do (
			if appendIfUnique object_names ob.name then (
				--# append to the export_queue, to be exported to FBX later when the mouse is released
				append export_queue ob
				when select ob changes var do on_object_select var

			) else (
				--# this hack exports new objects after an object has been created,
				--# but not while it is still being given its inital size,
				--# because we wait until mouse.mode is zero (no buttons pressed)
				if mouse.mode == 0 and export_queue.count > 0 do (
					o = export_queue[1]
					if appendIfUnique watching_transforms o.name do (
						when transform o changes var do on_object_transformed var
						on_object_transformed o
					)

					dump_object( export_queue[1] )
					deleteItem export_queue 1
				)
			)
		)
	)
)
registerRedrawViewsCallback redraw

function verts_to_string ob = (
	--a = ""
	--for v in ob.mesh.vertices do a += v.pos as string
	--a --# returns
	local ss = stringStream ""
	local fmt = "%"
	for v in ob.mesh.vertices do format fmt v.pos to:ss
	ss as string
)

--# both geometry and topology callbacks are called even if the user only had changed selection in editmesh mode.
--# to check for real changes we will need to manually compare vertex positions (string compare).
--# get_mesh_cache returns struct, caches verts_to_string in a.data

function on_geometry_changed ev id = (
	ob = GetAnimByHandle id[1]
	data = verts_to_string ob
	cname = getClassName ob

	a = get_mesh_cache ob.name
	if a.verts != ob.mesh.vertices.count or a.faces != ob.mesh.faces.count or a.edges != ob.mesh.edges.count then (
		print "MESH TOPO CHANGED"
		a.verts = ob.mesh.vertices.count
		a.faces = ob.mesh.faces.count
		a.edges = ob.mesh.edges.count
		a.data = data
		txt = "@SAVING:3DS@" + cname + "@" + ob.name + "~" + ob.position as string + "|" + ob.scale as string + "|" + ob.rotation as string + "*" + data
		setClipboardText( txt )
		dump_object( ob )
		sleep 0.01
		txt = "@LOAD:3DS@" + cname + "@" + ob.name + "~" + ob.position as string + "|" + ob.scale as string + "|" + ob.rotation as string + "*" + data
		setClipboardText( txt )
		sleep 0.09
	) else (

		if a.data != data do (
			print "MESH DEFORMED"
			a.data = data
			txt = "@UPDATE:STREAM@" + cname + "@" + ob.name + "~" + ob.position as string + "|" + ob.scale as string + "|" + ob.rotation as string + "*" + data
			setClipboardText( txt )
		)
	)
)


nec = NodeEventCallback mouseUp:true delay:1000 geometryChanged:on_geometry_changed
