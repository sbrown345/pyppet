#!/usr/bin/python
# updated March 2012

import os, sys, ctypes, math, time

import cv
import gtk3 as gtk
#import libfreenect_sync as freenect	# freenect_sync is broken on fedora!!
import threading



class ReducedPolygon( object ):
	def copy_buffer( self, memory ):	# clear local mem on copy?
		return cv.SeqSlice( self.poly2, cv.Slice(0,self.total), memory, 1 )
	def __del__(self):
		cv.ReleaseMemStorage( ctypes.pointer(self.mem1.POINTER) )
		cv.ReleaseMemStorage( ctypes.pointer(self.mem2.POINTER) )

	def __init__(self, contours, index, depth ):
		self.index = index		# used from other thread, so it knows to clear drawing surface on zero.
		self.depth = depth		# kinect depth level
		self.mem1 = cv.CreateMemStorage(0)
		self.mem2 = cv.CreateMemStorage(0)

		sizeof_contour = ctypes.sizeof( cv.Contour.CSTRUCT )

		self.poly1 = cv.ApproxPoly( 	 # pass1
			contours, 
			sizeof_contour, 
			self.mem1,
			cv.CV_POLY_APPROX_DP,
			3.0, 1 )

		self.poly2 = cv.ApproxPoly( 	 # pass2
			self.poly1, 
			sizeof_contour, 
			self.mem2,
			cv.CV_POLY_APPROX_DP,
			20.0, 1 )

		self.total = self.poly2.total

	def draw(self, image, lowres=False):

		cv.DrawContours(
			image, 
			self.poly1,
			(255,64,128), 	# external color
			(255,255,0),	# hole color
			1, # max levels
			1, # thickness
			cv.CV_AA, # linetype
			(0, 0)
		)
		if lowres:
			cv.DrawContours(
				image, 
				self.poly2,
				(128,64,64), 	# external color
				(255,255,0),	# hole color
				1, # max levels
				1, # thickness
				8, # linetype
				(0, 0)
			)


class Point(object):
	def __len__(self): return 2
	def __getitem__(self,key):
		if key == 0: return self.x
		elif key == 1: return self.y
		else: raise IndexError
	def __init__(self, x,y): self.x = x; self.y = y
	def scale( self, other ): return Point( self.x*other.x, self.y*other.y )
	def dot( self, other ): return self.x*other.x + self.y*other.y
	def length( self ): return math.sqrt( self.dot(self) )
	def angle( self, other ):
		dot = self.dot( other )
		length = self.length() * other.length()
		if not length: return .0
		else: return math.acos( dot / length )


