// WebGL Pyppet Client
// Copyright Brett Hartshorn 2012-2013
// License: "New" BSD
/*
Notes:
	This error can happen if you assign the same shader to different meshes,
	or forget to computeTangents before assignment.
	 [..:ERROR:gles2_cmd_decoder.cc(4561)] glDrawXXX: attempt to access out of range vertices

*/

Array.prototype.insert = function (index, item) {
	this.splice(index, 0, item); // changes array inplace
};

Array.prototype.remove = function (index) {
	this.splice(index, 1); // changes array inplace
};

Array.prototype.copy = function (index) {
	return [].concat( this );
};


// http://wiki.ecmascript.org/doku.php?id=harmony%3astring_extras
if (typeof String.prototype.startsWith != 'function') {
  // see below for better implementation!
  String.prototype.startsWith = function (str){
    return this.indexOf(str) == 0;
  };
}


// http://stackoverflow.com/questions/728360/most-elegant-way-to-clone-a-javascript-object
function clone(obj) {
    // Handle the 3 simple types, and null or undefined
    if (null == obj || "object" != typeof obj) return obj;

    // Handle Date
    if (obj instanceof Date) {
        var copy = new Date();
        copy.setTime(obj.getTime());
        return copy;
    }

    // Handle Array
    if (obj instanceof Array) {
        var copy = [];
        for (var i = 0, len = obj.length; i < len; i++) {
            copy[i] = clone(obj[i]);
        }
        return copy;
    }

    // Handle Object
    if (obj instanceof Object) {
        var copy = {};
        for (var attr in obj) {
            if (obj.hasOwnProperty(attr)) copy[attr] = clone(obj[attr]);
        }
        return copy;
    }

    throw new Error("Unable to copy obj! Its type isn't supported.");
}






/////////////////////////////////////////////////////////
var Objects = {};	// name : Object3D
var MESHES = [];	// list for intersect checking - not a dict because LOD's share names

var container;
var camera, scene, renderer;
var spotLight, ambientLight;
var CONTROLLER;
var postprocessing = { enabled  : false }; // used by dof and godrays
var material_depth; // dof
var materialDepth; // god rays



function start_tween_if_needed( tween ) {
	if ( TWEEN.getAll().indexOf(tween) == -1 ) {
		tween.start();
	} //else {tween._startTime = Date.now();}
}


var UserAPI = {
	text_fudge_factor : 0.01,
	position_tweens : {},  // object : tween
	scale_tweens : {},
	rotation_tweens : {},
	camera_controllers : {},
	camera : null,
	objects : Objects,
	meshes : MESHES,
	mesh_cache : {},
	cubemaps : {
		REFLECT:{},
		REFRACT:{}
	},
	skybox_cubemap : null,

	start_object_stream : function() {
		ws.send_string(
			JSON.stringify({request : "start_object_stream"})
		);
		ws.flush();
	},
	on_draw_html_link : function( line, params ) {
		var p = clone( params );
		p.scale *= 0.5;
		p.bgcolor = 'blue';
		return p;
	},

	create_debug_axis : function(axisLength){
		//Shorten the vertex function
		function v(x,y,z){ return new THREE.Vector3(x,y,z);}

		//Create axis (point1, point2, colour)
		function createAxis(p1, p2, color){
			var line, lineGeometry = new THREE.Geometry(),
			lineMat = new THREE.LineBasicMaterial({color: color, lineWidth: 1});
			lineGeometry.vertices.push(p1, p2);
			line = new THREE.Line(lineGeometry, lineMat);
			return line;
		}
		var o = new THREE.Object3D();
		o.add(
			createAxis(v(-axisLength, 0, 0), v(axisLength, 0, 0), 0xFF0000)
		);
		o.add(
			createAxis(v(0, -axisLength, 0), v(0, axisLength, 0), 0x00FF00)
		);
		o.add(
			createAxis(v(0, 0, -axisLength), v(0, 0, axisLength), 0x0000FF)
		);
		return o;
	},

	get_cubemap : function(name, type) {
		if (name in UserAPI.cubemaps[type]) {
			return UserAPI.cubemaps[type][name];
		} else {
			return UserAPI.skybox_cubemap;
		}
	},

	create_cubemap : function(path, format) {
		var urls = [
			path + '/px' + format, path + '/nx' + format,
			path + '/py' + format, path + '/ny' + format,
			path + '/pz' + format, path + '/nz' + format
		];
		var n = path.split('/');
		n = n[ n.length-1 ];

		var mapping = new THREE.CubeReflectionMapping();
		var reflect = UserAPI.cubemaps.REFLECT[ n ] = THREE.ImageUtils.loadTextureCube(
			urls, 
			mapping
		);

		var mapping = new THREE.CubeReflectionMapping();
		var refract = UserAPI.cubemaps.REFRACT[ n ] = THREE.ImageUtils.loadTextureCube(
			urls, 
			mapping
		);

		return {reflection:reflect, refraction:refract};


	},
	create_skybox : function(path, format, size) {
		//var material = new THREE.MeshBasicMaterial( { color: 0xffffff, envMap: textureCube, refractionRatio: 0.95 } );
		if (size === undefined) { size = 100 }

		var textureCube = UserAPI.create_cubemap(path, format).reflection;
		UserAPI.skybox_cubemap = textureCube;

		var shader = THREE.ShaderLib[ "cube" ];
		var uniforms = THREE.UniformsUtils.clone( shader.uniforms );
		uniforms[ "tCube" ].value = textureCube;
		//uniforms[ "uOpacity" ].value = 0.1; // cube in three.js shaderlib is hardcoded to be vec3
		var material = new THREE.ShaderMaterial( {

			fragmentShader: shader.fragmentShader,
			vertexShader: shader.vertexShader,
			uniforms: uniforms,
			depthWrite: false,
			side: THREE.BackSide,
			transparent: true,
			//opacity:0.2, // note in three.js opacity on a shader is set with the uOpacity uniform.
			blending: THREE.AdditiveBlending
		});

		mesh = new THREE.Mesh( new THREE.CubeGeometry( size, size, size ), material );
		return {mesh:mesh, texture:textureCube};

	},

	on_update_properties : function(ob, pak) {
		var props = pak.properties;
		for (_ in pak.properties) {
			ob.custom_attributes[_] = pak.properties[_] 
		}
		if (props.visible !== undefined) {
			ob.visible = props.visible; // this has no affect on an Object3D without mesh

			for (var i=0; i<ob.children.length; i++) { 		// show/hide meshes
				var child = ob.children[ i ];
				child.visible = props.visible;
			}
		}

		if (props.selected) { 
			SELECTED = ob;
			//Input.object = ob;
			Input.set_object( ob );
		}
		if (props.disable_input && ob === Input.object) {
			//Input.object = null;
			Input.set_object( null );
		}

		if (props.title) {
			title_object(		// note label_object is smart enough to not rebuild the texture etc.
				undefined, //ob.meshes[0].geometry, // geom (needed to calc the bounds to fit the text)
				ob,			// parent
				props.title, // title (can be undefined)
				ob.custom_attributes.text_flip,  // special case to force flipped text
				ob.custom_attributes.text_scale
			); // TODO optimize this only update on change
		}

		if (props.label || props.heading) {
			// the client can force input into label body when object is selected.
			// the toplevel title is controlled by the server side

			var text = props.label; // can also be undefined
			if (ob === Input.object) { text=undefined; }

			label_object(		// note label_object is smart enough to not rebuild the texture etc.
				undefined, //ob.meshes[0].geometry, // geom (needed to calc the bounds to fit the text)
				ob,			// parent
				text, 		// multiline text body
				props.heading,  // title (can be undefined)
				ob.custom_attributes.text_flip,  // special case to force flipped text
				ob.custom_attributes.text_scale
			);
		}

	},

	rebuild_hierarchy : function( ob, hierarchy ) {
		//console.log('rebuilding hierarchy', ob, hierarchy);
		for (var i=0; i < hierarchy.length; i ++) {
			var id = hierarchy[ i ];
			var child = ob.dynamic_hierarchy[id];
			//if (!(id in ob.dynamic_hierarchy)) {
			if ( child === undefined || child === null) {
				if (id in UserAPI.objects) {
					child = UserAPI.objects[ id ];
					console.log('adding child->', child);
					ob.add( child );
					//ob.dynamic_hierarchy.push( id );
				} else { console.log('waiting for->'+id)}
				ob.dynamic_hierarchy[id] = child; // keep track of children added
			}
		}

	},
	// allow for custom tween logic //
	on_interpolate_position : function(name, tween, vector) {
		tween.to(
			vector,
			1000 // magic number (if this number is too high, tween.js can consume 100percent CPU)
		);
	},

	on_interpolate_scale : function(name, tween, vector) {
		tween.to(
			vector,
			1000 // magic number
		);
	},

	get_object_by_id : function(id) {
		return Objects['__'+id+'__'];
	},
	send_message : function( object ) {
		ws.send_string( JSON.stringify(object));
		ws.flush();
	},

	request_mesh : function(id, callback) {
		//UserAPI.objects[ id ] = null;
		ws.send_string(
			JSON.stringify({
				request:"mesh",
				id:id
			})
		);
		ws.flush();
	},
	create_buffer_geometry : function( pak ) {
		console.log('creating new buffer geometry');
		var triangles = pak.triangles.length / 3;

		var geometry = new THREE.BufferGeometry();
		geometry.attributes = {
			index: {
				itemSize: 1,
				array: new Uint16Array( triangles * 3 ),
				numItems: triangles * 3
			},
			position: {
				itemSize: 3,
				array: new Float32Array( triangles * 3 * 3 ),
				numItems: triangles * 3 * 3
			},
			normal: {
				itemSize: 3,
				array: new Float32Array( triangles * 3 * 3 ),
				numItems: triangles * 3 * 3
			}//,
			//color: {
			//	itemSize: 3,
			//	array: new Float32Array( triangles * 3 * 3 ),
			//	numItems: triangles * 3 * 3
			//}
		}

		for ( var i = 0; i < pak.triangles.length; i ++ ) {
			geometry.attributes.index.array[i] = pak.triangles[i];
		}
		for ( var i = 0; i < pak.vertices.length; i ++ ) {
			console.log(pak.vertices[i]);
			geometry.attributes.position.array[i] = pak.vertices[i];
		}
		for ( var i = 0; i < pak.normals.length; i ++ ) {
			geometry.attributes.normal.array[i] = pak.normals[i];
		}
		//for ( var i = 0; i < pak.color.length; i ++ ) {
		//	geometry.attributes.color.array[i] = pak.color[i];
		//}

		geometry.computeBoundingSphere();

		var material = new THREE.MeshBasicMaterial();
		var mesh = new THREE.Mesh( geometry, material );
		scene.add( mesh );

	},
	update_material : function( mesh, pak ) {
		var material = mesh.material;
		if (pak.color) {
			if (pak.color.length==4) {
				material.opacity = pak.color[3];
			}
			if (pak.color.length >=3) {
				material.color.r = pak.color[0];
				material.color.g = pak.color[1];
				material.color.b = pak.color[2];
			}
			if (pak.color.length == 1) { // special case to assign just alpha changes
				material.opacity = pak.color[0];					
			}

		}

	},


	set_material : function(mesh, config) {
		var mat;

		if (config.color) {
			var clr = new THREE.Color();
			clr.setRGB( config.color[0],config.color[1],config.color[2] );
			config.color = clr;
		}

		if (config.emissive) {
			var clr = new THREE.Color();
			clr.setRGB(
				config.color[0] * config.emissive,
				config.color[1] * config.emissive,
				config.color[2] * config.emissive 
			);
			config.emissive = clr;
		}

		if (config.ambient) {
			var clr = new THREE.Color();
			clr.setRGB(
				config.color[0] * config.ambient,
				config.color[1] * config.ambient,
				config.color[2] * config.ambient 
			);
			config.ambient = clr.getHex(); // note the above accept a Color, docs say they should all be hex
		}

		if (config.vertexColors) {
			config.vertexColors = THREE.VertexColors;  // THREE.FaceColors to use face.color
		}

		if (config.shading=='FLAT') {
			config.shading = THREE.FlatShading;
		}
		else if (config.shading=='SMOOTH') {
			config.shading = THREE.SmoothShading;
		}

		if (config.side=='SINGLE') {
			config.side = THREE.FrontSide;
		}
		else if (config.side=='DOUBLE') {
			if (! config.transparent) {
				config.side = THREE.DoubleSide;
			} else if (config.blending == 'ADD' || config.blending == 'SUB' || config.blending == 'MULT') {
				config.side = THREE.DoubleSide;
			}
		}

		if (config.blending == 'NORMAL') {
			config.blending = THREE.NormalBlending;
		}
		else if (config.blending == 'ADD') {
			config.blending = THREE.AdditiveBlending;
		}
		else if (config.blending == 'SUB') {
			config.blending = THREE.SubtractiveBlending;
		}
		else if (config.blending == 'MULT') {
			config.blending = THREE.MultiplyBlending;
		}
		else if (config.blending == 'ADD_ALPHA') {
			config.blending = THREE.AdditiveAlphaBlending;
		}

		if (config.envMap && config.refractionRatio) {
			config.envMap = UserAPI.get_cubemap( 
				config.envMap, 
				config.envmap_type 
			);
		}

		if (config.type=='FLAT') {
			mat = new THREE.MeshBasicMaterial( config );
		} else if (config.type=='LAMBERT') {
			mat = new THREE.MeshLambertMaterial( config );
		} else if (config.type=='PHONG') {
			//config.specular = 0xffffff;
			var clr = new THREE.Color();
			clr.setRGB( config.specular[0],config.specular[1],config.specular[2] )
			config.specular = clr;


			config.metal = true;
			mat = new THREE.MeshPhongMaterial( config );
		} else if (config.type=='DEPTH') {
			mat = new THREE.MeshDepthMaterial( config );
		} else if (config.type=='SHADER') {
			mat = null;
		}
		mat.type = config.type;
		mat.name = config.name;
		mesh.materials[ config.type ] = mat;
		mesh.material = mat;
		mesh.original_material = mat.clone();
		mesh.active_material = mat;
		return mat;
	},
	create_geometry : function(pak, name) {
		//console.log('creating new geometry');

		var geometry = new THREE.Geometry();

		for ( var i = 0; i < pak.vertices.length; i ++ ) {
			var x = pak.vertices[i][0];
			var y = pak.vertices[i][1];
			var z = pak.vertices[i][2];
			var vec = new THREE.Vector3( x,y,z );
			geometry.vertices.push(vec);
		}
		for ( var i = 0; i < pak.triangles.length; i ++ ) {
			var f = pak.triangles[i];
			var face = new THREE.Face3( f[0], f[1], f[2] );

			if (pak.colors) {
				for ( var j=0; j<3; j++) {
					var rgb = pak.colors[ f[j] ];
					var clr = new THREE.Color();
					clr.setRGB( rgb[0], rgb[1], rgb[2] );
					face.vertexColors.push( clr );

				}
			}
			geometry.faces.push( face );

		}
		for ( var i = 0; i < pak.quads.length; i ++ ) {
			var f = pak.quads[i];
			var face = new THREE.Face4( f[0], f[1], f[2], f[3] );
			if (pak.colors) {
				for ( var j=0; j<4; j++) {
					var rgb = pak.colors[ f[j] ];
					var clr = new THREE.Color();
					clr.setRGB( rgb[0], rgb[1], rgb[2] );
					face.vertexColors.push( clr );

				}
			}
			geometry.faces.push(face);
		}

		//geometry.mergeVertices(); //BAD?
		geometry.computeCentroids();
		geometry.computeFaceNormals(); // required for dynamic lights
		geometry.computeBoundingSphere();
		geometry.computeBoundingBox();
		geometry.computeVertexNormals(); // we do not send vertex normals, use "shading:THREE.FlatShading"

		if (pak.subdiv) {
			var subsurf = new THREE.SubdivisionModifier( pak.subdiv );
			if (pak.colors) {
				subsurf.useOldVertexColors = true;  // enable vertex colors
			}
			subsurf.modify( geometry );
		}


		var material = new THREE.MeshBasicMaterial({
			side:THREE.DoubleSide, wireframe:true,
			vertexColors: THREE.VertexColors
			//vertexColors: THREE.FaceColors
		});
		var mesh = new THREE.Mesh( geometry, material );
		mesh.name = name;
		mesh.mesh_id = pak.mesh_id;
		mesh.doubleSided = true;
		mesh.castShadow = true;
		mesh.receiveShadow = true;
		mesh.materials = {};
		mesh.active_material = material;

		UserAPI.meshes.push( mesh );
		UserAPI.mesh_cache[ pak.mesh_id ] = mesh;

		if (pak.lines.length) {
			var linewidth = 1.0;
			if (pak.linewidth) {
				linewidth = pak.linewidth;
			}
			var linegeom = new THREE.Geometry();
			var linemat = new THREE.LineBasicMaterial( { 
				color: 0xffffff, 
				opacity: 0.95, transparent: true,
				vertexColors: THREE.VertexColors,
				linewidth: linewidth // note mrdoob - this should have been "lineWidth"
			} );

			for ( var i = 0; i < pak.lines.length; i ++ ) {
				var aidx = pak.lines[i][0];
				var bidx = pak.lines[i][1];

				var x = pak.vertices[aidx][0];
				var y = pak.vertices[aidx][1];
				var z = pak.vertices[aidx][2];
				var vec = new THREE.Vector3( x,y,z );
				linegeom.vertices.push(vec);

				var x = pak.vertices[bidx][0];
				var y = pak.vertices[bidx][1];
				var z = pak.vertices[bidx][2];
				var vec = new THREE.Vector3( x,y,z );
				linegeom.vertices.push(vec);

				if (pak.colors) {
					var r = pak.colors[aidx][0];
					var g = pak.colors[aidx][1];
					var b = pak.colors[aidx][2];
					var clr = new THREE.Color();
					clr.setRGB(r,g,b);
					linegeom.colors.push(clr);

					var r = pak.colors[bidx][0];
					var g = pak.colors[bidx][1];
					var b = pak.colors[bidx][2];
					var clr = new THREE.Color();
					clr.setRGB(r,g,b);
					linegeom.colors.push(clr);

				}

			}

			var line = new THREE.Line( 
				linegeom, 
				linemat, 
				THREE.LinePieces
			);
			mesh.add( line );

		}
		if (pak.points) {

			var pgeom = new THREE.Geometry();

			for ( var i = 0; i < pak.points.length; i ++ ) {
				var idx = pak.points[i];
				var x = pak.vertices[idx][0];
				var y = pak.vertices[idx][1];
				var z = pak.vertices[idx][2];
				var vec = new THREE.Vector3( x,y,z );
				pgeom.vertices.push(vec);
			}

			var particles = new THREE.ParticleSystem(
				pgeom, 
				new THREE.ParticleBasicMaterial({
					color: 0xffffff, size: 1, opacity: 0.5, 
					transparent:true, blending: THREE.AdditiveBlending 
				})
			);

			mesh.add( particles );

		}
		return mesh;
	},

	create_object : function(name, position, rotation, scale, min, max) {
		var o = new THREE.Object3D();
		o.name = name;
		//o.useQuaternion = true;		// euler OK.?
		o.dynamic_hierarchy = {}; // not used anymore
		o.custom_attributes = {}; // used by websocket callbacks
		o.meshes = [];			// used to lazy load mesh data

		//if ( position != undefined ) {
			o.position.x = position[0];
			o.position.y = position[1];
			o.position.z = position[2];
		//}
		//if ( scale != undefined ) {
			o.scale.x = scale[0];
			o.scale.y = scale[1];
			o.scale.z = scale[2];
		//}
		//if ( rotation != undefined ) {

			o.rotation.x = rotation[0];
			o.rotation.y = rotation[1];
			o.rotation.z = rotation[2];

		//}
/*
			o.quaternion.w = rotation[0];
			o.quaternion.x = rotation[1];
			o.quaternion.y = rotation[2];
			o.quaternion.z = rotation[3];
*/

		if (min !== undefined) {
			o.min = new THREE.Vector3( min[0], min[1], min[2] );
		}
		if (max !== undefined) {
			o.max = new THREE.Vector3( max[0], max[1], max[2] );
		}

		UserAPI.objects[ name ] = o;
		return o;
	},

	create_lod : function (_mesh, position, rotation, scale, parent, model_config) {

		var lod = new THREE.LOD();

		_mesh.material = new THREE.MeshLambertMaterial({
			transparent: false,
			color: 0xffffff
		});

		lod.name = _mesh.name;
		lod.base_mesh = null;
		lod.useQuaternion = true;			// ensure Quaternion
		lod.has_progressive_textures = false;	// enabled from websocket stream
		lod.shader = null;
		lod.dirty_modifiers = true;
		lod.auto_subdivision = false;

		lod.multires = false;
		lod.has_displacement = false;
		lod.has_AO = false;	// TODO fix baking to hide LOD proxy

		if ( position != undefined ) {
			lod.position.x = position[0];
			lod.position.y = position[1];
			lod.position.z = position[2];
		}
		if ( scale != undefined ) {
			lod.scale.x = scale[0];
			lod.scale.y = scale[1];
			lod.scale.z = scale[2];
		}
		if ( rotation != undefined ) {
			lod.quaternion.w = rotation[0];
			lod.quaternion.x = rotation[1];
			lod.quaternion.y = rotation[2];
			lod.quaternion.z = rotation[3];
		}

		// custom attributes (for callbacks)
		lod.custom_attributes = {};
		lod.dynamic_hierarchy = {};
		lod._uid_ = parseInt( lod.name.replace('__','').replace('__','') );

		lod.do_mouse_up_callback = function () {
			lod.on_mouse_up_callback( lod.custom_attributes );
		};
		lod.do_input_callback = function (txt) {
			if (lod.on_input_callback) {
				lod.on_input_callback( lod.custom_attributes, txt );
			}
		}

		if (UserAPI.on_model_loaded) {
			UserAPI.on_model_loaded(
				lod, 
				_mesh, 
				model_config // extra user defined config
			);
		}

		lod.addLevel( _mesh, 0 );
		lod.updateMatrix();
		//mesh.matrixAutoUpdate = false;

		// add to scene //
		//Objects[ lod.name ] = lod;
		UserAPI.objects[ lod.name ] = lod;

		if (parent) {
			var pid = '__'+parent+'__';
			if (UserAPI.objects[pid]) {
				var mparent = UserAPI.objects[ pid ];
				console.log('mparent'+mparent);
				mparent.add( lod );
				mparent.dynamic_hierarchy[lod.name] = lod;

			}
			//console.log('mparent-name'+parent);
		} else {
			scene.add( lod );
		}


		return lod;

	}
};

