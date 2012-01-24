var WIRE_MATERIAL = new THREE.MeshLambertMaterial( { color: 0x000000, wireframe: true } );

var SCREEN_WIDTH = window.innerWidth;
var SCREEN_HEIGHT = window.innerHeight - 10;

var composer, effectFXAA, hblur, vblur;

ws = new Websock();
ws.open( 'ws://localhost:8081' );
var tmp = null;

var Objects = {};

function on_message(e) {
	var data = ws.rQshiftStr();
	var ob = JSON.parse( data );
	var name = ob.name.replace('.', '_');

	if (name in Objects && Objects[name]) {
		m = Objects[ name ];
		m.position.x = ob.pos[0];
		m.position.y = ob.pos[2];
		m.position.z = -ob.pos[1];

		m.scale.x = ob.scl[0];
		m.scale.y = ob.scl[2];
		m.scale.z = ob.scl[1];

		m.rotation.x = ob.rot[0];
		m.rotation.y = ob.rot[2];
		m.rotation.z = -ob.rot[1];

		var vidx = 0;
		for (var i=0; i<ob.verts.length-3; i += 3) {
			var v = m.geometry_base.vertices[ vidx ].position;
			v.x = ob.verts[ i ];
			v.y = ob.verts[ i+2 ];
			v.z = -ob.verts[ i+1 ];
			vidx++;
		}
		//m.geometry_base.__dirtyVertices = true;
		//m.geometry_base.__tmpVertices = undefined;
		m.geometry_base.computeCentroids();
		//m.geometry_base.computeFaceNormals();
		//m.geometry_base.computeVertexNormals();

		if (ob.color) {
			m._material.color.r = ob.color[0];
			m._material.color.g = ob.color[1];
			m._material.color.b = ob.color[2];
		}

		m.dirty_modifiers = true;
		m.subsurf = ob.subsurf;
	}

	else if (name in Objects == false) {
		console.log( '>> loading new collada' );
		Objects[ name ] = null;
		var loader = new THREE.ColladaLoader();
		loader.options.convertUpAxis = true;
		loader.load( '/objects/'+ob.name+'.dae', on_collada_ready );

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
	tmp = collada;
	//skin = collada.skins[0]
	//Objects[ skin.name ] = collada;
	mesh = collada.scene.children[0];
	mesh.useQuaternion = false;
	mesh.castShadow = true;
	mesh.receiveShadow = true;
	mesh.geometry.dynamic = true;		// required
	mesh.geometry_base = THREE.GeometryUtils.clone(mesh.geometry);
	mesh._material = mesh.material;
	mesh.material = WIRE_MATERIAL;

/*	## over allocation is not the trick ##
	var modifier = new THREE.SubdivisionModifier( 2 );
	modifier.modify( mesh.geometry );
*/
	Objects[ mesh.name ] = mesh;

	scene.add( collada.scene );
	dae = collada.scene;

	camera.lookAt( mesh.position );
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
var spotLight, pointLight, ambientLight;
var dae, skin;
var controls;

function init() {
	console.log(">> THREE init");

	container = document.createElement( 'div' );
	document.body.appendChild( container );

	// scene //
	scene = new THREE.Scene();

	// camera //
	camera = new THREE.PerspectiveCamera( 45, window.innerWidth / (window.innerHeight-10), 1, 2000 );
	camera.position.set( 0, 4, 10 );
	//camera.up.set( 0, 0, 1 );
	scene.add( camera );

	controls = new THREE.FirstPersonControls( camera );
	controls.lookSpeed = 0.075;
	controls.movementSpeed = 10;
	controls.noFly = false;
	controls.lookVertical = true;
	//controls.constrainVertical = true;
	controls.verticalMin = 0.0;
	controls.verticalMax = 2.0;
	//controls.lon = -110;


	// Grid //
	var line_material = new THREE.LineBasicMaterial( { color: 0xcccccc, opacity: 0.2 } ),
	geometry = new THREE.Geometry(),
	floor = -0.04, step = 1, size = 14;
	for ( var i = 0; i <= size / step * 2; i ++ ) {
		geometry.vertices.push( new THREE.Vertex( new THREE.Vector3( - size, floor, i * step - size ) ) );
		geometry.vertices.push( new THREE.Vertex( new THREE.Vector3(   size, floor, i * step - size ) ) );
		geometry.vertices.push( new THREE.Vertex( new THREE.Vector3( i * step - size, floor, -size ) ) );
		geometry.vertices.push( new THREE.Vertex( new THREE.Vector3( i * step - size,  floor, size ) ) );

	}
	var line = new THREE.Line( geometry, line_material, THREE.LinePieces );
	scene.add( line );


	// Add the COLLADA //
	//scene.add( dae );


	// LIGHTS //
	ambientLight = new THREE.AmbientLight( 0x111111 );
	scene.add( ambientLight );

	pointLight = new THREE.PointLight( 0xff0000 );
	pointLight.position.z = 10000;
	pointLight.distance = 4000;
	scene.add( pointLight );

	pointLight2 = new THREE.PointLight( 0xff5500 );
	pointLight2.position.z = 1000;
	pointLight2.distance = 2000;
	scene.add( pointLight2 );

	pointLight3 = new THREE.PointLight( 0x0000ff );
	pointLight3.position.x = -1000;
	pointLight3.position.z = 1000;
	pointLight3.distance = 2000;
	scene.add( pointLight3 );

	spotLight = new THREE.SpotLight( 0xaaaaaa );
	spotLight.position.set( 0, 500, 10 );
	spotLight.target.position.set( 0, 0, 0 );
	spotLight.castShadow = true;
	spotLight.shadowCameraNear = 480;
	spotLight.shadowCameraFar = camera.far;
	spotLight.shadowCameraFov = 70;
	spotLight.shadowBias = 0.001;
	spotLight.shadowMapWidth = 2048;
	spotLight.shadowMapHeight = 2048;
	scene.add( spotLight );


	// renderer //
	renderer = new THREE.WebGLRenderer( { maxLights: 8 } );
	renderer.setSize( window.innerWidth, window.innerHeight-10 );
	container.appendChild( renderer.domElement );
	renderer.gammaInput = true;
	renderer.gammaOutput = true;
	renderer.shadowMapEnabled = true;
	renderer.shadowMapSoft = true;
	renderer.shadowMapAutoUpdate = false;
	renderer.setClearColor( {r:0.4,g:0.4,b:0.4}, 1.0 )

	renderer.physicallyBasedShading = true;
	// COMPOSER

	renderer.autoClear = false;

	renderTargetParameters = { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, format: THREE.RGBFormat, stencilBufer: false };
	renderTarget = new THREE.WebGLRenderTarget( SCREEN_WIDTH, SCREEN_HEIGHT, renderTargetParameters );

	effectFXAA = new THREE.ShaderPass( THREE.ShaderExtras[ "fxaa" ] );
	var effectVignette = new THREE.ShaderPass( THREE.ShaderExtras[ "vignette" ] );

	hblur = new THREE.ShaderPass( THREE.ShaderExtras[ "horizontalTiltShift" ] );
	vblur = new THREE.ShaderPass( THREE.ShaderExtras[ "verticalTiltShift" ] );

	var bluriness = 4;

	hblur.uniforms[ 'h' ].value = bluriness / SCREEN_WIDTH;
	vblur.uniforms[ 'v' ].value = bluriness / SCREEN_HEIGHT;

	hblur.uniforms[ 'r' ].value = vblur.uniforms[ 'r' ].value = 0.5;

	effectFXAA.uniforms[ 'resolution' ].value.set( 1 / SCREEN_WIDTH, 1 / SCREEN_HEIGHT );

	composer = new THREE.EffectComposer( renderer, renderTarget );

	var renderModel = new THREE.RenderPass( scene, camera );

	effectVignette.renderToScreen = true;
	vblur.renderToScreen = true;

	composer = new THREE.EffectComposer( renderer, renderTarget );

	composer.addPass( renderModel );

	composer.addPass( effectFXAA );

	composer.addPass( hblur );
	composer.addPass( vblur );

	//composer.addPass( effectVignette );


}


function animate() {
	// subdiv modifier //
	for (n in Objects) {
		var mesh = Objects[ n ];
		dbug = mesh;
		if (mesh && mesh.dirty_modifiers) {
			console.log( mesh.subsurf );
			mesh.dirty_modifiers = false;

			// update hull //
			mesh.geometry.vertices = mesh.geometry_base.vertices;
			mesh.geometry.__dirtyVertices = true;


			var modifier = new THREE.SubdivisionModifier( mesh.subsurf );
			var geo = THREE.GeometryUtils.clone( mesh.geometry_base );

			geo.mergeVertices();		// BAD?  required? //

			modifier.modify( geo );
			if ( mesh.children.length ) {
				mesh.remove( mesh.children[0] );
			}

			var hack = new THREE.Object3D();
			hack.add( new THREE.Mesh(geo, mesh._material) );
			mesh.add( hack );


/* not working!!
			geo.geometryGroups = undefined;
			geo.geometryGroupsList = [];
			mesh.geometry = geo;
			geo.__dirtyVertices = true;
			geo.__dirtyMorphTargets = true;
			geo.__dirtyElements = true;
			geo.__dirtyUvs = true;
			geo.__dirtyNormals = true;
			geo.__dirtyTangents = true;
			geo.__dirtyColors = true;
*/

			//mesh.geometry.geometryGroups = undefined;		// no help
			//mesh.geometry.geometryGroupsList = undefined;	// crashes

/*		######## this updates the mesh, but only shows faces < base length ########
			mesh.geometry.vertices = geo.vertices;
			mesh.geometry.faces = geo.faces;
			//mesh.geometry.faceUvs = geo.faceUvs;
			//mesh.geometry.faceVertexUvs = geo.faceVertexUvs;
			mesh.geometry.__dirtyVertices = true;
			mesh.geometry.__dirtyElements = true;
			mesh.geometry.__dirtyNormals = true;
			mesh.geometry.__dirtyColors = true;
			mesh.geometry.__dirtyTangents = true;
*/

		}
	}

	requestAnimationFrame( animate );
	render();
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

var use_camera_controls = true;
function on_key_up(event) {
	//console.log( event.keyCode );
	switch( event.keyCode ) {

		case 32: 		/* space */
			use_camera_controls = !use_camera_controls;
			break;

	}

}
window.addEventListener( 'keyup', on_key_up, false );


var clock = new THREE.Clock();
var dbug = null;

function render() {
	var timer = Date.now() * 0.0005;

	resize_view();

	var delta = clock.getDelta();
	if ( use_camera_controls ) {
		controls.update( delta );
	}

/*
	camera.position.x = Math.cos( timer ) * 10;
	camera.position.y = Math.sin( timer ) * 10;
	camera.position.z = 2;
	camera.lookAt( scene.position );
*/

	//renderer.render( scene, camera );

	// update subdiv was here


	// render shadow map
	renderer.autoUpdateObjects = false;
	renderer.initWebGLObjects( scene );
	renderer.updateShadowMap( scene, camera );

	// render cube map
/*
	mesh.visible = false;
	renderer.autoClear = true;
	cubeCamera.updatePosition( mesh.position );
	cubeCamera.updateCubeMap( renderer, scene );
	renderer.autoClear = false;
	mesh.visible = true;
*/

	// render scene
	renderer.autoUpdateObjects = true;
	composer.render( 0.1 );


}


init();
animate();

