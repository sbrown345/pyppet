#!/usr/bin/python3
'''
libblender ctypes example
by Brett, Nov 2011

libblender is a generated ctypes wrapper that exposes the C API of Blender, and over 9000 functions.
Using this you can embed Blender in another application.

From Blender:
	blender --python yourscript.py

	yourscript.py:
		import Blender
		while True: Blender.iterate()

-------------------------------------------------------------------


Standalone libblender (not working yet):

	Installing:
		Step1 - build bpy.so:
			. get the blender source code
			. edit CMakeLists.txt:
				. line 120 - enable PYTHON_MODULE:
					option(WITH_PYTHON_MODULE "Enable building as a python module (experemental, only enable for development)" ON)
				. line 270 - comment out these lines or turn to OFF:
					# may as well build python module without a UI
					if(WITH_PYTHON_MODULE)
						set(WITH_HEADLESS OFF)
					endif()
			. compile bpy.so

		Step2:
			. copy build/bin/bpy.so to ./libblender/linux32/libblender.so
			Notes for 64bits:
				copy to ./libblender/linux64/libblender.so
				./libblender/__init__.py (the ctypes wrapper) was generated on a 32bit platform,
				you might need to regenerate it for a 64bit platfrom using Rpythonic-0.4.2
					( command: rpythonic/scripts/generate-wrappers --blender )


	Known Bugs:
		WM_main loop crashes:
			segfaults at wm_draw_update(C)
	
		C version of "WM_init" opens a window and then crashes
		Py version of "WM_init" failes to open a window - this is likely the cause of the crash in wm_draw_update

'''


import os,sys, time, ctypes
import libblender as blender

STARTUP_BLEND = ''

## from RE_pipeline.h ##
#define RE_BAKE_LIGHT				0	/* not listed in rna_scene.c -> can't be enabled! */
#define RE_BAKE_ALL					1
#define RE_BAKE_AO					2
#define RE_BAKE_NORMALS				3
#define RE_BAKE_TEXTURE				4
#define RE_BAKE_DISPLACEMENT		5
#define RE_BAKE_SHADOW				6
#define RE_BAKE_SPEC_COLOR			7
#define RE_BAKE_SPEC_INTENSITY		8
#define RE_BAKE_MIRROR_COLOR		9
#define RE_BAKE_MIRROR_INTENSITY	10
#define RE_BAKE_ALPHA				11
#define RE_BAKE_EMIT				12


#Object *obedit= CTX_data_edit_object(C);
#ED_uvedit_assign_image

def bake_image( bo, type=6 ):
	import bpy

	print('bake_image...', bo)
	ob = Object( bo )
	print(ob)
	re= blender.RE_NewRender("_Bake View_")
	print('new render', re)

	C = get_context()
	print('context', C)
	bmain = blender.CTX_data_main(C)
	print('main', bmain)
	scn = Scene( bpy.context.scene )
	print('scene', scn )
	layer = 0
	blender.RE_Database_Baking( re, bmain, scn, layer, type, ob )
	print('---------- ok to bake -----------')
	do_update = 0
	progress = ctypes.pointer( ctypes.c_float() )
	vdone = blender.RE_bake_shade_all_selected( re, type, ob, do_update, progress )
	print('vdone',vdone)
	assert vdone
	return progress


########################## bpy-to-ctypes API ###########################

def Object( bo ):
	ptr = ctypes.POINTER(ctypes.c_void_p).from_address( bo.as_pointer() )
	return blender.Object( pointer=ctypes.pointer(ptr), cast=True )


def Image( img ):
	ptr = ctypes.POINTER(ctypes.c_void_p).from_address( img.as_pointer() )
	return blender.Image( pointer=ctypes.pointer(ptr), cast=True )

def Region( reg ):
	ptr = ctypes.POINTER(ctypes.c_void_p).from_address( reg.as_pointer() )
	return blender.ARegion( pointer=ctypes.pointer(ptr), cast=True )