var _colladas_pending = [];
var _current_collada_download = null;

function download_collada( name ) {
	Objects[ name ] = null;
	if (_current_collada_download) {
		_colladas_pending.push( name );
	} else {
		_download_collada( name );
	}

}

function _download_collada( name ) {
	_current_collada_download = name;

	var loader = new THREE.ColladaLoader();
	loader.options.convertUpAxis = true;
	//loader.options.centerGeometry = true; // hires has this on.
	loader.load(
		'/objects/'+name+'.dae', 
		on_collada_ready
	);

}



var PeerLights = [];
var Peers = {};

var DEBUG = false;
var USE_MODIFIERS = true;
var USE_SHADOWS = true;

var DISP_BIAS_MAGIC = 0.07;
var DISP_SCALE_MAGIC = 1.0;


var projector = new THREE.Projector();	// for picking
var mouse = { x: 0, y: 0 };				// for picking
function onDocumentMouseMove( event ) {
	event.preventDefault();
	mouse.x = ( event.clientX / window.innerWidth ) * 2 - 1;
	mouse.y = - ( event.clientY / window.innerHeight ) * 2 + 1;
}
document.addEventListener( 'mousemove', onDocumentMouseMove, false );


var INTERSECTED = null;				// for picking
var testing;

var SELECTED = null;

var WIRE_MATERIAL = new THREE.MeshLambertMaterial({ 
	color: 0x000000, 
	wireframe: true, 
	wireframeLinewidth:1, 
	polygonOffset:true, 
	polygonOffsetFactor:1 
});

var SCREEN_WIDTH = window.innerWidth;
var SCREEN_HEIGHT = window.innerHeight - 10;


//dancer = new Dancer();  // TODO FIX Dancer.js

var textureFlare0 = THREE.ImageUtils.loadTexture( "/textures/lensflare/lensflare0.png" );
var textureFlare2 = THREE.ImageUtils.loadTexture( "/textures/lensflare/lensflare2.png" );
var textureFlare3 = THREE.ImageUtils.loadTexture( "/textures/lensflare/lensflare3.png" );


var LIGHTS = {};
var METABALLS = {};
var CURVES = {};

var dbugmsg = null;

// note: keyup event charCode is invalid in firefox, the keypress event should work in all browsers.
var Input = {
	lines : [],
	cursor_x : 0,
	cursor_y : -1,
	object : null
}
Input.set_object = function(object) {
	Input.object = object;
	Input.clear();
}
Input.clear = function() {
	while (Input.lines.length) { Input.lines.pop() }
	Input.cursor_x = 0;
	Input.cursor_y = -1;
}

Input.insert_string = function(string) {
	var arr = string.split("")
	for (i=0; i<arr.length; i++) {
		var char = arr[ i ]
		Input.insert( char )
	}
}

Input.insert = function(char) {
	if (Input.object === null) {
		return;
	}

	if (char == '\n' || Input.lines.length==0) {
		Input.newline();
	}
	if (char != '\n') {
		console.log( Input.lines )
		console.log( Input.cursor_y )
		Input.lines[ Input.cursor_y ].insert(
			Input.cursor_x,
			char
		);
		Input.cursor_x += 1;
	}
}
Input.newline = function() {
	Input.lines.push( [] );
	Input.cursor_y += 1;
}
Input.backspace = function() {
	if (Input.cursor_x == 0) {
		Input.lines.remove( Input.cursor_y );
		Input.cursor_y -= 1;
		Input.cursor_x = Input.lines[ Input.cursor_y ].length - 1;

	} else {
		Input.cursor_x -= 1;
		Input.lines[Input.cursor_y].remove( Input.cursor_x );
		console.log( Input.lines[Input.cursor_y] );
	}
}

Input.move = function( direction ) {
	switch( direction ) {

		case "LEFT":
			if (Input.cursor_x >= 1) {
				Input.cursor_x -= 1;
			}
			break;

		case "RIGHT":
			if (Input.cursor_x < Input.lines[ Input.cursor_y ].length) {
				Input.cursor_x += 1;
			}
			break;

		case "UP":
			if (Input.cursor_y > 0) {
				Input.cursor_y -= 1;
				var len = Input.get_line().length;
				if (Input.cursor_x > len) {
					Input.cursor_x = len;
				}
			}
			break;

		case "DOWN":
			if (Input.cursor_y < Input.lines.length) {
				if (Input.cursor_y == Input.lines.length-1) {
					Input.newline();
				} else {
					Input.cursor_y += 1;
				}
				var len = Input.get_line().length;
				if (Input.cursor_x > len) {
					Input.cursor_x = len;
				}
			}


		default:
			break;
	}
}

Input.get_text = function() {
	var arr = [];
	for (var i=0; i<Input.lines.length; i++) {
		var line = Input.lines[i].join("");
		arr.push( line );
	}
	return arr.join("\n");
}
Input.get_line = function( index ) {
	if (index === undefined) {
		index = Input.cursor_y;
	}
	return Input.lines[ Input.cursor_y ].join("");
}


Input.get_text_with_cursor = function( cursor ) {
	if (cursor === undefined) {
		cursor = '|';
	}

	var arr = [];
	for (var i=0; i<Input.lines.length; i++) {
		var buff = Input.lines[i];
		if (i == Input.cursor_y) {
			buff = buff.copy();
			buff.insert( Input.cursor_x, cursor );
		}
		arr.push( buff.join("") );
	}
	return arr.join("\n");
}


//var _input_buffer = [];
var INPUT_OBJECT = null;
var _input_mesh = null; // deprecated

var SpinningObjects = [];

var SoundClips = {};
var Sounds = [];	// sounds need to be pushed here so they can be updated.

var Sound = function ( sources, radius, volume ) {
	var audio = document.createElement( 'audio' );
	for ( var i = 0; i < sources.length; i ++ ) {
		var source = document.createElement( 'source' );
		source.src = sources[ i ];
		audio.appendChild( source );

	}

	this.position = new THREE.Vector3();

	this.play = function () {
		audio.play();
	}

	this.update = function ( camera ) {
		var distance = this.position.distanceTo( camera.position );

		if ( distance <= radius ) {
			audio.volume = volume * ( 1 - distance / radius );
		} else {
			audio.volume = 0;
		}
	}
}
/////////////////////////////////////////////////////////////////




