var canvas = document.getElementById( 'canvas' );
var renderer = new GLGE.Renderer( canvas );
var XMLdoc = new GLGE.Document();
var scene = null;
var collada = null;
var o = null;

var TRANSFORM_SLOTS = ['QuatX', 'QuatY', 'QuatZ', 'QuatW', 'LocX', 'LocY', 'LocZ'];
//, 'ScaleX', 'ScaleY', 'ScaleZ'];


function setup() {
	var a = get_leaf_objects( collada )[0];
	var points = [];
	var act = get_action(a);
	var bones = get_bone_names(a);
	for (n in bones) {
		name = bones[ n ];
		var anim = new GLGE.AnimationVector();
		anim.setFrames( 1 );
		for (n in TRANSFORM_SLOTS) {
			slot = TRANSFORM_SLOTS[ n ];
			var curve = new GLGE.AnimationCurve();
			curve.setChannel( slot );
			point=new GLGE.LinearPoint();
			point.setX(1);
			point.setY(12.0);
			curve.addPoint( point );
			anim.addAnimationCurve( curve );
			points.push( point );
		}
		var chan = new GLGE.ActionChannel();
		chan.setTarget( name );
		chan.setAnimation( anim );
		act.addActionChannel( chan );
	}
	return points;
}

function get_animations( a ) {
	var anims = {};
	var act = get_action( a );
	for (chan in act.channels) {
		anims[ chan.target ] = chan.animation;	// chan.target is bone name
	}
	return anims;
}


function get_bone_names( ob ) {
	var child = null;
	var bones = [];
	var groups = [];
	for (n in ob.mesh.joints) {
		var child = ob.mesh.joints[ n ];
		if (child.className == 'Group') { groups.push(child); }
		else { bones.push(child); }
	}
	return bones;
}

function get_action( ob ) {			// returns default action
	var skel = ob.getSkeleton();
	var act = skel.actions.default;
	return act;
}

function get_leaf_objects( a ) { var r = []; _get_leaf_objects( a, r ); return r; }
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
	renderer.render();
}

XMLdoc.onLoad = function(){
	scene = XMLdoc.getElement( "mainscene" );
	renderer.setScene( scene );
	collada = scene.children[ scene.children.length-1 ]
	//o = get_leaf_objects( collada )[0];	// not ready yet, call later
	//setup( o );
	setInterval( update, 15 );
}
XMLdoc.parseScript("glge_document");