class Shape(object):
	HAND = None
	storage_hull = cv.CreateMemStorage(0)
	storage_defects = cv.CreateMemStorage(0)

	def touches( self, other ):
		pt1, pt2 = self.rectangle
		if other.rectangle[0] == pt1 or other.rectangle[1] == pt2:
			if other not in self.touching: self.touching.append( other )
		return other in self.touching

	def contains( self, other ):
		#if self.touches( other ): return False
		s1, s2 = self.rectangle
		o1, o2 = other.rectangle
		if s1[0] <= o1[0] and s1[1] <= o1[1] and s2[0] >= o2[0] and s2[1] >= o2[1]:
			if other not in self.children:
				self.children.append( other )
				other.parents.append( self )
		return other in self.children

	def draw_bounds( self, image, mode='rectangle' ):
		if mode=='rectangle':
			cv.Rectangle(
				image, self.rectangle[0], self.rectangle[1],
				(64,0,128), 1, 8, 0
			)
		else:
			cv.Circle( image, self.center, int(self.width), (128,0,128), 2, 7, 0 )


	def draw_defects( self, image ):
		for d in self.defects:
			start,end,depth = d
			cv.Line(image, start, end,
				(0,64,128),
				1,
				8, 
				0
			)
			cv.Line(image, end, depth,
				(0,64,128),
				2,
				8, 
				0
			)
		if len( self.defects ) >= 2 and self.center_defects:
			cv.Circle( image, self.center_defects, 24, (255,255,0), 15, 7, 0 )

	def draw_variance(self, image ):
		if len(self.points) < 3: return
		color = (128,80,80); width = 1
		if self.avariance > 30: color = (255,155,155)
		elif self.avariance > 10: color = (255,80, 80)
		else: color = (225,60, 60)

		for i in range(0,len(self.points),2):
			w = self.avariance_points[i]
			a = self.points[i-1]
			b = self.points[i]
			cv.Line( image, (a.x,a.y), (b.x,b.y), color, width+int(w*0.15), 8, 0 )


	def __init__( self, polygon ):	#poly, depth ):
		self.polygon = polygon
		poly = polygon.poly2
		depth = polygon.depth
		self.depth = depth
		self.points = []
		self.angles = [.0]
		self.touching = []
		self.children = []
		self.parents = []
		xavg = []; yavg = []
		xmin = ymin = xmax = ymax = None

		for j in range( poly.total ):
			ptr = cv.GetSeqElem( poly, j )
			#point = ctypes.cast(_ptr, cv.Point.CAST )
			#x = point.contents.x; y = point.contents.y
			point = cv.Point( pointer=ptr, cast=True )
			x = point.x; y = point.y
			p = Point(x,y)

			if self.points:
				a = math.degrees(self.points[-1].angle( p ))
				self.angles.append( a )
				
			self.points.append( p )
			xavg.append( x ); yavg.append( y )
			if j == 0:
				xmin = xmax = x
				ymin = ymax = y
			else:
				if x < xmin: xmin = x
				if x > xmax: xmax = x
				if y < ymin: ymin = y
				if y > ymax: ymax = y

		self.avariance = .0
		self.avariance_points = [.0,.0]
		if self.angles:
			prev = self.angles[0]
			for a in self.angles[1:]:
				v = abs( prev - a )
				self.avariance_points.append( v )
				self.avariance += v
				prev = a
			#print 'variance', self.avariance
			#print 'variance-points', self.avariance_points
			#print 'len len', len(self.points), len(self.avariance_points)

		n = len(self.points)

		self.weight = ( sum(xavg)/float(n), sum(yavg)/float(n) )
		self.width = xmax - xmin
		self.height = ymax - ymin
		self.center = ( int(xmin + (self.width/2)), int(ymin + (self.height/2)) )
		self.rectangle = ( (xmin,ymin), (xmax,ymax) )

		self.dwidth = xmax - xmin
		self.dheight = ymax - ymin
		self.dcenter = ( xmin + (self.dwidth/2), ymin + (self.dheight/2) )
		self.drectangle = ( (xmin,ymin), (xmax,ymax) )

		self.defects = []
		self.center_defects = None

		self.convex = cv.CheckContourConvexity( poly )
		if not self.convex:
			T = 80
			dxavg = []; dyavg = []
			hull = cv.ConvexHull2( poly, self.storage_hull, 1, 0 )
			defects = cv.ConvexityDefects( poly, hull, self.storage_defects )

			n = defects.total
			for j in range( n ):
				D = cv.ConvexityDefect( pointer=cv.GetSeqElem(defects,j), cast=True )
				s = D.start.contents
				e = D.end.contents
				d = D.depth_point.contents
				start	= ( s.x, s.y )
				end	= ( e.x, e.y )
				depth 	= ( d.x, d.y )

				## ignore large defects ##
				if abs(end[0] - depth[0]) > T or abs(end[1] - depth[1]) > T or abs(start[0] - end[0]) > T or abs(start[1] - end[1]) > T: 
					continue

				dxavg.append( depth[0] )
				dyavg.append( depth[1] )
				self.defects.append( (start, end, depth) )

			xmin = ymin = 999999
			xmax = ymax = -1
			if self.defects:
				n = len(self.defects)
				self.center_defects = ( int(sum(dxavg)/float(n)), int(sum(dyavg)/float(n)) )
				for j,f in enumerate( self.defects ):
					s,e,d = f
					if s[0] < xmin: xmin = s[0]
					if e[0] < xmin: xmin = e[0]
					if s[0] > xmax: xmax = s[0]
					if e[0] > xmax: xmax = e[0]
					if s[1] < ymin: ymin = s[1]
					if e[1] < ymin: ymin = e[1]
					if s[1] > ymax: ymax = s[1]
					if e[1] > ymax: ymax = e[1]

				self.dwidth = xmax - xmin
				self.dheight = ymax - ymin
				self.dcenter = ( xmin + (self.dwidth/2), ymin + (self.dheight/2) )
				self.drectangle = ( (xmin,ymin), (xmax,ymax) )

		cv.ClearMemStorage( self.storage_hull )
		cv.ClearMemStorage( self.storage_defects )