///////////////////////////////////////////////////////////
function on_mouse_down(event) {
	if (event.button==0) {	
		// PICKING //
		var vector = new THREE.Vector3( mouse.x, mouse.y, 1 );
		projector.unprojectVector( vector, camera );
		var ray = new THREE.Raycaster( camera.position, vector.sub( camera.position ).normalize() );

		// ray.intersectObjects only works on THREE.Particle and THREE.Mesh,
		// it will not traverse the children, that is why it fails on THREE.LOD.
		//var intersects = ray.intersectObjects( scene.children );
		var test = [];
		for (var i=0; i < UserAPI.meshes.length; i ++) {
			var mesh = UserAPI.meshes[ i ];
			if (mesh.name in UserAPI.objects && !mesh.material.wireframe) {
				var o = UserAPI.objects[mesh.name];
				if (o.clickable) {
					test.push( mesh );
				}
			}

		}
		var intersects = ray.intersectObjects( test );

		INTERSECTED = null;

		if ( intersects.length > 0 ) {
			for (var i=0; i < intersects.length; i ++) {
				var intersect = intersects[ i ];
				if (intersect.object.name && intersect.object.visible) {
					if ( INTERSECTED != intersect.object ) {
						if (UserAPI.on_model_click_pressed) {
							UserAPI.on_model_click_pressed( 
								UserAPI.objects[ intersect.object.name ],
								intersect.object, 
								intersect.distance
							);
						}
						console.log('distance'+intersect.distance);
						INTERSECTED = intersect.object;
						//INTERSECTED.currentHex = INTERSECTED.material.color.getHex();
						//INTERSECTED.material.color.setHex( 0xff0000 );

						break; //break out of for loop
					}
				}
			}
		} else { INTERSECTED = null; }
	}

}

function tween_position( o, name, pos ) {
	if ( name in UserAPI.position_tweens == false ) {
		var tween = new TWEEN.Tween(o.position);
		var vec = new THREE.Vector3(pos[0], pos[1], pos[2]);
		UserAPI.position_tweens[ name ] = {'vector':vec, 'tween':tween};
		tween.to( vec, 500 );
		tween.start();

	} else {
		var tween = UserAPI.position_tweens[ name ].tween;
		var vector = UserAPI.position_tweens[ name ].vector;
		vector.set( pos[0], pos[1], pos[2] );
		//UserAPI.on_interpolate_position( name, tween, vector );
		start_tween_if_needed( tween );
	}
}

function tween_scale( o, name, scl ) {
	if ( name in UserAPI.scale_tweens == false ) {
		var tween = new TWEEN.Tween(o.scale);

		tween.onUpdate(  // automatically hide something if its scale becomes 'small'
			function () { // this is an issue if the mesh children are still loading.. loading needs to check if o.visible
				var thresh = 0.01;
				if (this.x <= thresh && this.y <= thresh && this.z <= thresh ) {
					if (o.visible) {
						o.visible = false;
						for (var i=0; i<o.children.length; i++) {
							o.children[ i ].visible = false;
						}
					}
				} else if (o.visible === false) {
					o.visible = true;
					for (var i=0; i<o.children.length; i++) {
						o.children[ i ].visible = true;
					}
				}
			}

		);

		var vec = new THREE.Vector3(scl[0], scl[1], scl[2]);
		UserAPI.scale_tweens[ name ] = {'vector':vec, 'tween':tween};
		tween.to( vec, 500 );
		tween.start();

	} else {
		var tween = UserAPI.scale_tweens[ name ].tween;
		var vector = UserAPI.scale_tweens[ name ].vector;
		vector.set( scl[0], scl[1], scl[2] );
		//UserAPI.on_interpolate_scale( name, tween, vector );
		start_tween_if_needed( tween );
	}
}

function on_mouse_up( event ) {
	if ( INTERSECTED ) {
		var a = UserAPI.objects[ INTERSECTED.name ];
		Input.clear();

		if (a.custom_attributes.on_mouse_up_tween) {
			// kick off animation before sending message to server 
			if (a.custom_attributes.on_mouse_up_tween.scale) {
				tween_scale(
					a, 
					a.name, 
					a.custom_attributes.on_mouse_up_tween.scale
				);
			}

			if (a.custom_attributes.on_mouse_up_tween.position) {
				tween_position(
					a, 
					a.name, 
					a.custom_attributes.on_mouse_up_tween.position
				);
			}

		}

		if (a.on_mouse_up_callback) {
			a.on_mouse_up_callback( a.custom_attributes );
		}

		if (UserAPI.on_model_click_released) {
			UserAPI.on_model_click_released(
				a, //lod
				INTERSECTED
			)
		}
		INTERSECTED = null;
	}
}

function on_paste( evt ) {
	var data = evt.clipboardData.getData('text/plain');
	console.log(data);
	if (Input.object) {
		Input.insert_string( data );
	}

}
window.addEventListener( 'paste', on_paste, false );


// note: using both on_keydown and on_keypress to catch all events
function on_keydown ( evt ) {

	if (evt.ctrlKey) {
		//console.log(evt.keyCode); // 67 is C, 86 is V
		return;
	}

	var update = false;
	switch( evt.keyCode ) {
		case 38: // up
			Input.move( "UP" );
			update = true;
			break;

		case 37: // left
			Input.move( "LEFT" );
			update = true;
			break;

		case 40: // down
			Input.move( "DOWN" );
			update = true;
			break;

		case 39: // right
			Input.move( "RIGHT" );
			update = true;
			break;

		case 9: //tab
			Input.insert( '	' );
			//_input_buffer.push(' ');
			update=true;
			break;

		case 8: //backspace
			event.preventDefault(); // this fixes backspace on windows/osx?
			//_input_buffer.pop();
			Input.backspace();
			update=true; break;

		case 27: 		//esc
			//while (_input_buffer.length) { _input_buffer.pop() }
			Input.clear();
			update=true;
			break;
	}
	if (update && Input.object) {

		label_object(
			undefined, //INPUT_OBJECT.meshes[0].geometry,
			Input.object,
			Input.get_text_with_cursor(), // text
			undefined, // title
			undefined,  // special case to force flipped text
			Input.object.custom_attributes.text_scale
		);

	}

}
window.addEventListener( 'keydown', on_keydown, false );


function on_keypress( evt ) { 
	//console.log( String.fromCharCode(evt.charCode) );
	//console.log( evt.charCode );
	//console.log( evt.keyCode );
	//event.preventDefault(); // this fixes backspace on windows/osx?



	switch( evt.keyCode ) {
		case 32: // space
			Input.insert(' ');
			break;
		case 13: // enter - can trigger input and callbacks

			Input.insert('\n');

			if (UserAPI.on_enter_key) {
				UserAPI.on_enter_key( Input.get_text() );
			}
			if (Input.object) {
				console.log('doing input callback');

				if (Input.object.on_input_callback) {
					Input.object.on_input_callback(
						Input.object.custom_attributes, 
						Input.get_text() 
					);
				}
			}
			break;
		default:
			var string = String.fromCharCode(evt.charCode);
			if (string) {
				Input.insert( string );
				ws.send_string( string );
			}
	}

	if (Input.object) {

		label_object(
			undefined, //INPUT_OBJECT.meshes[0].geometry,
			Input.object,
			Input.get_text_with_cursor(), // text
			undefined, // title
			undefined,  // special case to force flipped text
			Input.object.custom_attributes.text_scale
		); // TODO optimize this only update on change

	}

}
window.addEventListener( 'keypress', on_keypress, false );

function create_text( line, parent, params ) {

	if (params.offset === undefined) { params.offset=-1.5; }
	if (params.scale === undefined) { params.scale=0.01; }
	if (params.resolution === undefined) { params.resolution=100; }
	if (params.color === undefined) { params.color="white"; }
	if (params.transparent === undefined) { params.transparent=true; }
	if (params.x === undefined) { params.x=0; }
	if (params.y === undefined) { params.y=0; }
	if (params.z === undefined) { params.z=0; }

	if ( line.startsWith('http://') === true ) {
		params = UserAPI.on_draw_html_link( line, params );
	}

	var mesh = createLabel(
		line, 
		params.x, params.y+params.offset, params.z,  // location, x,y,z
		params.resolution,
		params.color, // font color
		params.transparent,
		params.alignment,
		params.bgcolor
	);

	if (params.flip) {
		mesh.scale.x = -params.scale;
		mesh.scale.y = -params.scale;
		mesh.scale.z = -params.scale;
	} else {
		mesh.scale.x = params.scale;
		mesh.scale.y = params.scale;
		mesh.scale.z = params.scale;		
	}

	mesh.normal_width = mesh.width * params.scale;
	mesh.normal_height = mesh.height * params.scale;

	mesh.rotation.x = Math.PI/2.0;
	mesh.rotation.y = Math.PI;

	if (params.alignment == 'left') {
		//mesh.position.x = -((mesh.width/2) * params.scale); // old
		mesh.position.x = -parent.min.x;

	}

	parent.add( mesh );
	return mesh;
}

function create_multiline_text( text, title, parent, params ) {

	if (params.scale==undefined) { params.scale=0.0035; }
	if (params.spacing==undefined) { params.spacing = 0.3; }


	var lines = [];

	if (title != undefined) {

		if (params.title_resolution==undefined) { params.resolution=100; }  // default

		var _lines = title.split('\n');
		for (var i=0; i<_lines.length; i ++) {
			var line = _lines[ i ];
			var mesh = create_text( 
				line, 
				parent, 
				params
			);
			if (lines.length) {
				mesh.position.z = -(params.spacing+0.15)*i;
				//mesh.position.z -= lines[lines.length-1].height*scale;
			}
			lines.push( mesh );
		}

	}

	if (params.text_resolution==undefined) { params.resolution=75; } // default

	if (text != undefined) {
		var _lines = text.split('\n');


		for (var i=0; i<_lines.length; i ++) {
			if (-params.spacing*i <= parent.min.z) {
				continue;
			}
			var line = _lines[ i ];
			var mesh = create_text( 
				line, 
				parent, 
				params
			);
			if (lines.length) {
				mesh.position.z = -params.spacing*i;
				//mesh.position.z -= lines[lines.length-1].height*scale;
				if (mesh.position.z <= parent.min.z) {
					console.log('WARN text below parent');
					console.log( mesh.position );
					console.log( parent.min )
				}
			}
			lines.push( mesh );
		}
	}
	return lines;
}


/////////////// label any object ///////////////
function title_object(geometry, parent, title, flip, scale ) {

	if (flip === undefined) { flip = false; }
	if (scale === undefined) { scale = 0.0035; }

	if (title != undefined && title != parent._label_title) {
		parent._label_title = title;

		// clear heading and label //
		if (parent._title_objects != undefined) {
			for (var i=0; i<parent._title_objects.length; i++) {
				parent.remove( parent._title_objects[i] );
			}
		}
		if (parent._label_objects != undefined) {
			for (var i=0; i<parent._label_objects.length; i++) {
				parent.remove( parent._label_objects[i] );
			}
		}

		var lines = create_multiline_text(
			undefined, 
			title,
			parent,
			{
				offset : parent.max.y + UserAPI.text_fudge_factor,
				alignment : "center",
				flip : flip,
				scale : scale
			}
		);
		parent._title_objects = lines;
		//lines[0].position.z = -(bb.max.z - bb.min.z) / 2.0;
		//lines[0].position.x -= bb.min.x; // for left alignment
		var width = lines[ lines.length-1 ].normal_width;
		console.log('text-width', width);

		if (parent.visible === false) { // hide text if parent is also hidden
			for (var i=0; i<lines.length; i++) {
				lines[i].visible=false;
			}
		}

	}

}

function label_object(geometry, parent, txt, title, flip, scale ) {
	if (flip === undefined) { flip = false; }
	if (scale === undefined) { scale = 0.0035; }
	var spacing = (1.0 / scale) * scale * 0.15;


	if (title != undefined && title != parent._label_title) {
		parent._label_title = title;

		if (parent._title_objects != undefined) {
			for (var i=0; i<parent._title_objects.length; i++) {
				parent.remove( parent._title_objects[i] );
			}
		}
		var lines = create_multiline_text(
			undefined, 
			title,
			parent,
			{
				offset:parent.max.y + UserAPI.text_fudge_factor,
				alignment:"center",
				flip:flip,
				scale:scale
			}
		);
		parent._title_objects = lines;
		lines[0].position.z = parent.max.z - 0.2;

		if (parent.visible === false) { // hide text if parent is also hidden
			for (var i=0; i<lines.length; i++) {
				lines[i].visible=false;
			}
		}

	}

	//////////////////////////////////////////////////////

	if (txt != undefined && txt != parent._label_text) {
		parent._label_text = txt;

		if (parent._label_objects != undefined) {
			for (var i=0; i<parent._label_objects.length; i++) {
				parent.remove( parent._label_objects[i] );
			}
		}


		// use Input cursor to scroll text //
		var fit = ~~(Math.abs(parent.min.z) / spacing); //http://stackoverflow.com/questions/596467/how-do-i-convert-a-float-to-an-int-in-javascript
		var lines = txt.split('\n');
		if (Input.object === parent && Input.cursor_y > fit) {
			lines.splice(0, Input.cursor_y - fit );
		}

		var lines = create_multiline_text(
			lines.join('\n'), 
			undefined,
			parent,
			{
				offset : parent.max.y + UserAPI.text_fudge_factor,
				alignment : "left",
				flip : flip,
				scale : scale,
				spacing: spacing
			}
		);
		parent._label_objects = lines;

		if (parent.visible === false) { // hide text if parent is also hidden
			for (var i=0; i<lines.length; i++) {
				lines[i].visible=false;
			}
		}
	}
}



///////////////////// createLabel by ekeneijeoma - https://gist.github.com/ekeneijeoma/1186920
function createLabel(text, x, y, z, size, color, transparent, alignment, backGroundColor, backgroundMargin) {
	if(!backgroundMargin)
		backgroundMargin = 50;
	if (alignment==undefined) { alignment="left"; }

	var canvas = document.createElement("canvas");

	var context = canvas.getContext("2d");
	context.font = size + "pt Arial";

	var textWidth = context.measureText(text).width;

	canvas.width = textWidth + backgroundMargin;
	canvas.height = size + backgroundMargin;
	context = canvas.getContext("2d");
	context.font = size + "pt Arial";


	if(backGroundColor) {
		context.fillStyle = backGroundColor;
		context.fillRect(
			canvas.width / 2 - textWidth / 2 - backgroundMargin / 2, 
			canvas.height / 2 - size / 2 - +backgroundMargin / 2, 
			textWidth + backgroundMargin, size + backgroundMargin);
	}

	context.textAlign = alignment;
	context.textBaseline = "middle";
	context.fillStyle = color;

	var geom = new THREE.PlaneGeometry(canvas.width, canvas.height);

	if (alignment=="left") {
		context.fillText(text, backgroundMargin/2, canvas.height/2);
		for (var i=0; i<geom.vertices.length; i++) {
			geom.vertices[i].x += canvas.width/2;
		}
	} else {
		context.fillText(text, canvas.width/2, canvas.height/2);
	}

	// context.strokeStyle = "black";
	// context.strokeRect(0, 0, canvas.width, canvas.height);
	var texture = new THREE.Texture(canvas);
	//texture.flipY = false;
	//texture.flipX = false;
	texture.needsUpdate = true;

	var material = new THREE.MeshBasicMaterial({
		map : texture,
		transparent : transparent,
	});

	var mesh = new THREE.Mesh(geom, material);
	mesh.overdraw = true; // what is this option for?
	mesh.doubleSided = true;
	mesh.position.x = x;
	mesh.position.y = y;
	mesh.position.z = z;
	mesh.scale.y = -1.0;
	mesh.scale.z = -1.0;

	mesh.width = canvas.width;
	mesh.height = canvas.height;

	return mesh;
}


