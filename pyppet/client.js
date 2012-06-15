// WebGL Pyppet Client
// Blender Research Lab. PH (brett hartshorn)
// License: BSD
/*
This error can happen if you assign the same shader to different meshes,
or forget to computeTangents before assignment.
 [..:ERROR:gles2_cmd_decoder.cc(4561)] glDrawXXX: attempt to access out of range vertices
*/



var DEBUG = false;
var USE_MODIFIERS = true;
var USE_SHADOWS = true;

var DISP_BIAS_MAGIC = 0.07;
var DISP_SCALE_MAGIC = 1.0;


var projector = new THREE.Projector();	// for picking
var mouse = { x: 0, y: 0 };				// for picking
var INTERSECTED = null;				// for picking
var testing;

var SELECTED = null;

var WIRE_MATERIAL = new THREE.MeshLambertMaterial(
	{ color: 0x000000, wireframe: true, wireframeLinewidth:1, polygonOffset:true, polygonOffsetFactor:1 }
);

var SCREEN_WIDTH = window.innerWidth;
var SCREEN_HEIGHT = window.innerHeight - 10;


ws = new Websock();
ws.open( 'ws://' + HOST + ':8081' );	// global var "HOST" is injected by the server, (the server must know its IP over the internet and use that for non-localhost clients


var textureFlare0 = THREE.ImageUtils.loadTexture( "/textures/lensflare/lensflare0.png" );
var textureFlare2 = THREE.ImageUtils.loadTexture( "/textures/lensflare/lensflare2.png" );
var textureFlare3 = THREE.ImageUtils.loadTexture( "/textures/lensflare/lensflare3.png" );


var Objects = {};
var LIGHTS = {};
var METABALLS = {};
var CURVES = {};
var MESHES = [];	// list for intersect checking - not a dict because LOD's share names

var dbugmsg = null;



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
			ob.segments_v+1, 	// using curve.bevel_resolution
			spline.closed, 
			false
		);

		// 3d shape
		var tubeMesh = THREE.SceneUtils.createMultiMaterialObject(geometry, [
		  new THREE.MeshLambertMaterial({
		      color: 0xff00ff,
		      opacity: (geometry.debug) ? 0.2 : 0.8,
		      transparent: true
		  }),
		 new THREE.MeshBasicMaterial({
		    color: 0x000000,
		    opacity: 0.5,
		    wireframe: true
		})]);

		parent.add( tubeMesh );
	}
}

