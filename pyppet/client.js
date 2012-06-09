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
ws.open( 'ws://' + HOST + ':8081' );


var textureFlare0 = THREE.ImageUtils.loadTexture( "/textures/lensflare/lensflare0.png" );
var textureFlare2 = THREE.ImageUtils.loadTexture( "/textures/lensflare/lensflare2.png" );
var textureFlare3 = THREE.ImageUtils.loadTexture( "/textures/lensflare/lensflare3.png" );


var Objects = {};
var LIGHTS = {};

var dbugmsg = null;
function on_message(e) {
	var data = ws.rQshiftStr();
	var msg = JSON.parse( data );
	dbugmsg = msg;

	for (var name in msg['lights']) {
		var light;
		var ob = msg['lights'][ name ];

		if ( name in LIGHTS == false ) {	// Three.js bug, new lights are not added to old materials
			console.log('>> new light');

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
			m.shader.uniforms[ "uNormalScale" ].value = ob.norm;


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

			if (USE_MODIFIERS) {
				if (m != INTERSECTED) {
					m.shader.color.r = ob.color[0];
					m.shader.color.g = ob.color[1];
					m.shader.color.b = ob.color[2];
				}
				m.shader.uniforms[ "uShininess" ].value = ob.spec;
				if (m.multires) {
					m.shader.uniforms[ "uDisplacementBias" ].value = ob.disp_bias-DISP_BIAS_MAGIC;
					m.shader.uniforms[ "uDisplacementScale" ].value = ob.disp+DISP_SCALE_MAGIC;
				}
			}

			if (USE_MODIFIERS) {
				if (m.subsurf != ob.subsurf) {
					m.dirty_modifiers = true;
					m.subsurf = ob.subsurf;
				}

				if (ob.verts) {
					m.dirty_modifiers = true;

					var vidx=0;
					for (var i=0; i <= ob.verts.length-3; i += 3) {
						var v = m.geometry_base.vertices[ vidx ];
						v.x = ob.verts[ i ];
						v.y = ob.verts[ i+2 ];
						v.z = -ob.verts[ i+1 ];
						vidx++;
					}
					m.geometry_base.computeCentroids();
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
	mesh = collada.scene.children[0];
	mesh.useQuaternion = true;			// ensure Quaternion
	mesh.geometry.computeTangents();		// requires UV's
	mesh.has_progressive_textures = false;	// enabled from websocket stream
	mesh._material_ = mesh.material;

	// hijack material color to pass info from blender //
	if (mesh.material.color.r) {
		mesh.multires = true;
		mesh.has_displacement = true;
	} else {
		mesh.multires = false;
		mesh.has_displacement = false;
	}
	if (mesh.material.color.g) {	// mesh deformed with an armature will not have AO
		mesh.has_AO = true;
	} else {
		mesh.has_AO = false;
	}

	mesh.shader = mesh.material = create_normal_shader( mesh.name, mesh.has_displacement, mesh.has_AO );

	if (USE_SHADOWS) {
		mesh.castShadow = true;
		mesh.receiveShadow = true;
	}

	if (USE_MODIFIERS) {
		mesh.geometry.dynamic = true;		// required
		mesh.geometry_base = THREE.GeometryUtils.clone(mesh.geometry);
		mesh.material = WIRE_MATERIAL;
	}

	Objects[ mesh.name ] = mesh;
	mesh.dirty_modifiers = true;
	scene.add( mesh );
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


function create_normal_shader( name, displacement, AO ) {
	// material parameters
	var ambient = 0x111111, diffuse = 0xbbbbbb, specular = 0x171717, shininess = 50;
	var shader = THREE.ShaderUtils.lib[ "normal" ];
	var uniforms = THREE.UniformsUtils.clone( shader.uniforms );

	uniforms[ "tDiffuse" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?TEXTURE|64', undefined, on_texture_ready );
	uniforms[ "tNormal" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?NORMALS|128', undefined, on_texture_ready );
	if (AO) {
		uniforms[ "tAO" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?AO|64', undefined, on_texture_ready );
	}
	//uniforms[ "tSpecular" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?SPEC_INTENSITY|64', undefined, on_texture_ready );

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
		uniforms[ "tDisplacement" ].texture = THREE.ImageUtils.loadTexture( '/bake/'+name+'.jpg?DISPLACEMENT|256', undefined, on_texture_ready );
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
}
ws.on('open', on_open);

function on_close(e) {
	console.log(">> WebSockets.onclose");
}
ws.on('close', on_close);



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

	if (DEBUG==false) {
		setupFX( renderer, scene, camera );
		setupDOF( renderer );
	}
}


var DEPTH_MATERIAL;
var postprocessing = { enabled  : true };

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
		var mesh = Objects[ n ];
		dbug = mesh;
		if (mesh && USE_MODIFIERS) {
			if (mesh === SELECTED) { mesh.visible=true; }	// show hull
			else { mesh.visible=false; }	// hide hull

			if (mesh.dirty_modifiers) {
				mesh.dirty_modifiers = false;

				var subsurf = 0;
				if ( mesh.subsurf ) { subsurf=mesh.subsurf; }
				else if ( mesh.multires ) { subsurf=1; }

				// update hull //
				mesh.geometry.vertices = mesh.geometry_base.vertices;
				mesh.geometry.NeedUpdateVertices = true;

				var modifier = new THREE.SubdivisionModifier( subsurf );
				var geo = THREE.GeometryUtils.clone( mesh.geometry_base );

				geo.mergeVertices();		// BAD?  required? //

				modifier.modify( geo );
				geo.NeedUpdateTangents = true;
				geo.computeTangents();		// requires UV's
				//geo.computeFaceNormals();
				//geo.computeVertexNormals();

				if ( mesh.children.length ) { mesh.remove( mesh.children[0] ); }
				var hack = new THREE.Mesh(geo, mesh.shader)
				hack.castShadow = true;
				hack.receiveShadow = true;
				mesh.add( hack );
			}
		}
	}

	requestAnimationFrame( animate );
	if (DEBUG==true) { render_debug(); }
	else { render(); }
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
	STATE = { NONE : -1, ROTATE : 0, ZOOM : 1, PAN : 2 };

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

		// PICKING //
		var vector = new THREE.Vector3( mouse.x, mouse.y, 1 );
		projector.unprojectVector( vector, camera );
		var ray = new THREE.Ray( camera.position, vector.subSelf( camera.position ).normalize() );

		var intersects = ray.intersectObjects( scene.children );
		//var obs = [];
		//for (name in Objects) obs.push( Objects[name] )
		//var intersects = ray.intersectObjects( obs );
		testing = intersects;

		if ( intersects.length > 0 ) {
			for (var i=0; i < intersects.length; i ++) {
				var intersect = intersects[ i ];
				if (intersect.object.name) {	// ensure top level mesh with a name (UID)
					if ( INTERSECTED != intersect.object ) {
						//if ( INTERSECTED ) INTERSECTED.material.color.setHex( INTERSECTED.currentHex );

						INTERSECTED = intersect.object;
						INTERSECTED.currentHex = INTERSECTED.material.color.getHex();
						INTERSECTED.shader.color.setHex( 0xff0000 );
						break;
					}
				}
			}
		} else {
			//if ( INTERSECTED ) INTERSECTED.material.color.setHex( INTERSECTED.currentHex );
			INTERSECTED = null;
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