////////////////////// old stuff ///////////////////////////
function generate_extruded_splines( parent, ob ) {

	for (var i=0; i < ob.splines.length; i ++) {
		var spline = ob.splines[ i ];
		var extrude_path;
		var a = [];
		for (var j=0; j<spline.points.length; j ++) {
			var vec = spline.points[ j ];
			a.push( new THREE.Vector3(vec[0], vec[2], -vec[1]) )
		}
		if (spline.closed) {
			extrude_path = new THREE.ClosedSplineCurve3( a );
		} else {
			extrude_path = new THREE.SplineCurve3( a );
		}

		var geometry = new THREE.TubeGeometry(
			extrude_path,
			spline.segments_u, 	// using curve.resolution_u * spline.resolution_u
			ob.radius+0.001, 		// using curve.bevel_depth
			ob.segments_v+3, 	// using curve.bevel_resolution
			spline.closed, 
			false
		);

		//var material = new THREE.MeshLambertMaterial( {color: 0xff00ff} );
		var material = new THREE.MeshPhongMaterial( 
				{ color: 0x000000, specular: 0x888888, ambient: 0x000000, shininess: 250, perPixel: true }
		);

		var wire_material = new THREE.MeshBasicMaterial({
		    color: 0x000000,
		    opacity: 0.5,
		    wireframe: true,
		    transparent: true
		});

		// 3d shape
		//var tubeMesh = THREE.SceneUtils.createMultiMaterialObject(
		//	geometry, 
		//	[ material, wire_material ]
		//);
		var tubeMesh = new THREE.Mesh( geometry, material );
		tubeMesh.shader = material;

		if (USE_SHADOWS) {
			tubeMesh.castShadow = true;
			tubeMesh.receiveShadow = true;
		}
		parent.add( tubeMesh );
	}
}


function vec3_to_bytes(x,y,z) {
	var buffer = new ArrayBuffer(12);
	//var intView = new Int32Array(buffer);
	var bytesView = new Uint8Array(buffer);
	var floatView = new Float32Array(buffer);
	floatView[0] = x;
	floatView[1] = y;
	floatView[2] = z;
	//bits of the 32 bit float
	//return intView[0].toString(2) + intView[1].toString(2) + intView[2].toString(2);
	return Array.apply([], bytesView);
}
function int32_to_bytes(x) {
	var buffer = new ArrayBuffer(4);
	//var intView = new Int32Array(buffer);
	var bytesView = new Uint8Array(buffer);
	var intView = new Uint32Array(buffer);
	intView[0] = x;
	return Array.apply([], bytesView);
}


var PreviousMessage = null;





function on_binary_message( bytes ) {
	var buffer = new ArrayBuffer(2);
	//var intView = new Int32Array(buffer);
	var view = new Int16Array( buffer );
	var bytesView = new Uint8Array(buffer);
	//var floatView = new Float32Array(buffer);
	bytesView[0] = bytes[0];
	bytesView[1] = bytes[1];
	//bytesView[2] = bytes[2];
	//bytesView[3] = bytes[3];
	//var arr = Array.apply([], floatView);
	//camera.position.x = floatView[0];
	//camera.position.x = view[0] * (1.0/32768.0);

}

var _msg;
function on_json_message( data ) {
	var msg = JSON.parse( data );
	_msg = msg;
	if (msg.eval) {
		eval( msg.eval );
	}
	if (!UserAPI.initialized) {return}

	// ensure that all objects have been created //
	for (var name in msg['meshes']) {
		var pak = msg['meshes'][ name ];
		if (!(name in Objects)) {
			var o = UserAPI.create_object(
				name,
				pak.pos,
				pak.rot,
				pak.scl,
				pak.min,
				pak.max
			);
			if (pak.parent === undefined) {
				scene.add( o );
			}
			// request mesh if its not an empty //
			if (pak.empty) {
				o.add( UserAPI.create_debug_axis(0.25) );
			} else if (pak.mesh_id in UserAPI.mesh_cache) {
				console.log('pulling from cache',pak.mesh_id);
				var _mesh = UserAPI.mesh_cache[pak.mesh_id].clone();
				_mesh.material = UserAPI.mesh_cache[pak.mesh_id].original_material.clone();
				_mesh.clickable = UserAPI.mesh_cache[pak.mesh_id];
				_mesh.name = o.name;
				UserAPI.meshes.push( _mesh );
				o.add( _mesh );
				o.meshes.push( _mesh );
			} else {
				o.add( UserAPI.create_debug_axis(0.1) );
				UserAPI.request_mesh( name );				
			}
		}
	}

	for (var name in msg['meshes']) {
		var pak = msg['meshes'][ name ];
		var props = pak.properties; //ob
		var o = UserAPI.objects[ name ];

		if (o.parent === undefined && pak.parent !== undefined) {
			if (pak.parent == -1) {
				UserAPI.camera.add( o );
			} else {
				var pid = '__'+pak.parent+'__';
				if (pid in UserAPI.objects) {
					//console.log( 'ADDING-> '+pak.parent );
					UserAPI.objects[ pid ].add( o );
				} else {
					console.log( 'waiting for parent: '+pak.parent );
				}
			}

		}

		if (pak.geometry) { // request_mesh response
			var mesh = UserAPI.create_geometry( pak.geometry, name ); // TODO check model_config
			UserAPI.objects[ name ].add( mesh );
			UserAPI.objects[ name ].meshes.push( mesh );
		}

		if (pak.properties) {
			UserAPI.on_update_properties( o, pak );
			// api_gen.py sets this custom attribute
			o.clickable = o.custom_attributes.clickable;

		}

		if (pak.pos) {
			/*
			m.position.x = pak.pos[0];
			m.position.y = pak.pos[1];
			m.position.z = pak.pos[2];
			*/
			tween_position( o, name, pak.pos );
		}

		if (pak.scl) {
			//m.scale.x = pak.scl[0];
			//m.scale.y = pak.scl[1];
			//m.scale.z = pak.scl[2];				
			tween_scale( o, name, pak.scl );
		}

		if (pak.rot) {
			/*
			o.quaternion.w = pak.quat[0];
			o.quaternion.x = pak.quat[1];
			o.quaternion.y = pak.quat[2];
			o.quaternion.z = pak.quat[3];
			*/

			//o.rotation.x = pak.rot[0];
			//o.rotation.y = pak.rot[1];
			//o.rotation.z = pak.rot[2];
			//o.rotation.setEulerFromQuaternion( pak.quat );

			if ( name in UserAPI.rotation_tweens == false ) {
				var tween = new TWEEN.Tween(o.rotation);
				var vec = new THREE.Vector3(pak.rot[0], pak.rot[1], pak.rot[2]);
				UserAPI.rotation_tweens[ name ] = {'vector':vec, 'tween':tween};
				tween.to( vec, 500 );
				tween.start();

			} else {
				var tween = UserAPI.rotation_tweens[ name ].tween;
				var vector = UserAPI.rotation_tweens[ name ].vector;
				vector.set( pak.rot[0], pak.rot[1], pak.rot[2] );
				//UserAPI.on_interpolate_scale( name, tween, vector );
				//tween.start();
				start_tween_if_needed( tween );

			}

		}


		if (pak.on_click) {
			o.on_mouse_up_callback = _callbacks_[ pak.on_click ];
		}

		if (pak.on_input) {
			o.on_input_callback = _callbacks_[ pak.on_input ];
		}

		if (pak.eval) {
			//console.log( pak.eval );
			eval( pak.eval );
		}

		if (pak.active_material) {

			if (pak.active_material.type != o.meshes[0].material.type) {
				UserAPI.set_material( o.meshes[0], pak.active_material );
			} else {
				UserAPI.update_material( o.meshes[0], pak.active_material );
			}
		}

		if (pak.color && o.meshes.length > 0) { // special case for color //
			UserAPI.update_material( o.meshes[0], {color:pak.color} );
		}


	}	// end meshes

	if (UserAPI.on_json_message) {
		UserAPI.on_json_message( msg );
	}

}


function on_json_message_old( data ) {
	var msg = JSON.parse( data );
	dbugmsg = msg;

	for (var name in msg['texts']) {
		if ( name in TEXTS == false ) {
			console.log('>> new text');
			TEXTS[ name ] = new THREE.Object3D();
			scene.add( TEXTS[name] );
			TEXTS[name].useQuaternion = true;
		}
		var ob = msg['texts'][name];
		var parent = TEXTS[ name ];
		while ( parent.children.length ) parent.remove( parent.children[0] );


		var text = ob.text,
			height = 20,
			size = 70,
			hover = 30,

			curveSegments = 4,

			bevelThickness = 2,
			bevelSize = 1.5,
			bevelSegments = 3,
			bevelEnabled = true,

			font = "optimer", // helvetiker, optimer, gentilis, droid sans, droid serif
			weight = "bold", // normal bold
			style = "normal"; // normal italic


		var textGeo = new THREE.TextGeometry( text, {

			size: size,
			height: height,
			curveSegments: curveSegments,

			font: font,
			weight: weight,
			style: style,

			bevelThickness: bevelThickness,
			bevelSize: bevelSize,
			bevelEnabled: bevelEnabled,

			material: 0,
			extrudeMaterial: 1

		});


		var wire_material = new THREE.MeshBasicMaterial({
		    color: 0x000000,
		    opacity: 0.5,
		    wireframe: true
		});

		var mesh = new THREE.Mesh( textGeo, wire_material );
		parent.add( mesh );

		parent.position.x = ob.pos[0];
		parent.position.y = ob.pos[1];
		parent.position.z = ob.pos[2];

		parent.scale.x = ob.scl[0];
		parent.scale.y = ob.scl[1];
		parent.scale.z = ob.scl[2];
	}

	for (var name in msg['curves']) {
		if ( name in CURVES == false ) {
			console.log('>> new curve');
			CURVES[ name ] = new THREE.Object3D();
			scene.add( CURVES[name] );
			CURVES[name].useQuaternion = true;
		}
		var parent = CURVES[ name ];
		var ob = msg['curves'][name];

		while ( parent.children.length ) parent.remove( parent.children[0] );

		generate_extruded_splines(
			parent,
			ob
		);

		parent.position.x = ob.pos[0];
		parent.position.y = ob.pos[1];
		parent.position.z = ob.pos[2];

		parent.scale.x = ob.scl[0];
		parent.scale.y = ob.scl[1];
		parent.scale.z = ob.scl[2];

		//parent.quaternion.w = ob.rot[0];	// TODO swap points server side and enable this
		//parent.quaternion.x = ob.rot[1];
		//parent.quaternion.y = ob.rot[2];
		//parent.quaternion.z = ob.rot[3];

		for (var i=0; i<parent.children.length; i++) {
			var child = parent.children[ i ];
			var spline = ob.splines[ i ];
			child.shader.color.r = spline.color[0];
			child.shader.color.g = spline.color[1];
			child.shader.color.b = spline.color[2];

		}

	}

	for (var name in msg['metas']) {
		if ( name in METABALLS == false ) {
			console.log('>> new metaball');
			var mat = new THREE.MeshPhongMaterial( 
				{ color: 0x000000, specular: 0x888888, ambient: 0x000000, shininess: 250, perPixel: true }
			);
			var resolution = 32;
			var meta = new THREE.MarchingCubes( resolution, mat );

			if (USE_SHADOWS) {
				meta.castShadow = true;
				meta.receiveShadow = true;
			}

			meta.scale.set(		// actually no need to stream this since its fixed for now
				msg['metas'][name]['scl'][0],
				msg['metas'][name]['scl'][2],
				msg['metas'][name]['scl'][1]
			);

			scene.add( meta );
			METABALLS[ name ] = meta;
		}
		var meta = METABALLS[ name ];
		var ob = msg['metas'][name];
		meta.material.color.r = ob.color[0];
		meta.material.color.g = ob.color[1];
		meta.material.color.b = ob.color[2];

		meta.reset();

		for (var i=0; i < ob['elements'].length; i ++) {
			var ball = ob['elements'][ i ];
			// convert radius to strength and subtract
			meta.addBall(
				ball.x+0.5, ball.z+0.5, -ball.y+0.5,
				0.01+ball.radius, 100
			);
		}
	}

	for (var name in msg['lights']) {
		var light;
		var ob = msg['lights'][ name ];

		if ( name in LIGHTS == false ) {
			console.log('>> new light');
			// note when adding new lights, old materials need to be reloaded

			LIGHTS[ name ] = light = new THREE.PointLight( 0xffffff );
			scene.add( light );

			//var flareColor = new THREE.Color( 0xffffff );
			//flareColor.copy( light.color );
			//THREE.ColorUtils.adjustHSV( flareColor, 0, -0.5, 0.5 );

			var lensFlare = new THREE.LensFlare( 
				textureFlare0, 
				700, 		// size in pixels (-1 use texture width)
				0.0, 		// distance (0-1) from light source (0=at light source)
				THREE.AdditiveBlending, 
				light.color
			);

			lensFlare.add( textureFlare2, 512, 0.0, THREE.AdditiveBlending );
			lensFlare.add( textureFlare2, 512, 0.0, THREE.AdditiveBlending );
			lensFlare.add( textureFlare2, 512, 0.0, THREE.AdditiveBlending );

			lensFlare.add( textureFlare3, 60, 0.6, THREE.AdditiveBlending );
			lensFlare.add( textureFlare3, 70, 0.7, THREE.AdditiveBlending );
			lensFlare.add( textureFlare3, 120, 0.9, THREE.AdditiveBlending );
			lensFlare.add( textureFlare3, 70, 1.0, THREE.AdditiveBlending );

			//lensFlare.customUpdateCallback = lensFlareUpdateCallback;
			lensFlare.position = light.position;
			light.flare = lensFlare;
			scene.add( lensFlare );


		}
		light = LIGHTS[ name ];
		light.color.r = ob.color[0];
		light.color.g = ob.color[1];
		light.color.b = ob.color[2];
		light.distance = ob.dist;
		light.intensity = ob.energy;

		light.position.x = ob.pos[0];
		light.position.y = ob.pos[1];
		light.position.z = ob.pos[2];

		for (var i=0; i < light.flare.lensFlares.length; i ++) {
			var flare = light.flare.lensFlares[ i ];
			flare.scale = ob.scale;
		}

	}

	for (var name in msg['meshes']) {
		var ob = msg['meshes'][ name ];
		var raw_name = name;

		if (name in Objects && Objects[name]) {
			m = Objects[ name ];
			if (ob.selected) { SELECTED = m; }

			m.has_progressive_textures = ob.ptex;
			if (m.shader) m.shader.uniforms[ "uNormalScale" ].value = ob.norm;

			m.position.x = ob.pos[0];
			m.position.y = ob.pos[1];
			m.position.z = ob.pos[2];

			m.scale.x = ob.scl[0];
			m.scale.y = ob.scl[1];
			m.scale.z = ob.scl[2];

			m.quaternion.w = ob.rot[0];
			m.quaternion.x = ob.rot[1];
			m.quaternion.y = ob.rot[2];
			m.quaternion.z = ob.rot[3];

			m.custom_attributes = ob.custom_attributes;
			if (ob.on_click) {
				m.on_mouse_up_callback = _callbacks_[ ob.on_click ];
			}
			//m.on_mouse_up_callback = _callbacks_[ "0" ];


			if (USE_MODIFIERS && m.base_mesh) {
				m.auto_subdivision = ob.auto_subdiv;

				if (INTERSECTED == null || name != INTERSECTED.name) {
					for (var i=0; i<m.children.length; i++) {
						m.children[ i ].material.color.setRGB(
							ob.color[0],
							ob.color[1],
							ob.color[2]
						);
					}
				}
				m.shader.uniforms[ "uShininess" ].value = ob.spec;
				if (m.multires) {
					m.shader.uniforms[ "uDisplacementBias" ].value = ob.disp_bias-DISP_BIAS_MAGIC;
					m.shader.uniforms[ "uDisplacementScale" ].value = ob.disp+DISP_SCALE_MAGIC;
				}
			}

			if (USE_MODIFIERS && m.base_mesh) {
				if (m.subsurf != ob.subsurf) {
					m.dirty_modifiers = true;
					m.subsurf = ob.subsurf;
				}

				if (ob.verts) {
					if (m.subsurf) m.dirty_modifiers = true;	// TODO make compatible with: usersubsurf+autosubsurf ?
					camera.position.x = 1.95;

					var vidx=0;
					for (var i=0; i <= ob.verts.length-3; i += 3) {
						var v = m.base_mesh.geometry_base.vertices[ vidx ];
						v.x = ob.verts[ i ];
						v.y = ob.verts[ i+2 ];
						v.z = -ob.verts[ i+1 ];
						vidx++;
					}
					m.base_mesh.geometry_base.computeCentroids();
					//m.geometry_base.computeFaceNormals();
					//m.geometry_base.computeVertexNormals();
				}
			}

			if (ob.reload_textures) {
				reload_progressive_textures( m );
			}

		}
		else if (name in Objects == false) {
			console.log( '>> loading new collada' );
			Objects[ name ] = null;
			var loader = new THREE.ColladaLoader();
			loader.options.convertUpAxis = true;
			//loader.options.centerGeometry = true;
			loader.load(
				'/objects/'+raw_name+'.dae', 
				on_collada_ready
			);

		}

	}	// end meshes

	///////////////////////////////////////////////////
	if (DEBUG==true) { return; }
	///////////////////////////////////////////////////

	if (msg.camera.rand) {
		if (CONTROLLER.MODE != 'RANDOM') { CONTROLLER.set_mode('RANDOM'); }
		CONTROLLER.randomize = true;
	}
	/*
	postprocessing.bokeh_uniforms[ "focus" ].value = msg.camera.focus;
	postprocessing.bokeh_uniforms[ "aperture" ].value = msg.camera.aperture;
	postprocessing.bokeh_uniforms[ "maxblur" ].value = msg.camera.maxblur;
	*/

	for (var name in msg['FX']) {
		var fx = FX[ name ];
		fx.enabled = msg['FX'][name][0];
		var uniforms = msg['FX'][name][1];
		if (fx.uniforms) {
			for (var n in uniforms) { fx.uniforms[ n ].value = uniforms[ n ]; }
		}
		else {	// BloomPass
			for (var n in uniforms) { fx.screenUniforms[ n ].value = uniforms[ n ]; }
		}
	}

	if (msg.godrays) {
		if (postprocessing.enabled == false) enable_godrays();
	} else {
		if (postprocessing.enabled == true) disable_godrays();
	}

}

