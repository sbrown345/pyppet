#!/usr/bin/python
# updated nov, 2011 - NOT pypy1.7 compatible
import os, sys, time, ctypes, threading
import cv
import highgui as gui
import gtk3 as gtk


class LayerConfig(object):
	_FXtypes = 'FXsplit FXblur FXsobel FXathresh FXthresh'.split()

	_colorspaces = '''
	CV_BGR2GRAY
	CV_BGR2HLS
	CV_BGR2HSV
	CV_BGR2Lab
	CV_BGR2Luv
	CV_BGR2RGB
	CV_BGR2XYZ
	CV_BGR2YCrCb
	'''
	_ColorSpaces = {}
	_ColorSpacesByValue = {}
	for _n in _colorspaces.split():
		_ColorSpacesByValue[ getattr(cv,_n) ] = _n
		_ColorSpaces[ _n ] = getattr(cv,_n)

	def _toggle( self, button, name ):
		print( '_toggle', button, name )
		setattr(self, name, button.get_active() )

	def _adjust( self, adj, name ):
		setattr(self, name, adj.get_value() )


	def __init__(self, colorspace):
		self.colorspace = colorspace
		self.active = False
		self.alpha = 255
		self.blur = 2
		self.athresh_block_size = 3

		self.thresh_min = 32
		self.thresh_max = 200

		self.sobel_xorder = 1
		self.sobel_yorder = 1
		self.sobel_aperture = 5

		self.split_red = self.split_green = self.split_blue = False
		for fx in self._FXtypes: setattr(self, fx, False )



	def widget( self, notebook ):
		cspace = self._ColorSpacesByValue[ self.colorspace ]
		tag = cspace.split('2')[-1]
		page = gtk.VBox()
		#h = gtk.HBox()
		b = gtk.CheckButton(tag+' Colorspace')
		page.pack_start( b )
		b.connect('toggled', self._toggle, 'active')
		#lambda b,lay: setattr(lay,'active',bool(b.get_active())), layer)
		b.set_active( bool(self.active) )
		notebook.append_page( page, gtk.Label() )

		fxgroups = {}
		for name in self._FXtypes:
			row = gtk.HBox()
			page.pack_start( row )

			val = getattr( self, name )
			bb = gtk.VBox()
			sw = gtk.CheckButton()
			#sw = gtk.Switch()
			sw.set_active( bool(val) )
			sw.connect('toggled', self._toggle, name)
			#sw.connect('activate', self._toggle, name)

			bb.pack_start( sw, expand=False, fill=False )
			row.pack_start( bb, expand=False, fill=False )

			ex = gtk.Expander( name )
			row.pack_start( ex )
			bx = gtk.VBox(); bx.set_border_width( 10 )
			fxgroups[ name.split('FX')[-1] ] = bx
			ex.add( bx )


		_skip = ['colorspace','active', 'widget'] + self._FXtypes
		for name in dir(self):
			if not name.startswith('_') and name not in _skip:
				val = getattr( self, name )

				bx = None
				for fx in fxgroups:
					if name.startswith(fx):
						bx = fxgroups[fx]
						break

				if not bx:
					adjust = gtk.Adjustment(
						value=val, 
						lower=0, upper=255, 
					)
					adjust.connect('value-changed', self._adjust, name)
					scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
					scale.set_digits(0)
					#f = gtk.Frame( name )
					#f.add( scale )
					page.pack_start( scale )

				elif bx:
					if fx=='split':
						b = gtk.CheckButton( name )
						b.set_active( bool(getattr(self,name)) )
						b.connect('toggled', self._toggle, name)
						bx.pack_start( b )
					else:
						upper = 255
						lower = 0
						step = 1
						if name.startswith('sobel'):
							upper = 31; lower = 1; step=2
						adjust = gtk.Adjustment(
							value=val, 
							lower=lower, upper=upper, 
						)
						adjust.connect('value-changed', self._adjust, name)
						scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.GTK_POS_RIGHT)
						scale.set_digits(0)
						row = gtk.HBox()
						row.pack_start( gtk.Label( name.split(fx)[-1].replace('_',' ') ), expand=False )
						row.pack_start( scale )
						bx.pack_start( row )