class Kinect( object ):
	BUFFER = []
	PREVIEW_IMAGE = None
	DEPTH16RAW = cv.CreateImage((640,480), cv.IPL_DEPTH_16S, 1)

	## gui options ##
	show_depth = False
	sweeps = 16
	sweep_step = 2
	sweep_begin = 80

	@classmethod
	def toggle(self, button, name):
		setattr(self, name, button.get_active())
	@classmethod
	def adjust( self, adj, name ):
		setattr(self, name, adj.get_value() )

	def __init__(self):
		self.active = False
		self._lenpix = 480 * 640 * 2
		self.buffer_type = ctypes.c_void_p
		self.buffer = self.buffer_type()
		self.pointer = ctypes.pointer( self.buffer )

		status = -1
		if False:	# TODO get kinect working with Fedora
			#context = freenect.context()
			context = freenect._freenect_context()
			usbctx = freenect.libusb_context()
			uptr = ctypes.pointer( usbctx.POINTER )
			freenect.libusb_init( uptr )
			ptr = ctypes.pointer( context.POINTER )
			status = freenect.init(ptr, usbctx)
			print('init status', status )
			numdevs = freenect.num_devices( context )
			print( 'num devices', numdevs )
			assert numdevs
			assert 0
			#print( 'KINECT: setting leds' )
			#status = freenect.set_led( freenect.LED_YELLOW, 0 )
			#status = -1
			#status = freenect.set_led( 0, freenect.LED_YELLOW )
			print('KINECT STATUS',status)
		if status < 0: self.ready = False
		else: self.ready = True

	def loop(self, lock):
		self.active = True
		self.loops = 0

		print( 'starting thread - freenect sync' )
		while self.active:
			self.loops += 1
			print('new cap')
			status = freenect.sync_get_depth( ctypes.pointer(self.pointer), 0, 0, 
				freenect.FREENECT_DEPTH_11BIT
			)
			if status: break

			print('cap ok')
			lock.acquire()
			print('data set...')
			cv.SetData( Kinect.DEPTH16RAW, self.pointer, 640*2 )
			cv.ConvertScale( Kinect.DEPTH16RAW, ProcessContours.DEPTH8, 0.18, 0 )

			print('...data set done')
			lock.release()
			time.sleep(0.01)
		freenect.sync_set_led( freenect.LED_OFF, 0 )
		freenect.sync_stop()
		print( 'exit thread - freenect sync', self.loops )