function debug_geo( geo ) {
	var used = {};
	for (var i=0; i<geo.faces.length; i++) {
		face = geo.faces[i];
		used[face.a]=true;
		used[face.b]=true;
		used[face.c]=true;
		used[face.d]=true;
	}
	console.log( used );
	return used;
} 

function on_collada_ready( collada ) {
	console.log( '>> collada loaded' );
	_current_collada_download = null;
	if (_colladas_pending.length) {
		_download_collada( _colladas_pending.pop() );
	}

	var _mesh = collada.scene.children[0];
	_mesh.useQuaternion = true;
	_mesh.updateMatrix();
	_mesh.matrixAutoUpdate = false;
	MESHES.push( _mesh );

	if (USE_SHADOWS) {
		_mesh.castShadow = true;
		_mesh.receiveShadow = true;
	}

	//_mesh.geometry.computeTangents();	// requires UV's, this must come before material is assigned
	//_mesh.geometry.computeLineDistances();

	if ( Objects[_mesh.name] ) {
		// SECOND LOAD: loading LOD base level //
		var lod = Objects[ _mesh.name ];

		_mesh.position.set(0,0,0);
		_mesh.scale.set(1,1,1);
		_mesh.quaternion.set(0,0,0,1);
		_mesh.updateMatrix();

		lod.addLevel( _mesh, 8 );
		lod.base_mesh = _mesh;		// subdiv mod uses: lod.base_mesh.geometry_base

		if (USE_MODIFIERS) {
			_mesh.geometry.dynamic = true;		// required
			//_mesh.geometry_base = THREE.GeometryUtils.clone(_mesh.geometry);
			_mesh.geometry_base = _mesh.geometry.clone(); // new three API
			//_mesh.material = WIRE_MATERIAL;
		}

		lod.shader = create_normal_shader(
			{
				name :			lod.name,
				displacement :	lod.has_displacement,
				ao :				lod.has_AO,
				diffuse_size :	256,
				callback :		on_texture_ready		// allows progressive texture loading
			}
		);
		_mesh.material = lod.shader;


	} else {
		// FIRST LOAD: loading LOD far level //
		//_mesh.material.vertexColors = THREE.VertexColors;	// not a good idea

		//_mesh.material = create_normal_shader(
		//	{
		//		name :	_mesh.name,
		//		prefix :	'/bake/LOD/'
		//	}
		//);
		var lod = new THREE.LOD();

		_mesh.material = new THREE.MeshLambertMaterial({
			transparent: false,
			color: 0xffffff
		});

		lod.name = _mesh.name;
		lod.base_mesh = null;
		lod.useQuaternion = true;			// ensure Quaternion
		lod.has_progressive_textures = false;	// enabled from websocket stream
		lod.shader = null;
		lod.dirty_modifiers = true;
		lod.auto_subdivision = false;

		lod.multires = false;
		lod.has_displacement = false;
		lod.has_AO = false;	// TODO fix baking to hide LOD proxy

		lod.position.copy( _mesh.position );
		lod.scale.copy( _mesh.scale );
		lod.quaternion.copy( _mesh.quaternion );

		_mesh.position.set(0,0,0);
		_mesh.scale.set(1,1,1);
		_mesh.quaternion.set(0,0,0,1);
		_mesh.updateMatrix();


		// custom attributes (for callbacks)
		lod.custom_attributes = {};
		lod._uid_ = parseInt( lod.name.replace('__','').replace('__','') );
		lod.do_mouse_up_callback = function () {
			lod.on_mouse_up_callback( lod.custom_attributes );
		};
		lod.do_input_callback = function (txt) {
			console.log('sending text');
			console.log(txt);
			lod.on_input_callback( lod.custom_attributes, txt ); //
		}

		if (UserAPI.on_model_loaded) {
			UserAPI.on_model_loaded( lod, _mesh );
		}

		lod.addLevel( _mesh, 12 );
		lod.updateMatrix();
		//mesh.matrixAutoUpdate = false;


		// add to scene //
		Objects[ lod.name ] = lod;
		scene.add( lod );

/*
		setTimeout( function () {
			var loader = new THREE.ColladaLoader();
			loader.options.convertUpAxis = true;
			loader.options.centerGeometry = true;
			loader.load(
				'/objects/' + lod.name + '.dae?hires', 
				on_collada_ready
			);	
		}, 10000 );
*/
	}
}