class WebCamera(object):

	_default_spaces = [ 
		cv.CV_BGR2RGB, 
		cv.CV_BGR2HSV,
		cv.CV_BGR2Lab,
		cv.CV_BGR2YCrCb,
	]

	def __init__(self, width=640, height=480, active=True):
		self.active = active
		self.lock = None
		self.index = 0
		self.ready = os.path.exists('/dev/video0')		# is this true for all linux?
		self.cam = gui.CreateCameraCapture(self.index)

		########### Layer Configs ############
		self.layers = []
		for colorspace in self._default_spaces:
			self.layers.append( LayerConfig( colorspace ) )
		self.layers[0].active = True

		self.resize( width, height )


	def resize( self, x,y ):
		self.width = x
		self.height = y

		self.cam.SetCaptureProperty( gui.CV_CAP_PROP_FRAME_WIDTH, self.width )
		self.cam.SetCaptureProperty( gui.CV_CAP_PROP_FRAME_HEIGHT, self.height )

		self._rgb8 = cv.CreateImage((self.width,self.height), cv.IPL_DEPTH_8U, 3)
		self._rgb32 = cv.CreateImage((self.width,self.height), cv.IPL_DEPTH_32F, 3)
		self._gray8 = cv.CreateImage((self.width,self.height), cv.IPL_DEPTH_8U, 1)
		self._gray32 = cv.CreateImage((self.width,self.height), cv.IPL_DEPTH_32F, 1)

		self._R = cv.CreateImage((self.width,self.height), cv.IPL_DEPTH_8U, 1)
		self._G = cv.CreateImage((self.width,self.height), cv.IPL_DEPTH_8U, 1)
		self._B = cv.CreateImage((self.width,self.height), cv.IPL_DEPTH_8U, 1)
		self._A = cv.CreateImage((self.width,self.height), cv.IPL_DEPTH_8U, 1)

		self.dwidth = 240	#int(x/2)
		self.dheight = 160	#int(y/2)

		self.preview_image = cv.CreateImage((self.dwidth,self.dheight), cv.IPL_DEPTH_8U, 3)

		n = self.dwidth * self.dheight * 3
		self.BUFFER_TYPE = (ctypes.c_ubyte * n)
		raw = self.BUFFER_TYPE()
		for x in range( n ): raw[x] = 64

		ptr = ctypes.pointer( raw )
		pix = gtk.gdk_pixbuf_new_from_data(
			ptr, 
			gtk.GDK_COLORSPACE_RGB,
			False,	# ALPHA
			8,		# bits per sample
			self.dwidth,
			self.dheight,
			self.dwidth*3,	# row-stride
		)
		self.preview_image_gtk = gtk.gtk_image_new_from_pixbuf( pix )

		for layer in self.layers:
			layer._image = cv.CreateImage( (self.width,self.height), cv.IPL_DEPTH_8U, 3 )

		self.comp_image = cv.CreateImage( (self.width,self.height), cv.IPL_DEPTH_8U, 3 )


	def iterate( self ):
		_rgb8 = self._rgb8
		_rgb32 = self._rgb32
		_gray8 = self._gray8
		_gray32 = self._gray32

		if self.active:
			_frame = self.cam.QueryFrame()	# IplImage from highgui lacks fancy methods
			cv.cvSet( self.comp_image, cv.CvScalar(255,255,255) )
			#cv.cvSet( self.comp_image, cv.CvScalar(0,0,0) )
			prev = self.comp_image
			for layer in self.layers:
				if not layer.active: continue

				a = layer._image
				cv.CvtColor( _frame, a, layer.colorspace )		# no _frame.CvtColor because its from highgui

				## FX
				if layer.FXsplit:
					a.Split( self._R, self._G, self._B )
					if layer.split_red: a = self._R
					elif layer.split_green: a = self._G
					elif layer.split_blue: a = self._B


				if layer.FXblur:			# blur before threshing
					blur = int(layer.blur)
					if blur < 1: blur = 1
					cv.Smooth( a, a, cv.CV_BLUR, blur )

				if layer.FXsobel and layer.sobel_aperture % 2 and layer.sobel_aperture < 32:
					if layer.sobel_xorder < layer.sobel_aperture and layer.sobel_yorder < layer.sobel_aperture:
						xorder = int( layer.sobel_xorder )
						yorder = int( layer.sobel_yorder )
						aperture = int( layer.sobel_aperture )
						if a.nChannels == 1:
							cv.cvSobel( a, _gray32, xorder, yorder, aperture )
							cv.cvConvert( _gray32, a )
						else:
							cv.cvSobel( a, _rgb32, xorder, yorder, aperture )
							cv.cvConvert( _rgb32, a )

				if layer.FXthresh:
					cv.Threshold( a, a, int(layer.thresh_min), int(layer.thresh_max), cv.CV_THRESH_BINARY )

				if layer.FXathresh:
					blocksize = int(layer.athresh_block_size)
					if blocksize <= 2: blocksize = 3
					if blocksize % 2 != 1: blocksize += 1
					if a.nChannels == 1:
						cv.AdaptiveThreshold(a, a, 255, cv.CV_ADAPTIVE_THRESH_MEAN_C, cv.CV_THRESH_BINARY, blocksize )
					else:
						cv.CvtColor(a, _gray8, cv.CV_RGB2GRAY)
						cv.AdaptiveThreshold(_gray8, _gray8, 255, cv.CV_ADAPTIVE_THRESH_MEAN_C, cv.CV_THRESH_BINARY, blocksize )
						cv.CvtColor(_gray8, a, cv.CV_GRAY2RGB)

				if a.nChannels == 1:
						cv.CvtColor(a, _rgb8, cv.CV_GRAY2RGB)
						a = _rgb8

				if prev: cv.cvMul( prev, a, self.comp_image, 1.0-(layer.alpha/256.0) )
				else: cv.cvConvert( a, self.comp_image )
				prev = a

			cv.cvResize( self.comp_image, self.preview_image, True )
			if self.lock:
				self.lock.acquire()
				self.update_preview_image( self.preview_image.imageData )
				self.lock.release()
			else:
				self.update_preview_image( self.preview_image.imageData )


	def update_preview_image(self, pointer ):
		#ptr = ctypes.pointer( BUFFER_TYPE() )
		#ctypes.memmove( ptr, pointer, 640*480*3 )	# not required
		pix = gtk.gdk_pixbuf_new_from_data(
			pointer, 
			gtk.GDK_COLORSPACE_RGB,
			False,	# ALPHA
			8,		# bits per sample
			self.dwidth,
			self.dheight,
			self.dwidth*3,	# row-stride
		)
		gtk.image_set_from_pixbuf( self.preview_image_gtk, pix )

	def start_thread(self, lock):
		self.lock = lock
		if self.ready: threading._start_new_thread( self.loop, () )
		else: print('Warning: no webcam found')

	def loop(self):
		print('webcam begin thread...')
		while self.active:
			self.iterate()
		print('webcam thread exit')

class Widget(object):
	def exit(self, arg):
		self.active = False
		self.webcam.active = False

	def __init__(self, parent, active=True ):
		self.webcam = WebCamera( active=active )
		self.active = active
		root = gtk.VBox(); root.set_border_width( 2 )
		parent.add( root )
		root.pack_start( self.webcam.preview_image_gtk, expand=False )
		note = gtk.Notebook()
		note.set_tab_pos( gtk.POS_BOTTOM )
		root.pack_start( note, expand=False )
		for layer in self.webcam.layers:
			layer.widget( note )


if __name__ == '__main__':
	gtk.init()

	win = gtk.Window()
	win.set_title( 'OpenCV+GTK' )
	widget = Widget( win )
	win.connect('destroy', widget.exit )
	win.show_all()

	lock = threading._allocate_lock()
	widget.webcam.start_thread( lock )

	while widget.active:
		#widget.webcam.iterate()		# threading is way better
		lock.acquire()

		if gtk.gtk_events_pending():
			while gtk.gtk_events_pending():
				gtk.gtk_main_iteration()
		lock.release()