def Context( context ):
	ptr = ctypes.POINTER(ctypes.c_void_p).from_address( context.as_pointer() )
	return blender.bContext( pointer=ctypes.pointer(ptr), cast=True )

def Window( win ):
	ptr = ctypes.POINTER(ctypes.c_void_p).from_address( win.as_pointer() )
	return blender.wmWindow( pointer=ctypes.pointer(ptr), cast=True )

def Scene( s ):
	ptr = ctypes.POINTER(ctypes.c_void_p).from_address( s.as_pointer() )
	return blender.Scene( pointer=ctypes.pointer(ptr), cast=True )


##########################################################################

def get_image_buffer( img ):
	print( img, img.ibufs )
	ibuf = blender.BKE_image_get_ibuf( img, None )
	#ptr = img.ibufs.first		# LP_c_void_p
	#ibuf = blender.ImBuf( pointer=ptr, cast=True )
	print(ibuf, ibuf.x)
	print(ibuf, ibuf.y)
	#print(ibuf, ibuf.encodedbuffer)
	print(ibuf, ibuf.rect)
	return ibuf

def get_context():
	import bpy
	ptr = ctypes.POINTER(ctypes.c_void_p).from_address( bpy.context.as_pointer() )
	return blender.bContext( pointer=ctypes.pointer(ptr), cast=True )


def window_lower():
	C = get_context()
	win = blender.CTX_wm_window( C )
	blender.wm_window_lower( win )

def window_expand():		# makes blender expand to fit its parent window
	C = get_context()
	win = blender.CTX_wm_window( C )
	blender.wm_window_raise( win )


def window_resize( x, y ):
	print('resize',x,y)
	C = get_context()
	win = blender.CTX_wm_window( C )
	blender.wm_window_lower( win )
	blender.WM_setprefsize( 0, 0, x,y )
	blender.wm_window_set_size( win )
	blender.wm_window_raise( win )


def iterate(C, lock=None, draw=True):
	if lock: lock.acquire()
	blender.wm_window_process_events(C)	# might sleep 5ms if no events
	blender.wm_event_do_handlers(C)
	blender.wm_event_do_notifiers(C)
	if lock: lock.release()
	if draw: blender.wm_draw_update(C)

def WM_main(C):		# from wm.c
	while True:
		#/* get events from ghost, handle window events, add to window queues */
		print('proc events...')
		blender.wm_window_process_events(C); 
		#/* per window, all events to the window, screen, area and region handlers */
		print('do handlers...')
		blender.wm_event_do_handlers(C);
		#/* events have left notes about changes, we handle and cache it */
		print('do notifiers...')
		blender.wm_event_do_notifiers(C);
		#/* execute cached changes draw */
		print('drawing....')
		blender.wm_draw_update(C)		# SEGFAULTS wmSubWindowSet 0: doesn't exist

def wm_add_default(C):					# from wm.c	
	idcode = blender.BKE_idcode_from_name( "WindowManager" )
	print('winman idcode', idcode)
	_wm = blender.wmWindowManager()

	wm = blender.alloc_libblock(		# returns void pointer
		_wm,							# pointer to ListBase
		idcode,
		"WinMan"
	)
	wm = blender.wmWindowManager( pointer=wm, cast=True )
	print('wm', wm)
	print('CTX wm screen...')
	screen = blender.CTX_wm_screen(C)
	print( screen )
	print('CTX wm manager set...')
	blender.CTX_wm_manager_set(C, wm);
	print('wm window new...')
	win = blender.wm_window_new(C);
	print(win)
	wm.winactive = win.POINTER
	wm.file_saved = ctypes.c_short(1)
	blender.wm_window_make_drawable(C, win)
	print('----------------------')
	main = blender.CTX_data_main(C)
	#print( 'main.wm pointer is valid', main.wm )