function reload_progressive_textures( ob ) {
	var name = ob.name;
	ob.shader.uniforms[ "tDiffuse" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?TEXTURE|64|True', undefined, on_texture_ready );

	ob.shader.uniforms[ "tNormal" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?NORMALS|128|True', undefined, on_texture_ready );

	if (ob.has_AO) {
		ob.shader.uniforms[ "tAO" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?AO|64|True', undefined, on_texture_ready );
	}

	//ob.shader.uniforms[ "tSpecular" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?SPEC_INTENSITY|64|True', undefined, on_texture_ready );

	if (ob.has_displacement) {
		ob.shader.uniforms[ "tDisplacement" ].texture = THREE.ImageUtils.loadTexture(
			'/bake/'+name+'.jpg?DISPLACEMENT|256|True', undefined, on_texture_ready 
		);
	}

}


QUEUE = [];
TEX_LOADING = {};
function on_texture_ready( img ) {
	var url = img.src.split('?')[0];
	var args = img.src.split('?')[1];
	var type = args.split('|')[0];
	var size = parseInt( args.split('|')[1] );
	var a = url.split('/');
	var name = a[ a.length-1 ];
	name = name.substring( 0, name.length-4 );
	ob = Objects[ name ];

	if (img.attributes['src'].nodeValue in TEX_LOADING) {		// only assign texture when ready
		var tex = TEX_LOADING[ img.attributes['src'].nodeValue ];
		if (type=='NORMALS') {
			ob.shader.uniforms['tNormal'].texture = tex;
		} else if (type=='TEXTURE') {
			ob.shader.uniforms['tDiffuse'].texture = tex;
		} else if (type=='AO') {
			ob.shader.uniforms['tAO'].texture = tex;
		} else if (type=='DISPLACEMENT') {
			ob.shader.uniforms['tDisplacement'].texture = tex;
		} else if (type=='SPEC_INTENSITY') {
			ob.shader.uniforms['tSpecular'].texture = tex;
		} else { console.log('ERROR: unknown shader layer: '+type); }
	}

	/////////////////// do progressive loading ////////////////
	if (ob.has_progressive_textures) {
		// MAX_PROGRESSIVE_TEXTURE, etc. are defined by the server //
		size *= 2;
		if (type=='TEXTURE' && size <= MAX_PROGRESSIVE_TEXTURE) {
			QUEUE.push( '/bake/'+name+'.jpg?'+type+'|'+size );
			setTimeout( request_progressive_texture, 1000 );
		}
		else if (type=='NORMALS' && size <= MAX_PROGRESSIVE_NORMALS) {
			QUEUE.push( '/bake/'+name+'.jpg?'+type+'|'+size );
			setTimeout( request_progressive_texture, 1000 );
		}
		else if (type=='DISPLACEMENT' && size <= MAX_PROGRESSIVE_DISPLACEMENT) {
			QUEUE.push( '/bake/'+name+'.jpg?'+type+'|'+size );
			setTimeout( request_progressive_texture, 1000 );
		}
		else if (size <= MAX_PROGRESSIVE_DEFAULT) {
			QUEUE.push( '/bake/'+name+'.jpg?'+type+'|'+size );
			setTimeout( request_progressive_texture, 1000 );
		}
	}
}

function request_progressive_texture() {
	var url = QUEUE.pop();
	var tex = THREE.ImageUtils.loadTexture( url, undefined, on_texture_ready );
	TEX_LOADING[ url ] = tex;
}


function create_normal_shader( params ) {
	console.log('create_normal_shader');
	return new THREE.MeshBasicMaterial( {
		color: 0x000000, 
		shading: THREE.FlatShading,
		opacity: 0.1,
		transparent: true,
		blending: THREE.AdditiveBlending
	});
}


function create_normal_shader_deprecated( params ) {
	var name = params.name;
	var displacement = params.displacement;
	var AO = params.ao;
	var callback = params.callback;
	var prefix = params.prefix;
	var diffuse_size = params.diffuse_size;
	var normals_size = params.normals_size;
	var ao_size = params.ao_size;
	var disp_size = params.displacement_size;

	// defaults //
	if (prefix === undefined) prefix = '/bake/';
	if (diffuse_size === undefined) diffuse_size = 128;
	if (normals_size === undefined) normals_size = 128;
	if (ao_size === undefined) ao_size = 128;
	if (disp_size === undefined) disp_size = 128;


	var ambient = 0x111111, diffuse = 0xbbbbbb, specular = 0x171717, shininess = 50;
	var shader = THREE.ShaderUtils.lib[ "normal" ];
	var uniforms = THREE.UniformsUtils.clone( shader.uniforms );

/*
	uniforms[ "tDiffuse" ].texture = THREE.ImageUtils.loadTexture(
		prefix+name+'.jpg?TEXTURE|'+diffuse_size, undefined, callback
	);
	uniforms[ "tNormal" ].texture = THREE.ImageUtils.loadTexture(
		prefix+name+'.jpg?NORMALS|'+normals_size, undefined, callback
	);
	if (AO) {
		uniforms[ "tAO" ].texture = THREE.ImageUtils.loadTexture( prefix+name+'.jpg?AO|'+ao_size, undefined, callback );
	}

*/

	//uniforms[ "tSpecular" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?SPEC_INTENSITY|64', undefined, callback );

	uniforms[ "uNormalScale" ].value = 0.8;
	if (AO) {
		uniforms[ "enableAO" ].value = true;
	} else {
		uniforms[ "enableAO" ].value = false;
	}
	uniforms[ "enableDiffuse" ].value = true;
	uniforms[ "enableSpecular" ].value = false;
	uniforms[ "enableReflection" ].value = false;

	uniforms[ "uDiffuseColor" ].value.setHex( diffuse );
	uniforms[ "uSpecularColor" ].value.setHex( specular );
	uniforms[ "uAmbientColor" ].value.setHex( ambient );

	uniforms[ "uShininess" ].value = shininess;

	if (displacement) {
		console.log(name + ' has displacement');
		uniforms[ "tDisplacement" ].texture = THREE.ImageUtils.loadTexture(
			prefix+name+'.jpg?DISPLACEMENT|'+disp_size, undefined, callback 
		);
		uniforms[ "uDisplacementBias" ].value = 0.0;
		uniforms[ "uDisplacementScale" ].value = 0.0;
	} else {
		uniforms[ "uDisplacementBias" ].value = 0.0;
		uniforms[ "uDisplacementScale" ].value = 0.0;
	}

	uniforms[ "wrapRGB" ].value.set( 0.75, 0.5, 0.5 );

	var parameters = { fragmentShader: shader.fragmentShader, vertexShader: shader.vertexShader, uniforms: uniforms, lights: true };
	var material = new THREE.ShaderMaterial( parameters );

	material.wrapAround = true;
	material.color = uniforms['uDiffuseColor'].value;
	return material;
}






//////////////////////////////////////////////////////////////////////


function enable_godrays() {
	//renderer.sortObjects = false;
	renderer.autoClear = false;
	renderer.setClearColorHex( bgColor, 1 );
	postprocessing.enabled = true;
}
function disable_godrays() {
	//renderer.sortObjects = false;
	//renderer.autoClear = true;	# bloom wants autoclear off
	renderer.setClearColor( {r:0.14,g:0.14,b:0.14}, 1.0 )
	postprocessing.enabled = false;
	scene.overrideMaterial = null;


}



function setupGodRays() {
	materialDepth = new THREE.MeshDepthMaterial();
	var materialScene = new THREE.MeshBasicMaterial( { color: 0x000000, shading: THREE.FlatShading } );


	//////////////////// init-postproc ////////////////
	postprocessing.scene = new THREE.Scene();

	postprocessing.camera = new THREE.OrthographicCamera( window.innerWidth / - 2, window.innerWidth / 2,  height / 2, height / - 2, -10000, 10000 );
	postprocessing.camera.position.z = 100;

	postprocessing.scene.add( postprocessing.camera );

	var pars = { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, format: THREE.RGBFormat };
	postprocessing.rtTextureColors = new THREE.WebGLRenderTarget( window.innerWidth, height, pars );

	// Switching the depth formats to luminance from rgb doesn't seem to work. I didn't
	// investigate further for now.
	// pars.format = THREE.LuminanceFormat;

	// I would have this quarter size and use it as one of the ping-pong render
	// targets but the aliasing causes some temporal flickering

	postprocessing.rtTextureDepth = new THREE.WebGLRenderTarget( window.innerWidth, height, pars );

	// Aggressive downsize god-ray ping-pong render targets to minimize cost

	var w = window.innerWidth / 4.0;
	var h = height / 4.0;
	postprocessing.rtTextureGodRays1 = new THREE.WebGLRenderTarget( w, h, pars );
	postprocessing.rtTextureGodRays2 = new THREE.WebGLRenderTarget( w, h, pars );

	// god-ray shaders

	var godraysGenShader = THREE.ShaderGodRays[ "godrays_generate" ];
	postprocessing.godrayGenUniforms = THREE.UniformsUtils.clone( godraysGenShader.uniforms );
	postprocessing.materialGodraysGenerate = new THREE.ShaderMaterial( {

		uniforms: postprocessing.godrayGenUniforms,
		vertexShader: godraysGenShader.vertexShader,
		fragmentShader: godraysGenShader.fragmentShader

	} );

	var godraysCombineShader = THREE.ShaderGodRays[ "godrays_combine" ];
	postprocessing.godrayCombineUniforms = THREE.UniformsUtils.clone( godraysCombineShader.uniforms );
	postprocessing.materialGodraysCombine = new THREE.ShaderMaterial( {

		uniforms: postprocessing.godrayCombineUniforms,
		vertexShader: godraysCombineShader.vertexShader,
		fragmentShader: godraysCombineShader.fragmentShader

	} );

	var godraysFakeSunShader = THREE.ShaderGodRays[ "godrays_fake_sun" ];
	postprocessing.godraysFakeSunUniforms = THREE.UniformsUtils.clone( godraysFakeSunShader.uniforms );
	postprocessing.materialGodraysFakeSun = new THREE.ShaderMaterial( {

		uniforms: postprocessing.godraysFakeSunUniforms,
		vertexShader: godraysFakeSunShader.vertexShader,
		fragmentShader: godraysFakeSunShader.fragmentShader

	} );

	postprocessing.godraysFakeSunUniforms.bgColor.value.setHex( bgColor );
	postprocessing.godraysFakeSunUniforms.sunColor.value.setHex( sunColor );

	postprocessing.godrayCombineUniforms.fGodRayIntensity.value = 0.75;

	postprocessing.quad = new THREE.Mesh( new THREE.PlaneGeometry( window.innerWidth, height ), postprocessing.materialGodraysGenerate );
	postprocessing.quad.position.z = -9900;
	postprocessing.quad.rotation.x = Math.PI / 2;
	postprocessing.scene.add( postprocessing.quad );


}

UserAPI.setup_depth_of_field = function ( enabled ) {
	// set the global depth material
	//var height = window.innerHeight - 300;
	material_depth = new THREE.MeshDepthMaterial();

	postprocessing.scene = new THREE.Scene();
	postprocessing.enabled = enabled;

	postprocessing.camera = new THREE.OrthographicCamera( window.innerWidth / - 2, window.innerWidth / 2,  window.innerHeight / 2, window.innerHeight / - 2, -10000, 10000 );
	postprocessing.camera.position.z = 100;

	postprocessing.scene.add( postprocessing.camera );

	var pars = { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, format: THREE.RGBFormat };
	postprocessing.rtTextureDepth = new THREE.WebGLRenderTarget( window.innerWidth, height, pars );
	postprocessing.rtTextureColor = new THREE.WebGLRenderTarget( window.innerWidth, height, pars );

	var bokeh_shader = THREE.BokehShader;

	postprocessing.bokeh_uniforms = THREE.UniformsUtils.clone( bokeh_shader.uniforms );

	postprocessing.bokeh_uniforms[ "tColor" ].value = postprocessing.rtTextureColor;
	postprocessing.bokeh_uniforms[ "tDepth" ].value = postprocessing.rtTextureDepth;
	postprocessing.bokeh_uniforms[ "focus" ].value = 1.1;
	postprocessing.bokeh_uniforms[ "aspect" ].value = window.innerWidth / height;

	postprocessing.materialBokeh = new THREE.ShaderMaterial( {

		uniforms: postprocessing.bokeh_uniforms,
		vertexShader: bokeh_shader.vertexShader,
		fragmentShader: bokeh_shader.fragmentShader

	} );

	postprocessing.quad = new THREE.Mesh( new THREE.PlaneGeometry( window.innerWidth, window.innerHeight ), postprocessing.materialBokeh );
	postprocessing.quad.position.z = - 500;
	postprocessing.scene.add( postprocessing.quad );

	return postprocessing;
}




var FX = {};
var composer;

UserAPI.setup_compositor = function ( config ) {
	var fx;
	renderer.autoClear = false;	// required by bloom FX

	renderTargetParameters = {
		minFilter: THREE.LinearFilter, 
		magFilter: THREE.LinearFilter, 
		format: THREE.RGBAFormat, 
		stencilBufer: true,
	};
	renderTarget = new THREE.WebGLRenderTarget( 
		SCREEN_WIDTH, SCREEN_HEIGHT, 
		renderTargetParameters 
	);

	composer = new THREE.EffectComposer( renderer, renderTarget );

	var renderModel = new THREE.RenderPass( scene, camera );
	composer.addPass( renderModel );
	FX['BASE'] = renderModel;

	if (config.antialias) {
		FX['fxaa'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "fxaa" ] );
		fx.uniforms[ 'resolution' ].value.set( 1 / SCREEN_WIDTH, 1 / SCREEN_HEIGHT );
		composer.addPass( fx );

	}

	if (config.ao) {
		FX['ssao'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "ssao" ] );	// TODO find tutorial
		composer.addPass( fx );
	}

	if (config.dots) {
		FX['dots'] = fx = new THREE.DotScreenPass( new THREE.Vector2( 0, 0 ), 0.5, 1.8 );	// center, angle, size
		composer.addPass( fx );
	}

	if (config.vignette) {
		FX['vignette'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "vignette" ] );
		composer.addPass( fx );

	}

	if (config.bloom) {
		FX['bloom'] = fx = new THREE.BloomPass( 1.1 );
		composer.addPass( fx );		
	}

	if (config.dots2) {
		FX['glowing_dots'] = fx = new THREE.DotScreenPass( new THREE.Vector2( 0, 0 ), 0.01, 0.23 );
		composer.addPass( fx );

	}


	// fake DOF //	
	var bluriness = 3;
	if (config.hblur) {
		FX['blur_horizontal'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "horizontalTiltShift" ] );
		fx.uniforms[ 'h' ].value = bluriness / SCREEN_WIDTH;
		fx.uniforms[ 'r' ].value = 0.5;
		composer.addPass( fx );

	}

	if (config.vblur) {
		FX['blur_vertical'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "verticalTiltShift" ] );
		fx.uniforms[ 'v' ].value = bluriness / SCREEN_HEIGHT;
		fx.uniforms[ 'r' ].value = 0.5;
		composer.addPass( fx );

	}

	if (config.noise) {
		//			noise intensity, scanline intensity, scanlines, greyscale
		FX['noise'] = fx = new THREE.FilmPass( 0.01, 0.5, SCREEN_HEIGHT / 1.5, false );
		composer.addPass( fx );		
	}

	if (config.film) {
		//			noise intensity, scanline intensity, scanlines, greyscale
		FX['film'] = fx = new THREE.FilmPass( 0.01, 0.9, SCREEN_HEIGHT / 3, false );
		composer.addPass( fx );
	}


	////////////////////////////////////// dummy //////////////////////////////////
	FX['dummy'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "screen" ] );	// ShaderPass copies uniforms
	fx.uniforms['opacity'].value = 1.0;	// ensure nothing happens
	fx.renderToScreen = true;	// this means that this is final pass and render it to the screen.
	composer.addPass( fx );

	UserAPI.compositor = FX;
	UserAPI.composer = composer;

	return composer;
}




function distance_to_camera( ob ) {
		camera.matrixWorldInverse.getInverse( camera.matrixWorld );
		var inverse  = camera.matrixWorldInverse;
		var distance = -( inverse.elements[2] * ob.matrixWorld.elements[12] + inverse.elements[6] * ob.matrixWorld.elements[13] + inverse.elements[10] * ob.matrixWorld.elements[14] + inverse.elements[14] );
		return distance;
}

var _prev_width = window.innerWidth;
var _prev_height = window.innerHeight;
function resize_view() {
	if (window.innerWidth != _prev_width || window.innerHeight != _prev_height) {
		_prev_width = window.innerWidth;
		_prev_height = window.innerHeight;
		renderer.setSize( window.innerWidth, window.innerHeight-10 );
		camera.aspect = window.innerWidth / (window.innerHeight-10);
		camera.updateProjectionMatrix();
		if (UserAPI.on_view_resized) {
			UserAPI.on_view_resized();
		}

		console.log(">> resize view");
	}
}
UserAPI.resize_view = resize_view;


var clock = new THREE.Clock();
var dbug = null;

function render_debug() {
	var delta = clock.getDelta();
	CONTROLLER.update( delta );
	renderer.render( scene, camera );
}

function render() {
	var timer = Date.now() * 0.0005;
	resize_view();
	var delta = clock.getDelta();

	if (CONTROLLER.enabled) {
		CONTROLLER.update( delta );
	}


	if (UserAPI.on_redraw) {
		UserAPI.on_redraw( delta );
	}

	scene.updateMatrixWorld();
	//scene.traverse(
	//	function ( node ) { if ( node instanceof THREE.LOD ) node.update( camera ) } 
	//);

	for (var i=0; i<Sounds.length; i++) {
		Sounds[i].update(camera);
	}

	var time = Date.now() * 0.001;
	for (var i=0; i<SpinningObjects.length; i++) {
		var object = SpinningObjects[i];
		object.rotation.x = 0.25 * time;
		object.rotation.y = 0.25 * time;
	}

	if ( postprocessing.enabled ) {
		render_dof();
	} else {
		composer.render( 0.1 );
	}

	TWEEN.update();

}

var sunPosition = new THREE.Vector3( 0, 1000, -1000 );
var screenSpacePosition = new THREE.Vector3();
var orbitRadius = 200;
var bgColor = 0x000511;
var sunColor = 0xffee00;

var margin = 100;
var height = window.innerHeight - 2 * margin;

function render_dof() {

	renderer.clear();

	// Render scene into texture

	scene.overrideMaterial = null;
	renderer.render( scene, camera, postprocessing.rtTextureColor, true );

	// Render depth into texture

	scene.overrideMaterial = material_depth;
	renderer.render( scene, camera, postprocessing.rtTextureDepth, true );

	// Render bokeh composite

	renderer.render( postprocessing.scene, postprocessing.camera );

}

