ws = new Websock();
ws.open( 'ws://localhost:8081' );
var tmp = null;

var Objects = {};

function on_collada_ready( collada ) {
	console.log( '>> collada loaded' );
	tmp = collada;
	//skin = collada.skins[0]
	//Objects[ skin.name ] = collada;
	mesh = collada.scene.children[0];
	Objects[ mesh.name ] = collada;

	scene.add( collada.scene );
	dae = collada.scene;
}

function on_message(e) {
	var data = ws.rQshiftStr();
	var ob = JSON.parse( data );

	if (ob.name in Objects == false) {
		console.log( '>> loading new collada' );
		Objects[ ob.name ] = null;
		var loader = new THREE.ColladaLoader();
		loader.options.convertUpAxis = true;
		loader.load( '/objects/'+ob.name+'.dae', on_collada_ready );

	}
	else if (ob.name in Objects) {
		if ( Objects[ob.name] ) {
			o = Objects[ ob.name ];
			o.scene.position.x = ob.pos[0];
			o.scene.position.y = ob.pos[1];
			o.scene.position.z = ob.pos[2];
		}
	}
}



ws.on('message', on_message);

function on_open(e) {
	console.log(">> WebSockets.onopen");
}
ws.on('open', on_open);

function on_close(e) {
	console.log(">> WebSockets.oncloseXXX");
}
ws.on('close', on_close);



//////////////////////////////////////////////////////////////////////
var container;
var camera, scene, renderer;
var spotLight, pointLight, ambientLight;
var dae, skin;


function init() {
	console.log(">> THREE init");

	container = document.createElement( 'div' );
	document.body.appendChild( container );

	// scene //
	scene = new THREE.Scene();

	// camera //
	camera = new THREE.PerspectiveCamera( 45, window.innerWidth / window.innerHeight, 1, 2000 );
	camera.position.set( 20, 20, 3 );
	scene.add( camera );

	// Grid //
	var line_material = new THREE.LineBasicMaterial( { color: 0xcccccc, opacity: 0.2 } ),
	geometry = new THREE.Geometry(),
	floor = -0.04, step = 1, size = 14;
	for ( var i = 0; i <= size / step * 2; i ++ ) {
		geometry.vertices.push( new THREE.Vertex( new THREE.Vector3( - size, floor, i * step - size ) ) );
		geometry.vertices.push( new THREE.Vertex( new THREE.Vector3(   size, floor, i * step - size ) ) );
		geometry.vertices.push( new THREE.Vertex( new THREE.Vector3( i * step - size, floor, -size ) ) );
		geometry.vertices.push( new THREE.Vertex( new THREE.Vector3( i * step - size, floor,  size ) ) );

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
	spotLight.position.set( 1000, 500, 1000 );
	spotLight.castShadow = true;
	spotLight.shadowCameraNear = 500;
	spotLight.shadowCameraFov = 70;
	spotLight.shadowBias = 0.001;
	spotLight.shadowMapWidth = 1024;
	spotLight.shadowMapHeight = 1024;
	scene.add( spotLight );


	// renderer //
	renderer = new THREE.WebGLRenderer( { maxLights: 8 } );
	renderer.setSize( window.innerWidth, window.innerHeight );
	container.appendChild( renderer.domElement );
	renderer.gammaInput = true;
	renderer.gammaOutput = true;
	renderer.shadowMapEnabled = true;
	renderer.shadowMapSoft = true;


	//setInterval( update, 100 );

}


function animate() {
	requestAnimationFrame( animate );
	render();
}

function render() {
	var timer = Date.now() * 0.0005;

	camera.position.x = Math.cos( timer ) * 10;
	camera.position.y = 2;
	camera.position.z = Math.sin( timer ) * 10;

	camera.lookAt( scene.position );
	renderer.render( scene, camera );

}


init();
animate();