class ProcessShapes( object ):
	def __init__(self):
		self.active = False
		self.contours_image = cv.cvCreateImage((640,480), 8, 3)
		self.dwidth = 240
		self.dheight = 180
		self.loops = 0

		self.preview_image = cv.CreateImage((self.dwidth,self.dheight), cv.IPL_DEPTH_8U, 3)

		n = self.dwidth * self.dheight * 3
		raw = (ctypes.c_ubyte * n)()
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

	def update_frame( self, shapes ):
		print('update_frame')
		img = self.contours_image

		for s1 in shapes:
			for s2 in shapes:
				if s1 is not s2:
					s1.touches( s2 )
					s1.contains( s2 )		# parents, children

		#Shape.HAND = None
		hand = head = None
		for s in shapes:
			## these numbers are magic
			if len(s.children) >= 8 and s.width < 200 and s.height < 180 and s.width > 100 and s.height > 150:
				if not s.touching:
					head = s  # end of magic
					break

		best = []; maybe = []; poor = []
		for s in shapes:
			if not s.defects: continue
			if head and s in head.children: continue

			if len(s.touching) >= 2 and len(s.defects) >= 2:
				if s.dwidth < 320 and s.dheight < 340:
					best.append( s )
					if not hand or ( s.dwidth <= hand.dwidth and s.dheight <= hand.dheight ):
						hand = s
				else: maybe.append( s )
			elif len(s.defects) >= 2:
				poor.append( s )

		if hand: Shape.HAND = hand
		if not hand:
			if maybe:
				for s in maybe:
					if not hand or ( s.dwidth <= hand.dwidth and s.dheight <= hand.dheight ):
						hand = s

			if not hand and poor and Shape.HAND:
				hx,hy = Shape.HAND.center_defects
				for s in poor:
					if not hand or ( s.dwidth <= hand.dwidth and s.dheight <= hand.dheight ):
						sx,sy = s.center_defects
						if abs(hx-sx) < 20 and abs(hy-sy) < 20:
							hand = s

		print('ready')
		#self.lock.acquire()
		if 0:		# threadsafe?
			if head: head.draw_bounds( self.contours_image, 'circle' )
			if hand:
				hand.draw_defects( self.contours_image )
		self.lock.acquire()
		cv.SetZero( self.contours_image )
		for s in shapes:
			print('-------------drawing poly',s)
			s.polygon.draw( self.contours_image )
		print('DONE')
		#self.lock.acquire()
		cv.cvResize( self.contours_image, self.preview_image, True )
		if Kinect.show_depth:
			cv.Add( self.preview_image, ProcessContours.DEPTH240, self.preview_image )

		Kinect.PREVIEW_IMAGE = self.preview_image
		self.update_preview_image( self.preview_image.imageData )
		self.lock.release()

	def update_preview_image(self, pointer ):
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

	def iterate(self, lock):
		self.lock = lock
		frame = []
		trash = []
		self.loops += 1
		batch = []

		i = 0
		while Kinect.BUFFER:	# and i < 30:
			batch.append( Kinect.BUFFER.pop() )
			i += 1

		if batch: print('batch - proc shapes', len(batch) )

		frame = [ Shape(polygon) for polygon in batch ]
		self.update_frame( frame )		# final draws and shows




class ProcessContours( object ):
	DEPTH640 = cv.CreateImage((640,480), cv.IPL_DEPTH_8U, 3)
	#DEPTH320 = cv.CreateImage((320,240), cv.IPL_DEPTH_8U, 3)
	DEPTH240 = cv.CreateImage((240,180), cv.IPL_DEPTH_8U, 3)
	DEPTH8 = cv.CreateImage((640,480), 8, 1)

	def __init__(self):
		self.active = False
		#self.depth8 = cv.CreateImage((640,480), 8, 1)
		self.depth8 = ProcessContours.DEPTH8

		self.sweep_images = [ cv.CreateImage((640,480), 8, 1) for i in range(64) ]
		self.storage = cv.CreateMemStorage(0)

	def loop(self, lock):
		print( 'starting thread - ProcessContours' )
		self.active = True
		self.loops = 0
		while self.active:
			self.loops += 1
			print('.....contours thread... locking, convert scale...')
			lock.acquire()
			#lock.release()	# bug was here
			cv.CvtColor(self.depth8, self.DEPTH640, cv.CV_GRAY2RGB)
			cv.Resize( self.DEPTH640, self.DEPTH240, False )
			lock.release()	# fixed Dec 6th 2011
			print('.....contours thread ok.....')
			# blur helps?
			#cv.Smooth( self.depth8, self.depth8, cv.CV_BLUR, 16, 16, 0.1, 0.1 )
			#cv.Smooth( self.depth8, self.depth8, cv.CV_GAUSSIAN, 13, 13, 0.1, 0.1 )

			thresh = Kinect.sweep_begin
			index = 0
			#for img in self.sweep_thresh:
			for i in range( int(Kinect.sweeps) ):
				if thresh >= 255: break

				img = self.sweep_images[ i ]
				cv.ClearMemStorage( self.storage )

				cv.Threshold( self.depth8, img, thresh, 255, cv.CV_THRESH_BINARY_INV )
				#cv.Canny( img, img, 0, 255, 3 )	# too slow
				seq = cv.CvSeq()
				contours = ctypes.pointer( seq.POINTER )

				cv.FindContours(
					img,
					self.storage,
					contours,
					ctypes.sizeof( cv.Contour.CSTRUCT ),
					cv.CV_RETR_EXTERNAL,
					cv.CV_CHAIN_APPROX_SIMPLE, 
					(0,0) 
				)
				#print( contours.contents.contents.total )
				_total = 0
				try: _total = contours.contents.contents.total
				except ValueError:	#ValueError: NULL pointer access
					thresh += int(Kinect.sweep_step)
					continue
				P = ReducedPolygon( contours.contents, index, thresh )

				lock.acquire()
				Kinect.BUFFER.append( P )
				lock.release()

				index += 1
				thresh += int(Kinect.sweep_step)
			print('==========proc shapes.iterate============')
			self.proc_shapes.iterate( lock )
			time.sleep(0.01)

		print( 'thread exit - ProcessContours', self.loops )