function render_godrays() {	// TODO how to combine godrays and composer - TODO update and test this
	var timer = Date.now() * 0.0005;
	resize_view();
	var delta = clock.getDelta();
	CONTROLLER.update( delta );
	//////////////////////////////////////////

	var margin = 100;
	var height = window.innerHeight - 2 * margin;
	// Find the screenspace position of the sun

	screenSpacePosition.copy( sunPosition );
	projector.projectVector( screenSpacePosition, camera );

	screenSpacePosition.x = ( screenSpacePosition.x + 1 ) / 2;
	screenSpacePosition.y = ( screenSpacePosition.y + 1 ) / 2;

	// Give it to the god-ray and sun shaders

	postprocessing.godrayGenUniforms[ "vSunPositionScreenSpace" ].value.x = screenSpacePosition.x;
	postprocessing.godrayGenUniforms[ "vSunPositionScreenSpace" ].value.y = screenSpacePosition.y;

	postprocessing.godraysFakeSunUniforms[ "vSunPositionScreenSpace" ].value.x = screenSpacePosition.x;
	postprocessing.godraysFakeSunUniforms[ "vSunPositionScreenSpace" ].value.y = screenSpacePosition.y;

	// -- Draw sky and sun --

	// Clear colors and depths, will clear to sky color

	renderer.clearTarget( postprocessing.rtTextureColors, true, true, false );

	// Sun render. Runs a shader that gives a brightness based on the screen
	// space distance to the sun. Not very efficient, so i make a scissor
	// rectangle around the suns position to avoid rendering surrounding pixels.

	var sunsqH = 0.74 * height; // 0.74 depends on extent of sun from shader
	var sunsqW = 0.74 * height; // both depend on height because sun is aspect-corrected

	screenSpacePosition.x *= window.innerWidth;
	screenSpacePosition.y *= height;

	renderer.setScissor( screenSpacePosition.x - sunsqW / 2, screenSpacePosition.y - sunsqH / 2, sunsqW, sunsqH );
	renderer.enableScissorTest( true );

	postprocessing.godraysFakeSunUniforms[ "fAspect" ].value = window.innerWidth / height;

	postprocessing.scene.overrideMaterial = postprocessing.materialGodraysFakeSun;
	renderer.render( postprocessing.scene, postprocessing.camera, postprocessing.rtTextureColors );

	renderer.enableScissorTest( false );

	// -- Draw scene objects --

	// Colors

	scene.overrideMaterial = null;
	renderer.render( scene, camera, postprocessing.rtTextureColors );

	// Depth

	scene.overrideMaterial = materialDepth;
	renderer.render( scene, camera, postprocessing.rtTextureDepth, true );

	// -- Render god-rays --

	// Maximum length of god-rays (in texture space [0,1]X[0,1])

	var filterLen = 1.0;

	// Samples taken by filter

	var TAPS_PER_PASS = 6.0;

	// Pass order could equivalently be 3,2,1 (instead of 1,2,3), which
	// would start with a small filter support and grow to large. however
	// the large-to-small order produces less objectionable aliasing artifacts that
	// appear as a glimmer along the length of the beams

	// pass 1 - render into first ping-pong target

	var pass = 1.0;
	var stepLen = filterLen * Math.pow( TAPS_PER_PASS, -pass );

	postprocessing.godrayGenUniforms[ "fStepSize" ].value = stepLen;
	postprocessing.godrayGenUniforms[ "tInput" ].texture = postprocessing.rtTextureDepth;

	postprocessing.scene.overrideMaterial = postprocessing.materialGodraysGenerate;

	renderer.render( postprocessing.scene, postprocessing.camera, postprocessing.rtTextureGodRays2 );

	// pass 2 - render into second ping-pong target

	pass = 2.0;
	stepLen = filterLen * Math.pow( TAPS_PER_PASS, -pass );

	postprocessing.godrayGenUniforms[ "fStepSize" ].value = stepLen;
	postprocessing.godrayGenUniforms[ "tInput" ].texture = postprocessing.rtTextureGodRays2;

	renderer.render( postprocessing.scene, postprocessing.camera, postprocessing.rtTextureGodRays1  );

	// pass 3 - 1st RT

	pass = 3.0;
	stepLen = filterLen * Math.pow( TAPS_PER_PASS, -pass );

	postprocessing.godrayGenUniforms[ "fStepSize" ].value = stepLen;
	postprocessing.godrayGenUniforms[ "tInput" ].texture = postprocessing.rtTextureGodRays1;

	renderer.render( postprocessing.scene, postprocessing.camera , postprocessing.rtTextureGodRays2  );

	// final pass - composite god-rays onto colors

	postprocessing.godrayCombineUniforms["tColors"].texture = postprocessing.rtTextureColors;
	postprocessing.godrayCombineUniforms["tGodRays"].texture = postprocessing.rtTextureGodRays2;

	postprocessing.scene.overrideMaterial = postprocessing.materialGodraysCombine;

	renderer.render( postprocessing.scene, postprocessing.camera );
	postprocessing.scene.overrideMaterial = null;


}



//////////////////////////////////////////////////// Camera Controls ////////////////////////////////////////////////
/**
 * @author Eberhard Graether / http://egraether.com/
 */

CameraController = function ( object, domElement ) {

	THREE.EventDispatcher.call( this );

	var _this = this;
	var STATE = { NONE: -1, ROTATE: 2, ZOOM: 1, PAN: 0, TOUCH_ROTATE: 3, TOUCH_ZOOM: 4, TOUCH_PAN: 5 };

	this.object = object;
	this.domElement = ( domElement !== undefined ) ? domElement : document;

	// API

	this.enabled = true;

	this.screen = { width: 0, height: 0, offsetLeft: 0, offsetTop: 0 };
	this.radius = ( this.screen.width + this.screen.height ) / 4;

	this.rotateSpeed = 1.0;
	this.zoomSpeed = 1.2;
	this.panSpeed = 0.3;

	this.noRotate = false;
	this.noZoom = false;
	this.noPan = false;

	this.staticMoving = false;
	this.dynamicDampingFactor = 0.2;

	this.minDistance = 0;
	this.maxDistance = Infinity;

	this.keys = [ 65 /*A*/, 83 /*S*/, 68 /*D*/ ];

	// internals
	this.use_smooth_target = true;
	this.smooth_target = new THREE.Vector3();
	this.allow_tilt = false;

	this.target = new THREE.Vector3();

	var lastPosition = new THREE.Vector3();

	var _state = STATE.NONE,
	_prevState = STATE.NONE,

	_eye = new THREE.Vector3(),

	_rotateStart = new THREE.Vector3(),
	_rotateEnd = new THREE.Vector3(),

	_zoomStart = new THREE.Vector2(),
	_zoomEnd = new THREE.Vector2(),

	_touchZoomDistanceStart = 0,
	_touchZoomDistanceEnd = 0,

	_panStart = new THREE.Vector2(),
	_panEnd = new THREE.Vector2();

	// for reset

	this.target0 = this.target.clone();
	this.position0 = this.object.position.clone();
	this.up0 = this.object.up.clone();

	// events

	var changeEvent = { type: 'change' };


	// methods

	this.handleResize = function () {

		this.screen.width = window.innerWidth;
		this.screen.height = window.innerHeight;

		this.screen.offsetLeft = 0;
		this.screen.offsetTop = 0;

		this.radius = ( this.screen.width + this.screen.height ) / 4;

	};

	this.handleEvent = function ( event ) {

		if ( typeof this[ event.type ] == 'function' ) {

			this[ event.type ]( event );

		}

	};

	this.getMouseOnScreen = function ( clientX, clientY ) {

		return new THREE.Vector2(
			( clientX - _this.screen.offsetLeft ) / _this.radius * 0.5,
			( clientY - _this.screen.offsetTop ) / _this.radius * 0.5
		);

	};

	this.getMouseProjectionOnBall = function ( clientX, clientY ) {

		var mouseOnBall = new THREE.Vector3(
			( clientX - _this.screen.width * 0.5 - _this.screen.offsetLeft ) / _this.radius,
			( _this.screen.height * 0.5 + _this.screen.offsetTop - clientY ) / _this.radius,
			0.0
		);

		var length = mouseOnBall.length();

		if ( length > 1.0 ) {

			mouseOnBall.normalize();

		} else {

			mouseOnBall.z = Math.sqrt( 1.0 - length * length );

		}

		_eye.copy( _this.object.position ).sub( _this.target );

		var projection = _this.object.up.clone().setLength( mouseOnBall.y );
		projection.add( _this.object.up.clone().cross( _eye ).setLength( mouseOnBall.x ) );
		projection.add( _eye.setLength( mouseOnBall.z ) );

		return projection;

	};

	this.rotateCamera = function () {

		var angle = Math.acos( _rotateStart.dot( _rotateEnd ) / _rotateStart.length() / _rotateEnd.length() );

		if ( angle ) {

			var axis = ( new THREE.Vector3() ).crossVectors( _rotateStart, _rotateEnd ).normalize(),
				quaternion = new THREE.Quaternion();

			angle *= _this.rotateSpeed;

			quaternion.setFromAxisAngle( axis, -angle );

			_eye.applyQuaternion( quaternion );

			if (_this.allow_tilt) {  // do not allow tilt camera by default
				_this.object.up.applyQuaternion( quaternion );
			}

			_rotateEnd.applyQuaternion( quaternion );

			if ( _this.staticMoving ) {

				_rotateStart.copy( _rotateEnd );

			} else {

				quaternion.setFromAxisAngle( axis, angle * ( _this.dynamicDampingFactor - 1.0 ) );
				_rotateStart.applyQuaternion( quaternion );

			}

		}

	};

	this.zoomCamera = function () {

		if ( _state === STATE.TOUCH_ZOOM ) {

			var factor = _touchZoomDistanceStart / _touchZoomDistanceEnd;
			_touchZoomDistanceStart = _touchZoomDistanceEnd;
			_eye.multiplyScalar( factor );

		} else {

			var factor = 1.0 + ( _zoomEnd.y - _zoomStart.y ) * _this.zoomSpeed;

			if ( factor !== 1.0 && factor > 0.0 ) {

				_eye.multiplyScalar( factor );

				if ( _this.staticMoving ) {

					_zoomStart.copy( _zoomEnd );

				} else {

					_zoomStart.y += ( _zoomEnd.y - _zoomStart.y ) * this.dynamicDampingFactor;

				}

			}

		}

	};

	this.panCamera = function () {

		var mouseChange = _panEnd.clone().sub( _panStart );

		if ( mouseChange.lengthSq() ) {

			mouseChange.multiplyScalar( _eye.length() * _this.panSpeed );

			var pan = _eye.clone().cross( _this.object.up ).setLength( mouseChange.x );
			pan.add( _this.object.up.clone().setLength( mouseChange.y ) );

			_this.object.position.add( pan );
			_this.target.add( pan );

			if ( _this.staticMoving ) {

				_panStart = _panEnd;

			} else {

				_panStart.add( mouseChange.subVectors( _panEnd, _panStart ).multiplyScalar( _this.dynamicDampingFactor ) );

			}

		}

	};

	this.checkDistances = function () {

		if ( !_this.noZoom || !_this.noPan ) {

			if ( _this.object.position.lengthSq() > _this.maxDistance * _this.maxDistance ) {

				_this.object.position.setLength( _this.maxDistance );

			}

			if ( _eye.lengthSq() < _this.minDistance * _this.minDistance ) {

				_this.object.position.addVectors( _this.target, _eye.setLength( _this.minDistance ) );

			}

		}

	};

	this.update = function (delta) {
		//console.log(delta);

		_eye.subVectors( _this.object.position, _this.target );

		if ( !_this.noRotate ) {

			_this.rotateCamera();

		}

		if ( !_this.noZoom ) {

			_this.zoomCamera();

		}

		if ( !_this.noPan ) {

			_this.panCamera();

		}

		_this.object.position.addVectors( _this.target, _eye );

		_this.checkDistances();

		_this.object.lookAt( _this.target );

		// new controller_options extra user options //
		if (_this.object.controller_options !== undefined) {
			if (_this.object.controller_options.follows_target !== undefined) {
				//_this.object.controller_options.follows_target.lookAt( _this.target );
				_this.object.controller_options.follows_target.target.position.x = _this.target.x;
				_this.object.controller_options.follows_target.target.position.y = _this.target.y;
				_this.object.controller_options.follows_target.target.position.z = _this.target.z;
			}

			if (_this.object.controller_options.follows !== undefined) {
				//_this.object.controller_options.follows_target.lookAt( _this.target );
				_this.object.controller_options.follows.position.x = _this.object.position.x;
				_this.object.controller_options.follows.position.y = _this.object.position.y;
				_this.object.controller_options.follows.position.z = _this.object.position.z;
			}

		}

		if ( lastPosition.distanceToSquared( _this.object.position ) > 0 ) {

			_this.dispatchEvent( changeEvent );

			lastPosition.copy( _this.object.position );

		}
		if (_this.use_smooth_target) {
			var p = _this.target;
			var u = p.clone();
			u.sub( _this.smooth_target );
			u.multiplyScalar( 0.1 );
			p.sub( u );

		}

		// custom extra position constraint //
		if (_this.object.position_target && _this.object.use_position_constraint) {
			var p = _this.object.position;
			var u = p.clone();
			u.sub( _this.object.position_target );
			u.multiplyScalar( 0.1 );
			p.sub( u );
		}

	};

	this.reset = function () {

		_state = STATE.NONE;
		_prevState = STATE.NONE;

		_this.target.copy( _this.target0 );
		_this.object.position.copy( _this.position0 );
		_this.object.up.copy( _this.up0 );

		_eye.subVectors( _this.object.position, _this.target );

		_this.object.lookAt( _this.target );

		_this.dispatchEvent( changeEvent );

		lastPosition.copy( _this.object.position );

	};

	// listeners



	function mousedown( event ) {
		on_mouse_down( event );
		document.addEventListener( 'mousemove', mousemove, false );
		document.addEventListener( 'mouseup', mouseup, false );

		if ( _this.enabled === false ) return;

		event.preventDefault();
		event.stopPropagation();


		//_state = STATE.ZOOM;

		if ( _state === STATE.NONE ) {

			_state = event.button;

		}

		if ( _state === STATE.ROTATE && !_this.noRotate ) {

			_rotateStart = _rotateEnd = _this.getMouseProjectionOnBall( event.clientX, event.clientY );

		} else if ( _state === STATE.ZOOM && !_this.noZoom ) {

			_zoomStart = _zoomEnd = _this.getMouseOnScreen( event.clientX, event.clientY );

		} else if ( _state === STATE.PAN && !_this.noPan ) {

			_panStart = _panEnd = _this.getMouseOnScreen( event.clientX, event.clientY );

		}


	}

	function mousemove( event ) {

		if ( _this.enabled === false ) return;

		event.preventDefault();
		event.stopPropagation();

		if ( _state === STATE.ROTATE && !_this.noRotate ) {

			_rotateEnd = _this.getMouseProjectionOnBall( event.clientX, event.clientY );

		} else if ( _state === STATE.ZOOM && !_this.noZoom ) {

			_zoomEnd = _this.getMouseOnScreen( event.clientX, event.clientY );

		} else if ( _state === STATE.PAN && !_this.noPan ) {

			_panEnd = _this.getMouseOnScreen( event.clientX, event.clientY );

		}

	}

	function mouseup( event ) {
		on_mouse_up( event );
		if ( _this.enabled === false ) return;

		event.preventDefault();
		event.stopPropagation();

		_state = STATE.NONE;

		document.removeEventListener( 'mousemove', mousemove );
		document.removeEventListener( 'mouseup', mouseup );

	}

	function mousewheel( event ) {

		if ( _this.enabled === false ) return;

		event.preventDefault();
		event.stopPropagation();

		var delta = 0;

		if ( event.wheelDelta ) { // WebKit / Opera / Explorer 9

			delta = event.wheelDelta / 10;

		} else if ( event.detail ) { // Firefox

			delta = - event.detail / 3;

		}

		_zoomStart.y += ( 1 / delta ) * 0.05;

	}

	function touchstart( event ) {

		if ( _this.enabled === false ) return;

		switch ( event.touches.length ) {

			case 1:
				_state = STATE.TOUCH_ROTATE;
				_rotateStart = _rotateEnd = _this.getMouseProjectionOnBall( event.touches[ 0 ].pageX, event.touches[ 0 ].pageY );
				break;

			case 2:
				_state = STATE.TOUCH_ZOOM;
				var dx = event.touches[ 0 ].pageX - event.touches[ 1 ].pageX;
				var dy = event.touches[ 0 ].pageY - event.touches[ 1 ].pageY;
				_touchZoomDistanceEnd = _touchZoomDistanceStart = Math.sqrt( dx * dx + dy * dy );
				break;

			case 3:
				_state = STATE.TOUCH_PAN;
				_panStart = _panEnd = _this.getMouseOnScreen( event.touches[ 0 ].pageX, event.touches[ 0 ].pageY );
				break;

			default:
				_state = STATE.NONE;

		}

	}

	function touchmove( event ) {

		if ( _this.enabled === false ) return;

		event.preventDefault();
		event.stopPropagation();

		switch ( event.touches.length ) {

			case 1:
				_rotateEnd = _this.getMouseProjectionOnBall( event.touches[ 0 ].pageX, event.touches[ 0 ].pageY );
				break;

			case 2:
				var dx = event.touches[ 0 ].pageX - event.touches[ 1 ].pageX;
				var dy = event.touches[ 0 ].pageY - event.touches[ 1 ].pageY;
				_touchZoomDistanceEnd = Math.sqrt( dx * dx + dy * dy )
				break;

			case 3:
				_panEnd = _this.getMouseOnScreen( event.touches[ 0 ].pageX, event.touches[ 0 ].pageY );
				break;

			default:
				_state = STATE.NONE;

		}

	}

	function touchend( event ) {

		if ( _this.enabled === false ) return;

		switch ( event.touches.length ) {

			case 1:
				_rotateStart = _rotateEnd = _this.getMouseProjectionOnBall( event.touches[ 0 ].pageX, event.touches[ 0 ].pageY );
				break;

			case 2:
				_touchZoomDistanceStart = _touchZoomDistanceEnd = 0;
				break;

			case 3:
				_panStart = _panEnd = _this.getMouseOnScreen( event.touches[ 0 ].pageX, event.touches[ 0 ].pageY );
				break;

		}

		_state = STATE.NONE;

	}

	this.domElement.addEventListener( 'contextmenu', function ( event ) { event.preventDefault(); }, false );

	this.domElement.addEventListener( 'mousedown', mousedown, false );
	this.domElement.addEventListener( 'mousewheel', mousewheel, false );
	this.domElement.addEventListener( 'DOMMouseScroll', mousewheel, false ); // firefox

	this.domElement.addEventListener( 'touchstart', touchstart, false );
	this.domElement.addEventListener( 'touchend', touchend, false );
	this.domElement.addEventListener( 'touchmove', touchmove, false );

	//window.addEventListener( 'keydown', keydown, false );
	//window.addEventListener( 'keyup', keyup, false );

	this.handleResize();

};