def wm_window_match_init(C, wmlist):	# static function from wm_files.c
	#...
	#G.main->wm.first= G.main->wm.last= NULL;
	print('CTX wm window...')
	active_win = blender.CTX_wm_window(C)
	#...
	print('CTX wm window set...')
	blender.CTX_wm_window_set(C, active_win)
	print('ED editors exit...')
	blender.ED_editors_exit(C)
	#... wm_window_match_do
	print('wm add default...')
	#blender.wm_add_default(C)	# SEGFAULTS!!!
	wm_add_default(C)


def WM_read_homefile(C, reports, from_memory=1):	# from wm_files.c
	wmbase = blender.ListBase()
	wm_window_match_init(C, wmbase)
	print('BKE read file...')
	if from_memory:
		success = blender.BKE_read_file_from_memory(
			C,
			ctypes.cast( blender.CTYPES_DLL.datatoc_startup_blend, ctypes.POINTER(ctypes.c_char) ),
			ctypes.cast( blender.CTYPES_DLL.datatoc_startup_blend_size, ctypes.POINTER(ctypes.c_int) ).contents,
			None
		)
	else: success = blender.BKE_read_file( C, STARTUP_BLEND, None )
	print('startup .blend loaded', success)

#/* only called once, for startup */
def WM_init(C, argc, argv):
	blender.wm_ghost_init(C)
	blender.wm_init_cursor_data()

	blender.GHOST_CreateSystemPaths()
	blender.wm_operatortype_init()
	blender.WM_menutype_init()

	#set_free_windowmanager_cb(wm_close_and_free);	/* library.c */

	func = lambda: blender.wm_window_testbreak()
	cfunc = ctypes.CFUNCTYPE( ctypes.c_void_p)( func )
	ptr = ctypes.pointer( cfunc )
	blender.set_blender_test_break_cb(ptr)	# /* blender.c */

	func = lambda a,b: blender.ED_render_id_flush_update(a,b)
	cfunc = ctypes.CFUNCTYPE( ctypes.c_void_p, ctypes.c_void_p,ctypes.c_void_p)( func )
	ptr = ctypes.pointer( cfunc )
	blender.DAG_editors_update_cb( ptr )		# /* depsgraph.c */

	print('ED spacetypes init...')
	blender.ED_spacetypes_init();	#/* editors/space_api/spacetype.c */
	
	blender.ED_file_init();	#		/* for fsmenu */
	blender.ED_init_node_butfuncs();	
	
	#/* Please update source/gamengine/GamePlayer/GPG_ghost.cpp if you change this */
	dpi = 100
	blender.BLF_init(11, dpi)

	blender.BLF_lang_init()

	#/* get the default database, plus a wm */
	print('WM read homefile...')
	rlist = blender.ReportList()
	#blender.WM_read_homefile(C, rlist, ctypes.c_short(1))		# SEGFAULTS! defined in wm_files.c
	WM_read_homefile(C, rlist)

	#------------------------------------------------------------------------------------------------------------------

	#/* note: there is a bug where python needs initializing before loading the
	# * startup.blend because it may contain PyDrivers. It also needs to be after
	# * initializing space types and other internal data.
	# *
	# * However cant redo this at the moment. Solution is to load python
	# * before WM_read_homefile() or make py-drivers check if python is running.
	# * Will try fix when the crash can be repeated. - campbell. */

	#ifdef WITH_PYTHON
	print('bpy context set...')
	blender.BPY_context_set(C); 	#/* necessary evil */
	#blender.BPY_python_start(argc, argv);
	print('bpy driver reset...')
	blender.BPY_driver_reset();
	#/* causes addon callbacks to be freed but this is actually what we want. */

	############# HELP ############
	#print('bpy app handlers reset...')
	#blender.BPY_app_handlers_reset()	# SEGFAULTS
	#print('bpy modules load user...')
	#blender.BPY_modules_load_user(C)		# SEGFAULTS

	print('ghost toggle console...')
	blender.GHOST_toggleConsole(3);

	#TODO	blender.wm_init_reports(C); #/* reports cant be initialized before the wm */

	############## HELP ###########
	#print('gpu init...')		# SEGFAULTS
	#blender.GPU_extensions_init()
	#print( 'GPU set mipmap...')
	#blender.GPU_set_mipmap(True)
	#blender.GPU_set_anisotropic(True)

	print('UI init...')
	blender.UI_init()
	print('clear mat copy buf...')
	blender.clear_matcopybuf()
	print('ED init...')
	blender.ED_render_clear_mtex_copybuf()
	blender.ED_preview_init_dbase()
	print('WM read history...')
	#blender.WM_read_history();

	#/* allow a path of "", this is what happens when making a new file */
	#/*
	#if(G.main->name[0] == 0)
	#	BLI_make_file_string("/", G.main->name, BLI_getDefaultDocumentFolder(), "untitled.blend");
	#*/
	#BLI_strncpy(G.lib, G.main->name, FILE_MAX);
	print('py wm init complete')


