var canvas = document.getElementById( 'canvas' );
var renderer = new GLGE.Renderer( canvas );
var XMLdoc = new GLGE.Document();
var scene = null;
var collada = null;

function get_leaf_objects( a, result ) {
	if (a.className == 'Group') {
		for (var i=0;i<a.children.length;i++) {
			get_leaf_objects( a.children[i], result );
		}
	} else if (a.className == 'Object') {
		result.push( a );
	}
}

function update() {
	//var scn = XMLdoc.getElement( "mainscene" );
	//var dae = scn.children[ scn.children-1 ];
	//var objects = dae.getObjects();
	//var skel = objects[0].getSkeleton();
	renderer.render();
}

XMLdoc.onLoad = function(){
	scene = XMLdoc.getElement( "mainscene" );
	renderer.setScene( scene );
	collada = scene.children[ scene.children.length-1 ]

	setInterval( update, 15 );
}
XMLdoc.parseScript("glge_document");