function on_message(e) {
	var data = ws.rQshiftStr();
	var msg = JSON.parse( data );
	dbugmsg = msg;

	for (var name in msg['curves']) {
		if ( name in CURVES == false ) {
			console.log('>> new curve');
			CURVES[ name ] = new THREE.Object3D();
			scene.add( CURVES[name] );
			CURVES[name].useQuaternion = true;
		}
		var parent = CURVES[ name ];
		var ob = msg['curves'][name];

		if ( parent.children.length ) parent.remove( parent.children[0] );  // TODO remove all children

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


	}

	for (var name in msg['metas']) {
		if ( name in METABALLS == false ) {
			console.log('>> new metaball');
			var mat = new THREE.MeshPhongMaterial( 
				{ color: 0x000000, specular: 0x888888, ambient: 0x000000, shininess: 250, perPixel: true }
			);
			var resolution = 32;
			var meta = new THREE.MarchingCubes( resolution, mat );

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
				ball.x+0.5, ball.z+0.5, ball.y+0.5,
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

			if (USE_MODIFIERS && m.base_mesh) {
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
		fx.enabled = msg['FX'][name][0];	// something BUGGY here TODO
		var uniforms = msg['FX'][name][1];
		if (fx.uniforms) {
			for (var n in uniforms) { fx.uniforms[ n ].value = uniforms[ n ]; }
		}
		else {	// BloomPass
			for (var n in uniforms) { fx.screenUniforms[ n ].value = uniforms[ n ]; }
		}
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

var dbugdae = null;
function on_collada_ready( collada ) {
	console.log( '>> collada loaded' );
	dbugdae = collada;
	var _mesh = collada.scene.children[0];
	_mesh.useQuaternion = true;
	_mesh.updateMatrix();
	_mesh.matrixAutoUpdate = false;
	MESHES.push( _mesh );

	if ( Objects[_mesh.name] ) {
		// SECOND LOAD: loading LOD base level //
		var lod = Objects[ _mesh.name ];

		_mesh.position.set(0,0,0);
		_mesh.scale.set(1,1,1);
		_mesh.quaternion.set(0,0,0,1);
		_mesh.updateMatrix();

		lod.addLevel( _mesh, 8 );
		lod.base_mesh = _mesh;		// subdiv mod uses: lod.base_mesh.geometry_base

		if (USE_SHADOWS) {
			_mesh.castShadow = true;
			_mesh.receiveShadow = true;
		}

		if (USE_MODIFIERS) {
			_mesh.geometry.dynamic = true;		// required
			_mesh.geometry_base = THREE.GeometryUtils.clone(_mesh.geometry);
			//_mesh.material = WIRE_MATERIAL;
		}

		_mesh.geometry.computeTangents();		// requires UV's

		// hijack material color to pass info from blender //
		if (_mesh.material.color.r) {
			lod.multires = true;
			lod.has_displacement = true;
		} else {
			lod.multires = false;
			lod.has_displacement = false;
		}
		if (_mesh.material.color.g) {	// mesh deformed with an armature will not have AO
			lod.has_AO = true;
		} else {
			lod.has_AO = false;
		}
		//if (_mesh.material.color.b) { lod.auto_subdivision = true; }
		//else { lod.auto_subdivison = false; }
		lod.auto_subdivision = true;	// hijack material hack broken?


		lod.shader = create_normal_shader(
			lod.name,
			lod.has_displacement,
			lod.has_AO,
			on_texture_ready		// allows progressive texture loading
		);
		_mesh.material = lod.shader;


	} else {
		// FIRST LOAD: loading LOD far level //
		//_mesh.material.vertexColors = THREE.VertexColors;	// not a good idea
		_mesh.geometry.computeTangents();		// requires UV's
		_mesh.material = create_normal_shader(
			_mesh.name,
			false,				// displacement
			false,				// AO
			undefined,			// on loaded callback
			'/bake/LOD/'
		);


		var lod = new THREE.LOD();
		lod.name = _mesh.name;
		lod.base_mesh = null;
		lod.useQuaternion = true;			// ensure Quaternion
		lod.has_progressive_textures = false;	// enabled from websocket stream
		// TODO best performance, no UV's, no textures, vertex colors?
		lod.shader = null;
		lod.dirty_modifiers = true;

		lod.position.copy( _mesh.position );
		lod.scale.copy( _mesh.scale );
		lod.quaternion.copy( _mesh.quaternion );

		_mesh.position.set(0,0,0);
		_mesh.scale.set(1,1,1);
		_mesh.quaternion.set(0,0,0,1);
		_mesh.updateMatrix();

		lod.addLevel( _mesh, 12 );
		lod.updateMatrix();
		//mesh.matrixAutoUpdate = false;

		Objects[ lod.name ] = lod;
		scene.add( lod );

		var loader = new THREE.ColladaLoader();
		loader.options.convertUpAxis = true;
		loader.options.centerGeometry = true;
		loader.load(
			'/objects/'+lod.name+'.dae?hires', 
			on_collada_ready
		);
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


function create_normal_shader( name, displacement, AO, callback, prefix ) {
	// material parameters
	if (prefix === undefined) prefix = '/bake/'

	var ambient = 0x111111, diffuse = 0xbbbbbb, specular = 0x171717, shininess = 50;
	var shader = THREE.ShaderUtils.lib[ "normal" ];
	var uniforms = THREE.UniformsUtils.clone( shader.uniforms );

	uniforms[ "tDiffuse" ].texture = THREE.ImageUtils.loadTexture( prefix+name+'.jpg?TEXTURE|64', undefined, callback );
	uniforms[ "tNormal" ].texture = THREE.ImageUtils.loadTexture( prefix+name+'.jpg?NORMALS|128', undefined, callback );
	if (AO) {
		uniforms[ "tAO" ].texture = THREE.ImageUtils.loadTexture( prefix+name+'.jpg?AO|64', undefined, callback );
	}
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
		uniforms[ "tDisplacement" ].texture = THREE.ImageUtils.loadTexture( prefix+name+'.jpg?DISPLACEMENT|256', undefined, callback );
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




ws.on('message', on_message);

function on_open(e) {
	console.log(">> WebSockets.onopen");
	setTimeout( update_server, 1000 );
}
ws.on('open', on_open);

function on_close(e) {
	console.log(">> WebSockets.onclose");
}
ws.on('close', on_close);

function update_server() {
	THREE.ImageUtils.loadTexture(
		'/RPC/player/'+camera.position.x+','+(-camera.position.z)+','+camera.position.y, 
		undefined, on_texture_ready );
	setTimeout( update_server, 3000 );

}

//////////////////////////////////////////////////////////////////////
var container;
var camera, scene, renderer;
var spotLight, ambientLight;
var CONTROLLER;

function init() {
	console.log(">> THREE init");

	container = document.createElement( 'div' );
	document.body.appendChild( container );

	// scene //
	scene = new THREE.Scene();
	//scene.fog = new THREE.FogExp2( 0xefd1b5, 0.0025 );

	// camera //
	camera = new THREE.PerspectiveCamera( 45, window.innerWidth / (window.innerHeight-10), 0.5, 2000 );
	camera.position.set( 0, 4, 10 );
	scene.add( camera );

	CONTROLLER = new MyController( camera );

	// Grid //
	var line_material = new THREE.LineBasicMaterial( { color: 0x000000, opacity: 0.2 } ),
	geometry = new THREE.Geometry(),
	floor = -0.04, step = 1, size = 14;
	for ( var i = 0; i <= size / step * 2; i ++ ) {
		geometry.vertices.push( new THREE.Vector3( - size, floor, i * step - size ) );
		geometry.vertices.push( new THREE.Vector3(   size, floor, i * step - size ) );
		geometry.vertices.push( new THREE.Vector3( i * step - size, floor, -size ) );
		geometry.vertices.push( new THREE.Vector3( i * step - size,  floor, size ) );
	}
	var line = new THREE.Line( geometry, line_material, THREE.LinePieces );
	scene.add( line );

	// LIGHTS //
	ambientLight = new THREE.AmbientLight( 0x111111 );
	scene.add( ambientLight );

	var sunIntensity = 1.0;
	spotLight = new THREE.SpotLight( 0xffffff, sunIntensity );
	spotLight.position.set( 0, 500, 10 );
	spotLight.target.position.set( 0, 0, 0 );
	spotLight.castShadow = true;
	spotLight.shadowCameraNear = 480;
	spotLight.shadowCameraFar = camera.far;
	spotLight.shadowCameraFov = 30;
	spotLight.shadowBias = 0.001;
	spotLight.shadowMapWidth = 2048;
	spotLight.shadowMapHeight = 2048;
	spotLight.shadowDarkness = 0.3 * sunIntensity;
	scene.add( spotLight );


	// renderer //
	renderer = new THREE.WebGLRenderer( { maxLights: 8, antialias: true } );
	renderer.setSize( window.innerWidth, window.innerHeight-10 );
	container.appendChild( renderer.domElement );

	renderer.gammaInput = true;
	renderer.gammaOutput = true;
	if (USE_SHADOWS) {
		renderer.shadowMapEnabled = true;
		renderer.shadowMapSoft = true;
		//renderer.shadowMapAutoUpdate = false;		// EVIL!
	}
	renderer.setClearColor( {r:0.24,g:0.24,b:0.24}, 1.0 )
	renderer.physicallyBasedShading = true;		// allows per-pixel shading

	renderer.sortObjects = false;		// LOD
	//renderer.autoUpdateScene = false;	// LOD

	if (DEBUG==false) {
		setupFX( renderer, scene, camera );
		//setupDOF( renderer );
		//setupGodRays( renderer );
	}
}


var DEPTH_MATERIAL;
var postprocessing = { enabled  : true };
var materialDepth;

function setupGodRays( renderer ) {
	materialDepth = new THREE.MeshDepthMaterial();
	var materialScene = new THREE.MeshBasicMaterial( { color: 0x000000, shading: THREE.FlatShading } );


	renderer.sortObjects = false;
	renderer.autoClear = false;
	renderer.setClearColorHex( bgColor, 1 );

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

function setupDOF( renderer ) {
	DEPTH_MATERIAL = new THREE.MeshDepthMaterial();

	//renderer.sortObjects = false;
	//renderer.autoClear = false;

	postprocessing.scene = new THREE.Scene();

	postprocessing.camera = new THREE.OrthographicCamera( window.innerWidth / - 2, window.innerWidth / 2,  window.innerHeight / 2, window.innerHeight / - 2, -10000, 10000 );
	postprocessing.camera.position.z = 100;

	postprocessing.scene.add( postprocessing.camera );

	var pars = { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, format: THREE.RGBFormat };
	postprocessing.rtTextureDepth = new THREE.WebGLRenderTarget( 
		SCREEN_WIDTH, 
		SCREEN_HEIGHT,
		pars 
	);
	postprocessing.rtTextureColor = new THREE.WebGLRenderTarget( 
		SCREEN_WIDTH, 
		SCREEN_HEIGHT,
		pars 
	);

	var bokeh_shader = THREE.ShaderExtras[ "bokeh" ];

	postprocessing.bokeh_uniforms = THREE.UniformsUtils.clone( bokeh_shader.uniforms );

	postprocessing.bokeh_uniforms[ "tColor" ].texture = postprocessing.rtTextureColor;
	postprocessing.bokeh_uniforms[ "tDepth" ].texture = postprocessing.rtTextureDepth;
	postprocessing.bokeh_uniforms[ "focus" ].value = 2.1;
	postprocessing.bokeh_uniforms[ "aspect" ].value = SCREEN_WIDTH / SCREEN_HEIGHT;

	postprocessing.materialBokeh = new THREE.ShaderMaterial( {
		uniforms: postprocessing.bokeh_uniforms,
		vertexShader: bokeh_shader.vertexShader,
		fragmentShader: bokeh_shader.fragmentShader

	} );

	postprocessing.quad = new THREE.Mesh( new THREE.PlaneGeometry( window.innerWidth, window.innerHeight ), postprocessing.materialBokeh );
	postprocessing.quad.position.z = - 500;
	postprocessing.scene.add( postprocessing.quad );
}




var FX = {};
var composer;

function setupFX( renderer, scene, camera ) {
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


	FX['fxaa'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "fxaa" ] );
	fx.uniforms[ 'resolution' ].value.set( 1 / SCREEN_WIDTH, 1 / SCREEN_HEIGHT );
	composer.addPass( fx );

	//FX['ssao'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "ssao" ] );	// TODO find tutorial
	//composer.addPass( fx );


	FX['dots'] = fx = new THREE.DotScreenPass( new THREE.Vector2( 0, 0 ), 0.5, 1.8 );	// center, angle, size
	composer.addPass( fx );


	FX['vignette'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "vignette" ] );
	composer.addPass( fx );

	FX['bloom'] = fx = new THREE.BloomPass( 1.1 );
	composer.addPass( fx );


	FX['glowing_dots'] = fx = new THREE.DotScreenPass( new THREE.Vector2( 0, 0 ), 0.01, 0.23 );
	composer.addPass( fx );


	// fake DOF //
	var bluriness = 3;
	FX['blur_horizontal'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "horizontalTiltShift" ] );
	fx.uniforms[ 'h' ].value = bluriness / SCREEN_WIDTH;
	fx.uniforms[ 'r' ].value = 0.5;
	composer.addPass( fx );

	FX['blur_vertical'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "verticalTiltShift" ] );
	fx.uniforms[ 'v' ].value = bluriness / SCREEN_HEIGHT;
	fx.uniforms[ 'r' ].value = 0.5;
	composer.addPass( fx );

	//			noise intensity, scanline intensity, scanlines, greyscale
	FX['noise'] = fx = new THREE.FilmPass( 0.01, 0.5, SCREEN_HEIGHT / 1.5, false );
	composer.addPass( fx );


	//			noise intensity, scanline intensity, scanlines, greyscale
	FX['film'] = fx = new THREE.FilmPass( 10.0, 0.1, SCREEN_HEIGHT / 3, false );
	composer.addPass( fx );


	////////////////////////////////////// dummy //////////////////////////////////
	FX['dummy'] = fx = new THREE.ShaderPass( THREE.ShaderExtras[ "screen" ] );	// ShaderPass copies uniforms
	fx.uniforms['opacity'].value = 1.0;	// ensure nothing happens
	fx.renderToScreen = true;	// this means that this is final pass and render it to the screen.
	composer.addPass( fx );


	return composer;
}



function animate() {
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
				var geo = THREE.GeometryUtils.clone( lod.base_mesh.geometry_base );
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

	requestAnimationFrame( animate );
	if (DEBUG==true) { render_debug(); }
	else { render(); }
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
		console.log(">> resize view");
	}
}



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
	CONTROLLER.update( delta );

	// render shadow map
	//renderer.autoUpdateObjects = false;
	//renderer.initWebGLObjects( scene );
	//renderer.updateShadowMap( scene, camera );


/*
	// render cube map
	mesh.visible = false;
	renderer.autoClear = true;
	cubeCamera.updatePosition( mesh.position );
	cubeCamera.updateCubeMap( renderer, scene );
	renderer.autoClear = false;
	mesh.visible = true;
*/


	// render scene
	//scene.overrideMaterial = DEPTH_MATERIAL;
	//FX['BASE'].overrideMaterial = DEPTH_MATERIAL;
	//renderer.autoUpdateObjects = true;

	scene.updateMatrixWorld();
	THREE.SceneUtils.traverseHierarchy(
		scene, 
		function ( node ) { if ( node instanceof THREE.LOD ) node.update( camera ) } 
	);

	composer.render( 0.1 );
/*
	renderer.clear();

	// Render scene into texture

	scene.overrideMaterial = null;
	renderer.render( scene, camera, postprocessing.rtTextureColor, true );

	// Render depth into texture

	scene.overrideMaterial = DEPTH_MATERIAL;
	renderer.render( scene, camera, postprocessing.rtTextureDepth, true );

	// Render bokeh composite
	renderer.render( postprocessing.scene, postprocessing.camera );
*/

}

var sunPosition = new THREE.Vector3( 0, 1000, -1000 );
var screenSpacePosition = new THREE.Vector3();
var orbitRadius = 200;
var bgColor = 0x000511;
var sunColor = 0xffee00;

var margin = 100;
var height = window.innerHeight - 2 * margin;


function render_godrays() {	// TODO how to combine godrays and composer
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
// merge TrackballControls.js and RollControls.js into single Controller //

MyController = function ( object, domElement ) {
	this.MODE = 'TRACK'		// TRACK, FREE, SPIN

	this.set_mode = function( mode ) {
		this.MODE = mode;
		if (this.MODE=='FREE') { this.object.matrixAutoUpdate = false; }
		else { this.object.matrixAutoUpdate = true; }
		distance=this.object.position.length();
	};
	this.update = function(delta) {
		var camera = this.object;

		if (this.MODE=='TRACK') { this.update_TRACK(); }
		else if (this.MODE=='FREE') { this.update_FREE(delta); }
		else if (this.MODE=='SPIN') {
			//var timer = Date.now() * 0.0005;
			//var x = Math.abs(raw_mouseX * 0.001) + 1.0;
			var x = raw_mouseX * 0.1;
			var y = raw_mouseY * 0.1;
			//camera.position.x = Math.cos( timer ) * distance * x;
			//camera.position.z = Math.sin( timer ) * distance * x;
			camera.position.x += ( x - camera.position.x ) * 0.01;
			camera.position.y += ( - y - camera.position.y ) * 0.01;
			camera.lookAt( this.target );
		}
		else if (this.MODE=='RANDOM') {
			if ( this.randomize ) {
				this.randomize = false;
				var a = Math.random() * 3;
				var d = (Math.random() * 3) + 0.5
				camera.position.x = Math.cos( a ) * distance * d;
				camera.position.z = Math.sin( a ) * distance * d;
				camera.position.y = (Math.random()-0.25) * 4;
				var t = this.target.clone();
				t.x += (Math.random()-0.5) * (Math.random()*10);
				t.y += (Math.random()-0.25)  * (Math.random()*4);
				t.z += (Math.random()-0.5) * (Math.random()*10);
				camera.lookAt( t );
				camera.rotation.z = Math.random()-0.5;
			}
		}
	};

	// SPIN //
	var raw_mouseX = 0, raw_mouseY = 0;
	var distance = 10.0;
	this.randomize = false;

	/**	THREE.TrackballControls
	 * @author Eberhard Graether / http://egraether.com/
	 */

	var _this = this,
	STATE = { NONE : -1, ROTATE : 1, ZOOM : 0, PAN : 2 };

	this.object = object;
	this.domElement = ( domElement !== undefined ) ? domElement : document;

	// API
	this.enabled = true;
	this.screen = { width: window.innerWidth, height: window.innerHeight, offsetLeft: 0, offsetTop: 0 };
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
	this.target = new THREE.Vector3( 0, 0, 0 );
	var _keyPressed = false,
	_state = STATE.NONE,
	_eye = new THREE.Vector3(),
	_rotateStart = new THREE.Vector3(),
	_rotateEnd = new THREE.Vector3(),
	_zoomStart = new THREE.Vector2(),
	_zoomEnd = new THREE.Vector2(),
	_panStart = new THREE.Vector2(),
	_panEnd = new THREE.Vector2();


	//////////////////////////// RollControls API //////////////////////////
	this.mouseLook = true;
	this.autoForward = false;
	this.lookSpeed = 1;
	this.movementSpeed = 1;
	this.rollSpeed = 1;
	this.constrainVertical = [ -0.9, 0.9 ];
	// disable default target object behavior
//	this.object.matrixAutoUpdate = false;
	// internals
	this.forward = new THREE.Vector3( 0, 0, 1 );
	this.roll = 0;
	var xTemp = new THREE.Vector3();
	var yTemp = new THREE.Vector3();
	var zTemp = new THREE.Vector3();
	var rollMatrix = new THREE.Matrix4();
	var doRoll = false, rollDirection = 1, forwardSpeed = 0, sideSpeed = 0, upSpeed = 0;
	var mouseX = 0, mouseY = 0;
	var windowHalfX = window.innerWidth / 2;
	var windowHalfY = window.innerHeight / 2;


	// methods
	this.update_TRACK = function() {
		_eye.copy( _this.object.position ).subSelf( this.target );
		if ( !_this.noRotate ) {
			_this.rotateCamera();
		}
		if ( !_this.noZoom ) {
			_this.zoomCamera();
		}
		if ( !_this.noPan ) {
			_this.panCamera();
		}
		_this.object.position.add( _this.target, _eye );
		_this.checkDistances();
		_this.object.lookAt( _this.target );

	};



	this.getMouseOnScreen = function( clientX, clientY ) {
		return new THREE.Vector2(
			( clientX - _this.screen.offsetLeft ) / _this.radius * 0.5,
			( clientY - _this.screen.offsetTop ) / _this.radius * 0.5
		);
	};

	this.getMouseProjectionOnBall = function( clientX, clientY ) {
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
		_eye.copy( _this.object.position ).subSelf( _this.target );
		var projection = _this.object.up.clone().setLength( mouseOnBall.y );
		projection.addSelf( _this.object.up.clone().crossSelf( _eye ).setLength( mouseOnBall.x ) );
		projection.addSelf( _eye.setLength( mouseOnBall.z ) );
		return projection;

	};

	this.rotateCamera = function() {
		var angle = Math.acos( _rotateStart.dot( _rotateEnd ) / _rotateStart.length() / _rotateEnd.length() );

		if ( angle ) {
			var axis = ( new THREE.Vector3() ).cross( _rotateStart, _rotateEnd ).normalize(),
			quaternion = new THREE.Quaternion();
			angle *= _this.rotateSpeed;
			quaternion.setFromAxisAngle( axis, -angle );
			quaternion.multiplyVector3( _eye );
			quaternion.multiplyVector3( _this.object.up );
			quaternion.multiplyVector3( _rotateEnd );

			if ( _this.staticMoving ) {
				_rotateStart = _rotateEnd;
			} else {
				quaternion.setFromAxisAngle( axis, angle * ( _this.dynamicDampingFactor - 1.0 ) );
				quaternion.multiplyVector3( _rotateStart );
			}
		}
	};

	this.zoomCamera = function() {
		var factor = 1.0 + ( _zoomEnd.y - _zoomStart.y ) * _this.zoomSpeed;
		if ( factor !== 1.0 && factor > 0.0 ) {
			_eye.multiplyScalar( factor );
			if ( _this.staticMoving ) {
				_zoomStart = _zoomEnd;
			} else {
				_zoomStart.y += ( _zoomEnd.y - _zoomStart.y ) * this.dynamicDampingFactor;
			}
		}
	};

	this.panCamera = function() {
		var mouseChange = _panEnd.clone().subSelf( _panStart );
		if ( mouseChange.lengthSq() ) {
			mouseChange.multiplyScalar( _eye.length() * _this.panSpeed );
			var pan = _eye.clone().crossSelf( _this.object.up ).setLength( mouseChange.x );
			pan.addSelf( _this.object.up.clone().setLength( mouseChange.y ) );
			_this.object.position.addSelf( pan );
			_this.target.addSelf( pan );
			if ( _this.staticMoving ) {
				_panStart = _panEnd;
			} else {
				_panStart.addSelf( mouseChange.sub( _panEnd, _panStart ).multiplyScalar( _this.dynamicDampingFactor ) );
			}
		}
	};

	this.checkDistances = function() {
		if ( !_this.noZoom || !_this.noPan ) {
			if ( _this.object.position.lengthSq() > _this.maxDistance * _this.maxDistance ) {
				_this.object.position.setLength( _this.maxDistance );
			}
			if ( _eye.lengthSq() < _this.minDistance * _this.minDistance ) {
				_this.object.position.add( _this.target, _eye.setLength( _this.minDistance ) );
			}
		}
	};



	// listeners
	this.keydown = function( event ) {
		if ( ! _this.enabled ) return;
		console.log('keydown');
		console.log( event.keyCode );

		if (event.keyCode == 49) { _this.set_mode('TRACK'); }			// 1 key
		else if (event.keyCode == 50) { _this.set_mode('FREE'); }		// 2 key
		else if (event.keyCode == 51) { _this.set_mode('SPIN'); }		// 3 key
		else if (event.keyCode == 52) { _this.set_mode('RANDOM'); }	// 4 key

		///////////////////// TRACK ///////////////////
		if ( _state !== STATE.NONE ) {
			return;
		} else if ( event.keyCode === _this.keys[ STATE.ROTATE ] && !_this.noRotate ) {
			_state = STATE.ROTATE;
		} else if ( event.keyCode === _this.keys[ STATE.ZOOM ] && !_this.noZoom ) {
			_state = STATE.ZOOM;
		} else if ( event.keyCode === _this.keys[ STATE.PAN ] && !_this.noPan ) {
			_state = STATE.PAN;
		}
		if ( _state !== STATE.NONE ) {
			_keyPressed = true;
		}
		//////////////////// FREE ////////////////////////
		switch( event.keyCode ) {
			case 38: /*up*/
			case 87: /*W*/ forwardSpeed = 1; break;
			case 37: /*left*/
			case 65: /*A*/ sideSpeed = -1; break;
			case 40: /*down*/
			case 83: /*S*/ forwardSpeed = -1; break;
			case 39: /*right*/
			case 68: /*D*/ sideSpeed = 1; break;
			case 81: /*Q*/ doRoll = true; rollDirection = 1; break;
			case 69: /*E*/ doRoll = true; rollDirection = -1; break;
			case 82: /*R*/ upSpeed = 1; break;
			case 70: /*F*/ upSpeed = -1; break;
		}
	};


	this.keyup = function( event ) {
		if ( ! _this.enabled ) return;
		if ( _state !== STATE.NONE ) { _state = STATE.NONE; }		/////////// TRACK //////////
		////////////// FREE ///////////////
		switch( event.keyCode ) {
			case 38: /*up*/
			case 87: /*W*/ forwardSpeed = 0; break;
			case 37: /*left*/
			case 65: /*A*/ sideSpeed = 0; break;
			case 40: /*down*/
			case 83: /*S*/ forwardSpeed = 0; break;
			case 39: /*right*/
			case 68: /*D*/ sideSpeed = 0; break;
			case 81: /*Q*/ doRoll = false; break;
			case 69: /*E*/ doRoll = false; break;
			case 82: /*R*/ upSpeed = 0; break;
			case 70: /*F*/ upSpeed = 0; break;
		}
	};


	this.mouseup = function( event ) {
		if ( ! _this.enabled ) return;
		event.preventDefault();
		event.stopPropagation();

		if ( INTERSECTED ) {
			var tex = THREE.ImageUtils.loadTexture(
				'/RPC/select/'+INTERSECTED.name, undefined, on_texture_ready 
			);
			INTERSECTED.material.color.setHex( INTERSECTED.currentHex );
			INTERSECTED = null;
		}

		if (_this.MODE=='TRACK') { _state = STATE.NONE; }
		else if (_this.MODE=='FREE') {
			switch ( event.button ) {
				case 0: forwardSpeed = 0; break;
				case 2: forwardSpeed = 0; break;
			}
		}
	};


	this.mousedown = function( event ) {
		console.log('>> mouse down');
		if ( ! _this.enabled ) return;
		event.preventDefault();
		event.stopPropagation();


		if (event.button==2) {	// right click selects like in blender
			// PICKING //
			var vector = new THREE.Vector3( mouse.x, mouse.y, 1 );
			projector.unprojectVector( vector, camera );
			var ray = new THREE.Ray( camera.position, vector.subSelf( camera.position ).normalize() );

			// ray.intersectObjects only works on THREE.Particle and THREE.Mesh,
			// it will not traverse the children, that is why it fails on THREE.LOD.
			//var intersects = ray.intersectObjects( scene.children );
			var intersects = ray.intersectObjects( MESHES );
			testing = intersects;

			if ( intersects.length > 0 ) {
				for (var i=0; i < intersects.length; i ++) {
					var intersect = intersects[ i ];
					if (intersect.object.name && intersect.object.visible) {
						if ( INTERSECTED != intersect.object ) {
							INTERSECTED = intersect.object;
							INTERSECTED.currentHex = INTERSECTED.material.color.getHex();
							INTERSECTED.material.color.setHex( 0xff0000 );
							break;
						}
					}
				}
			} else { INTERSECTED = null; }
		}
		/////////////////////////////////////////////////////////////////////


		if (_this.MODE=='TRACK') { _this.mousedown_TRACK(event); }
		else if (_this.MODE=='FREE') { _this.mousedown_FREE(event); }
		randomize = true;
	};

	this.mousedown_TRACK = function( event ) {
		if ( _state === STATE.NONE ) {
			_state = event.button;
			if ( _state === STATE.ROTATE && !_this.noRotate ) {
				_rotateStart = _rotateEnd = _this.getMouseProjectionOnBall( event.clientX, event.clientY );
			} else if ( _state === STATE.ZOOM && !_this.noZoom ) {
				_zoomStart = _zoomEnd = _this.getMouseOnScreen( event.clientX, event.clientY );
			} else if ( ! _this.noPan ) {
				_panStart = _panEnd = _this.getMouseOnScreen( event.clientX, event.clientY );
			}
		}
	};
	this.mousedown_FREE = function( event ) {
		switch ( event.button ) {
			case 0: forwardSpeed = 1; break;
			case 2: forwardSpeed = -1; break;
		}
	};


	this.mousemove = function( event ) {
		if ( ! _this.enabled ) return;
		/////////////////////////////// PICKING /////////////////////////////////////
		mouse.x = ( event.clientX / window.innerWidth ) * 2 - 1;
		mouse.y = - ( event.clientY / window.innerHeight ) * 2 + 1;

		////////////////// SPIN ///////////////////
		raw_mouseX = ( event.clientX - windowHalfX );
		raw_mouseY = ( event.clientY - windowHalfY );

		////////////////// FREE ///////////////////
		mouseX = ( event.clientX - windowHalfX ) / window.innerWidth;
		mouseY = ( event.clientY - windowHalfY ) / window.innerHeight;
		///////////////// TRACK ///////////////////////////////
		if ( _keyPressed ) {
			_rotateStart = _rotateEnd = _this.getMouseProjectionOnBall( event.clientX, event.clientY );
			_zoomStart = _zoomEnd = _this.getMouseOnScreen( event.clientX, event.clientY );
			_panStart = _panEnd = _this.getMouseOnScreen( event.clientX, event.clientY );
			_keyPressed = false;
		}
		if ( _state === STATE.NONE ) {
			return;
		} else if ( _state === STATE.ROTATE && !_this.noRotate ) {
			_rotateEnd = _this.getMouseProjectionOnBall( event.clientX, event.clientY );
		} else if ( _state === STATE.ZOOM && !_this.noZoom ) {
			_zoomEnd = _this.getMouseOnScreen( event.clientX, event.clientY );
		} else if ( _state === STATE.PAN && !_this.noPan ) {
			_panEnd = _this.getMouseOnScreen( event.clientX, event.clientY );
		}
	};




	this.domElement.addEventListener( 'contextmenu', function ( event ) { event.preventDefault(); }, false );
	this.domElement.addEventListener( 'mousemove', this.mousemove, false );
	this.domElement.addEventListener( 'mousedown', this.mousedown, false );
	this.domElement.addEventListener( 'mouseup', this.mouseup, false );
	window.addEventListener( 'keydown', this.keydown, false );
	window.addEventListener( 'keyup', this.keyup, false );




	///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
	////////////////////////////////////////////	THREE.RollControls	//////////////////////////////////////////////
	/**
	 * @author mikael emtinger / http://gomo.se/
	 * @author alteredq / http://alteredqualia.com/
	 */

	this.update_FREE = function ( delta ) {

		if ( this.mouseLook ) {
			var actualLookSpeed = delta * this.lookSpeed;
			this.rotateHorizontally( actualLookSpeed * mouseX );
			this.rotateVertically( actualLookSpeed * mouseY );

		}

		var actualSpeed = delta * this.movementSpeed;
		var forwardOrAuto = ( forwardSpeed > 0 || ( this.autoForward && ! ( forwardSpeed < 0 ) ) ) ? 1 : forwardSpeed;

		this.object.translateZ( -actualSpeed * forwardOrAuto );
		this.object.translateX( actualSpeed * sideSpeed );
		this.object.translateY( actualSpeed * upSpeed );

		if( doRoll ) {
			this.roll += this.rollSpeed * delta * rollDirection;
		}

		// cap forward up / down

		if( this.forward.y > this.constrainVertical[ 1 ] ) {
			this.forward.y = this.constrainVertical[ 1 ];
			this.forward.normalize();

		} else if( this.forward.y < this.constrainVertical[ 0 ] ) {
			this.forward.y = this.constrainVertical[ 0 ];
			this.forward.normalize();

		}


		// construct unrolled camera matrix
		zTemp.copy( this.forward );
		yTemp.set( 0, 1, 0 );
		xTemp.cross( yTemp, zTemp ).normalize();
		yTemp.cross( zTemp, xTemp ).normalize();

		this.object.matrix.n11 = xTemp.x; this.object.matrix.n12 = yTemp.x; this.object.matrix.n13 = zTemp.x;
		this.object.matrix.n21 = xTemp.y; this.object.matrix.n22 = yTemp.y; this.object.matrix.n23 = zTemp.y;
		this.object.matrix.n31 = xTemp.z; this.object.matrix.n32 = yTemp.z; this.object.matrix.n33 = zTemp.z;

		// calculate roll matrix
		rollMatrix.identity();
		rollMatrix.n11 = Math.cos( this.roll ); rollMatrix.n12 = -Math.sin( this.roll );
		rollMatrix.n21 = Math.sin( this.roll ); rollMatrix.n22 =  Math.cos( this.roll );

		// multiply camera with roll
		this.object.matrix.multiplySelf( rollMatrix );
		this.object.matrixWorldNeedsUpdate = true;

		// set position
		this.object.matrix.n14 = this.object.position.x;
		this.object.matrix.n24 = this.object.position.y;
		this.object.matrix.n34 = this.object.position.z;
	};

	this.translateX = function ( distance ) {
		this.object.position.x += this.object.matrix.n11 * distance;
		this.object.position.y += this.object.matrix.n21 * distance;
		this.object.position.z += this.object.matrix.n31 * distance;
	};

	this.translateY = function ( distance ) {
		this.object.position.x += this.object.matrix.n12 * distance;
		this.object.position.y += this.object.matrix.n22 * distance;
		this.object.position.z += this.object.matrix.n32 * distance;
	};

	this.translateZ = function ( distance ) {
		this.object.position.x -= this.object.matrix.n13 * distance;
		this.object.position.y -= this.object.matrix.n23 * distance;
		this.object.position.z -= this.object.matrix.n33 * distance;
	};


	this.rotateHorizontally = function ( amount ) {
		// please note that the amount is NOT degrees, but a scale value
		xTemp.set( this.object.matrix.n11, this.object.matrix.n21, this.object.matrix.n31 );
		xTemp.multiplyScalar( amount );
		this.forward.subSelf( xTemp );
		this.forward.normalize();
	};

	this.rotateVertically = function ( amount ) {
		// please note that the amount is NOT degrees, but a scale value
		yTemp.set( this.object.matrix.n12, this.object.matrix.n22, this.object.matrix.n32 );
		yTemp.multiplyScalar( amount );
		this.forward.addSelf( yTemp );
		this.forward.normalize();
	};


};









///////////////////////////////////////////////////////////////////////////
///////////////////// init and run ///////////////////
init();
animate();