def main():
	print('py main...')
	syshandle = 0
	C = blender.CTX_create()
	print( C )
	ba = blender.bArgs()
	#setCallbacks()
	#bprogname = os.path.join( os.path.abspath('.'), 'blender' )
	#blender.BLI_where_am_i(bprogname, len(bprogname), 'blender')		# SEGFAULTS, not important?

	blender.BLI_threadapi_init()
	blender.RNA_init()
	blender.RE_engines_init()
	blender.pluginapi_force_ref()	# deprecated?
	blender.init_nodesystem()
	blender.initglobals()			#/* blender.c */
	blender.IMB_init()
	blender.BLI_cb_init()
	#if with game engine: syshandle = blender.SYS_GetSystem()
	blender.BLI_argsParse(ba, 1, None, None)  # required, segfaults without this


	_argv = ''
	for arg in sys.argv: _argv += arg + ' '
	_argv = bytes( _argv, 'utf-8' )
	argc = len(sys.argv)
	argv = ctypes.pointer(ctypes.c_char_p(_argv))
	ba = blender.BLI_argsInit(argc, argv)
	#blender.setupArguments(C, ba, syshandle)	# missing

	print('BKE font register builtin...')
	bfont = ctypes.cast(
		blender.CTYPES_DLL.datatoc_Bfont, ctypes.POINTER(ctypes.c_void_p)
	)
	bfontsize = ctypes.cast(
		blender.CTYPES_DLL.datatoc_Bfont_size, ctypes.POINTER(ctypes.c_int)
	).contents
	print(bfontsize)

	blender.BKE_font_register_builtin(
		bfont, 
		bfontsize
	)
	blender.BLI_argsParse(ba, 1, None, None)  # required, segfaults without this

	blender.sound_init_once()
	blender.init_def_material()

	blender.BLI_argsParse(ba, 2, None, None)
	blender.BLI_argsParse(ba, 3, None, None)
	print('wm init....')
	#blender.WM_init(C, argc, argv)		# opens a window and then SEGFAULTS
	WM_init( C, argc, argv )				# no segfault, but no window appears, missing something??
	print('-----------wm init ok-------------')

	#blender.BLI_where_is_temp(btempdir, FILE_MAX, 1); /* call after loading the startup.blend so we can read U.tempdir */

	#blender.CTX_py_init_set(C, 1)		# is this safe to call?
	print('keymap init...')
	blender.WM_keymap_init( C )

	#/* OK we are ready for it */
	#BLI_argsParse(ba, 4, load_file, C);
	#BLI_argsFree(ba);
	print('wm init splash...')
	blender.WM_init_splash(C)
	#blender.WM_main(C)
	print('WM main...')
	WM_main(C)
	print('test complete')



if __name__ == '__main__':
	main()