class Widget(object):
	def exit(self, arg):
		print( 'exit' )
		self.active = False
		for thread in [self.kinect, self.proc_contours, self.proc_shapes]:
			thread.active = False
		freenect.sync_set_led( freenect.LED_OFF, 0 )
		freenect.sync_stop()

	def start_threads( self, lock ):
		if self.kinect.ready:
			threading._start_new_thread( self.kinect.loop, (lock,) )
			threading._start_new_thread( self.proc_contours.loop, (lock,) )
			#threading._start_new_thread( self.proc_shapes.loop, (lock,) )
		else:
			print( 'Warning: no kinect devices found' )

	def __init__(self, parent ):
		self.active = True

		self.kinect= Kinect()
		self.proc_contours = ProcessContours()
		self.proc_shapes = ProcessShapes()
		self.proc_contours.proc_shapes = self.proc_shapes

		self.root = root = gtk.HBox()
		root.set_border_width( 3 )
		parent.add( root )

		self.dnd_container = gtk.EventBox()
		self.dnd_container.add( self.proc_shapes.preview_image_gtk )
		root.pack_start( self.dnd_container, expand=False )

		page = gtk.VBox()
		root.pack_start( page, expand=True )

		row = gtk.HBox(); page.pack_start( row, expand=False )
		b = gtk.CheckButton('show depth')
		row.pack_start( b )
		b.connect('toggled', Kinect.toggle, 'show_depth')


		row = gtk.HBox(); page.pack_start( row, expand=False )
		adjust = gtk.Adjustment( value=Kinect.sweeps, lower=1, upper=64 )
		adjust.connect('value-changed', Kinect.adjust, 'sweeps')
		scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
		scale.set_digits(0)
		row.pack_start( scale )

		row = gtk.HBox(); page.pack_start( row, expand=False )
		adjust = gtk.Adjustment( value=Kinect.sweep_step, lower=1, upper=8 )
		adjust.connect('value-changed', Kinect.adjust, 'sweep_step')
		scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
		scale.set_digits(0)
		row.pack_start( scale )

		row = gtk.HBox(); page.pack_start( row, expand=False )
		adjust = gtk.Adjustment( value=Kinect.sweep_begin, lower=0, upper=255 )
		adjust.connect('value-changed', Kinect.adjust, 'sweep_begin')
		scale = gtk.HScale( adjust ); scale.set_value_pos(gtk.POS_RIGHT)
		scale.set_digits(0)
		row.pack_start( scale )

if __name__ == '__main__':
	gtk.init()
	win = gtk.Window()
	widget = Widget( win )
	win.set_title( 'kinect-gtk' )
	win.connect('destroy', widget.exit )
	win.show_all()

	lock = threading._allocate_lock()
	widget.start_threads( lock )

	while widget.active:
		if gtk.gtk_events_pending():
			while gtk.gtk_events_pending():
				lock.acquire()
				gtk.gtk_main_iteration()
				lock.release()




