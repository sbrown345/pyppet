
var container;

var camera, scene, renderer, objects;

var spotLight, pointLight, ambientLight;

var dae, skin;

var loader = new THREE.ColladaLoader();
loader.options.convertUpAxis = true;
loader.load( '/objects/Cube.dae', function colladaReady( collada ) {

	dae = collada.scene;
	skin = collada.skins[ 0 ];

	//dae.scale.x = dae.scale.y = dae.scale.z = 0.00001;
	//dae.updateMatrix();

	init();
	animate();

} );


function init() {

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
	scene.add( dae );


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


	setInterval( update, 100 );

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


function update() {

}



