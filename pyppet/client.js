var canvas = document.getElementById( 'canvas' );
var renderer = new GLGE.Renderer( canvas );
var XMLdoc = new GLGE.Document();
var scene = null;
var collada = null;

function get_animations( a ) {
	var anims = {};
	var act = get_action( a );
	for (chan in act.channels) {
		anims[ chan.target ] = chan.animation;
	}
	return anims;
}
// chan.animation:
//  .curves, .setFrames, .setJSONSrc, .setJSONString, .addAnimationCurve
// curves:
//	LocX.keyFrames:
//		LinearPoint: x, y (x is time, y is value)


function get_bone_names( a ) {
	var ob = get_leaf_objects( a )[0];
	var child = null;
	var bones = [];
	var groups = [];

	for (var i=0;i<a.children.length;i++) {
		child = ob.mesh.joints[ i ];
		if (child.className == 'Group') { groups.push(child); }
		else { bones.push(child); }
	}
	return bones;
}

function get_action( a ) {	// returns default action
	var ob = get_leaf_objects( a )[0];
	var skel = ob.getSkeleton();
	var act = skel.actions.default;
	return act;
}

function get_leaf_objects( a ) {
	var r = [];
	_get_leaf_objects( a, r );
	return r;
}

function _get_leaf_objects( a, result ) {
	if (a.className == 'Group') {
		for (var i=0;i<a.children.length;i++) {
			_get_leaf_objects( a.children[i], result );
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