///////////////////////////////////////////////////////////////////////////////////////////////////
function create_point_light_with_flare( args ) {
	var light = new THREE.PointLight( 0xffffff );
	light.color.r = args.r;
	light.color.g = args.g;
	light.color.b = args.b;

	if (args.intensity===undefined) { args.intensity=0.15; }
	light.intensity = args.intensity;
	light.position.x = args.x;
	light.position.y = args.y;
	light.position.z = args.z;
	scene.add( light );

	//var flareColor = new THREE.Color( 0xffffff );
	//flareColor.copy( light.color );
	//THREE.ColorUtils.adjustHSV( flareColor, 0, -Math.random(), Math.random() );

	var lensFlare = new THREE.LensFlare( 
		textureFlare0, 
		224, 		// size in pixels (-1 use texture width)
		0.0, 		// distance (0-1) from light source (0=at light source)
		THREE.AdditiveBlending, 
		light.color
	);

	lensFlare.add( textureFlare2, 32, 0.0, THREE.AdditiveBlending );
	lensFlare.add( textureFlare2, 24, 0.0, THREE.AdditiveBlending );
	lensFlare.add( textureFlare2, 16, 0.0, THREE.AdditiveBlending );

	lensFlare.add( textureFlare3, 60, 0.6, THREE.AdditiveBlending );
	lensFlare.add( textureFlare3, 70, 0.7, THREE.AdditiveBlending );
	lensFlare.add( textureFlare3, 20, 0.9, THREE.AdditiveBlending );
	lensFlare.add( textureFlare3, 170, 1.0, THREE.AdditiveBlending );

	//lensFlare.customUpdateCallback = lensFlareUpdateCallback;
	lensFlare.position = light.position;
	light.flare = lensFlare;
	scene.add( lensFlare );

	return light
}

function create_point_light_with_flares( num ) {
	for ( var i=0; i<num; i ++ ) {
		create_point_light_with_flare({
			x: Math.random()*50,
			y: (Math.random()*50)+10,
			z: (Math.random()*100),
			r: 1.0,
			g: 1.0,
			b: 1.0
		});
	}
}


UserAPI.initialize = function( renderer_params ) {
	console.log(">> THREE init");
	UserAPI.initialized = true;

	container = document.createElement( 'div' );
	document.body.appendChild( container );

	// scene //
	scene = new THREE.Scene();
	//scene.fog = new THREE.FogExp2( 0xefd1b5, 0.0025 );

	// camera //
	camera = new THREE.PerspectiveCamera( 45, window.innerWidth / (window.innerHeight-10), 0.5, 1e7 );
	camera.position.set( 0, 1, -10 );
	camera.position_target = camera.position.clone();
	camera.use_position_constraint = true;
	scene.add( camera );
	UserAPI.camera = camera;

	CONTROLLER = new CameraController( camera );
	UserAPI.camera_controllers.default = CONTROLLER;

	// Grid //
	var line_material = new THREE.LineBasicMaterial( { color: 0x000000, opacity: 0.2 } ),
	geometry = new THREE.Geometry(),
	floor = -0.04, step = 1, size = 4;
	for ( var i = 0; i <= size / step * 2; i ++ ) {
		geometry.vertices.push( new THREE.Vector3( - size, floor, i * step - size ) );
		geometry.vertices.push( new THREE.Vector3(   size, floor, i * step - size ) );
		geometry.vertices.push( new THREE.Vector3( i * step - size, floor, -size ) );
		geometry.vertices.push( new THREE.Vector3( i * step - size,  floor, size ) );
	}
	var line = new THREE.Line( geometry, line_material, THREE.LinePieces );
	scene.add( line );
	UserAPI.grid = line;

	// LIGHTS //
	ambientLight = new THREE.AmbientLight( 0x000011 );
	scene.add( ambientLight );
	UserAPI.ambient_light = ambientLight;

	var sunIntensity = 0.75;
	spotLight = new THREE.SpotLight( 0xffffff, sunIntensity );
	spotLight.position.set( 0, 500, 10 );
	spotLight.target.position.set( 0, 0, 0 );
	spotLight.castShadow = true;
	spotLight.shadowCameraNear = 480;
	spotLight.shadowCameraFar = camera.far;
	spotLight.shadowCameraFov = 30;
	spotLight.shadowBias = 0.001;
	spotLight.shadowMapWidth = 512;
	spotLight.shadowMapHeight = 512;
	spotLight.shadowDarkness = 0.1 * sunIntensity;
	scene.add( spotLight );
	UserAPI.sun = spotLight;

	// renderer //
	renderer = new THREE.WebGLRenderer( renderer_params );
	renderer.setSize( window.innerWidth, window.innerHeight-10 );
	container.appendChild( renderer.domElement );

	UserAPI.renderer = renderer;

	renderer.gammaInput = true;
	renderer.gammaOutput = true;
	if (USE_SHADOWS) {
		renderer.shadowMapEnabled = true;
		renderer.shadowMapSoft = true;
		//renderer.shadowMapAutoUpdate = false;		// EVIL!
	}
	renderer.setClearColor( {r:0.4,g:0.4,b:0.4}, 1.0 )
	renderer.physicallyBasedShading = true;		// allows per-pixel shading

	renderer.sortObjects = true;
	//renderer.autoUpdateScene = false;	// LOD


	console.log(">> THREE init complete <<");
	return {renderer:renderer, scene:scene, camera:camera}
}

UserAPI['update_modifiers'] = function() {
	// subdiv modifier //
	for (n in Objects) {
		var lod = Objects[ n ];

		if (USE_MODIFIERS && lod && lod.base_mesh && lod.LODs[0].object3D.visible) {
			//if (mesh === SELECTED) { mesh.visible=true; }	// show hull
			//else { mesh.visible=false; }	// hide hull

			if (lod.dirty_modifiers ) {
				lod.dirty_modifiers = false;

				var subsurf = 0;
				if ( lod.subsurf ) { subsurf=lod.subsurf; }
				else if ( lod.multires ) { subsurf=1; }

				// update hull //
				//mesh.geometry.vertices = mesh.geometry_base.vertices;
				//mesh.geometry.NeedUpdateVertices = true;

				var modifier = new THREE.SubdivisionModifier( subsurf );
				var geo = lod.base_mesh.geometry_base.clone();
				geo.mergeVertices();		// BAD?  required? //
				modifier.modify( geo );

				geo.NeedUpdateTangents = true;
				geo.computeTangents();		// requires UV's
				//geo.computeFaceNormals();
				//geo.computeVertexNormals();

				//if ( mesh.children.length ) { mesh.remove( mesh.children[0] ); }
				var hack = new THREE.Mesh(geo, lod.shader)
				hack.castShadow = true;
				hack.receiveShadow = true;
				hack.name = lod.name;							// required for picking
				MESHES[ MESHES.indexOf(lod.children[1]) ] = hack;	// required for picking

				lod.remove( lod.children[1] );
				lod.LODs[ 0 ].object3D = hack;
				lod.add( hack );

			} else if (lod.auto_subdivision){

				if (distance_to_camera(lod) < lod.LODs[0].visibleAtDistance/2) {

					var subsurf = 0;
					if ( lod.subsurf ) { subsurf=lod.subsurf; }
					else if ( lod.multires ) { subsurf=1; }
					subsurf ++;

					var modifier = new THREE.SubdivisionModifier( subsurf );
					var geo = THREE.GeometryUtils.clone( lod.base_mesh.geometry_base );
					geo.mergeVertices();		// BAD?  required? //
					modifier.modify( geo );

					geo.NeedUpdateTangents = true;
					geo.computeTangents();		// requires UV's

					var hack = new THREE.Mesh(geo, lod.shader)
					hack.castShadow = true;
					hack.receiveShadow = true;

					lod.remove( lod.children[1] );
					lod.LODs[ 0 ].object3D = hack;
					lod.add( hack );

				} else {

					var subsurf = 0;
					if ( lod.subsurf ) { subsurf=lod.subsurf; }
					else if ( lod.multires ) { subsurf=1; }

					var modifier = new THREE.SubdivisionModifier( subsurf );
					var geo = THREE.GeometryUtils.clone( lod.base_mesh.geometry_base );
					geo.mergeVertices();		// BAD?  required? //
					modifier.modify( geo );

					geo.NeedUpdateTangents = true;
					geo.computeTangents();		// requires UV's

					var hack = new THREE.Mesh(geo, lod.shader)
					hack.castShadow = true;
					hack.receiveShadow = true;

					lod.remove( lod.children[1] );
					lod.LODs[ 0 ].object3D = hack;
					lod.add( hack );
				}
			}
		}
	}
}


UserAPI.animate = function() {
	requestAnimationFrame( UserAPI.animate );  // requestAnimationFrame tries to maintain 60fps, but can fail to render, setInterval is safer.
	render();
}


///////////////////// init and run ///////////////////
var ws;
var _ws_ticker = false;
function on_message(e) {
	//console.log('on_message');
	// check first byte, if null then read following binary data //
	var length = ws.rQlen();
	if (UserAPI.initialized) {
		_ws_ticker = ! _ws_ticker;

		if (Input.object) {
			var a = '|';
			if (_ws_ticker) {
				a = '.';
			}
			label_object(
				undefined, //INPUT_OBJECT.meshes[0].geometry,
				Input.object,
				Input.get_text_with_cursor(a), // text
				undefined, // title
				undefined,  // special case to force flipped text
				Input.object.custom_attributes.text_scale
			);

		}

		switch( ws.rQpeek8() ) {
			case 0:
				on_binary_message( ws.rQshiftBytes().slice(1,length) );
				break;
			default:
				on_json_message( ws.rQshiftStr() );
				break;
		}
	} else {
		on_json_message( ws.rQshiftStr() );
	}
}

UserAPI['create_websocket'] = function() {
	ws = new Websock(); 	// from the websockify API
	ws.on('message', on_message);

	function on_open(e) {
		console.log(">> WebSockets.onopen");
		window.setInterval( update_player_view, 1000/8.0 );

	}
	ws.on('open', on_open);

	function on_close(e) {
		console.log(">> WebSockets.onclose");
		UserAPI.compositor.film.uniforms['nIntensity'].value = 0.8;
	}
	ws.on('close', on_close);

	var a = 'ws://' + HOST + ':' + HOST_PORT;
	if (WEBSOCKET_PATH) { a += '/'+WEBSOCKET_PATH; } // to trigger a custom response from websocket server, WEBSOCKET_PATH can be defined by the server.
	console.log('connecting to:'+a);
	ws.open( a );	// global var "HOST" and "HOST_PORT" is injected by the server, (the server must know its IP over the internet and use that for non-localhost clients
	console.log('websocket open OK');

	//UserAPI.animate(); // start animation loop

}

function update_player_view() {
	if (UserAPI.initialized) {
		var arr = vec3_to_bytes( camera.position.x, (-camera.position.z), camera.position.y );
		arr = arr.concat(
			vec3_to_bytes( CONTROLLER.target.x, (-CONTROLLER.target.z), CONTROLLER.target.y )
		);
		ws.send( [0].concat(arr) ); // not part of simple action api - prefixed with null byte
		ws.flush();		
	}
}


//init();
//animate();
UserAPI.create_websocket();
