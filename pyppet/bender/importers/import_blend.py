#!/usr/bin/python
# simple Blender file loader - copyright 2013 - Brett Hartshorn
# License: "New" BSD

'''
Reads Blender's binary file format (.blend),
and converts the data into simple Python objects.

'''

import os, sys
import struct
import collections

DEBUG = '--debug' in sys.argv

if sys.version_info.major < 3:
	NULL_CHAR = '\0'
	_unpack_c_string_char = NULL_CHAR
else:
	NULL_CHAR = bytes( chr(0), 'ascii' )
	_unpack_c_string_char = 0

def unpack_c_string(data, offset):
	size = 0
	while data[offset+size] != _unpack_c_string_char: size += 1
	return struct.Struct(str(size)+'s').unpack_from(data, offset)[0].decode("iso-8859-1")

class Header(object):
	'''
	the header is in the first 12 bytes of all blend files
	'''
	_header_format = struct.Struct("7s1s1s3s")
	assert _header_format.size == 12


	def debug(self):
		print(self.identifier)
		print(self.pointer_size)
		print(self.endianess)
		print(self.version)

	def __init__(self, file):
		a = self._header_format.unpack( 
			file.read(self._header_format.size) 
		)
		self.identifier = a[0].decode()
		assert self.identifier == 'BLENDER'

		if a[1].decode() == '_':
			self.pointer_size = 4 # 32bit CPU
		elif a[1].decode() == '-':
			self.pointer_size = 8 # 64bit CPU
		else:
			raise RuntimeError('invalid pointer size')

		if a[2].decode() == 'v':
			self.endianess = 'LITTLE'
		elif a[2].decode() == 'V':
			self.endianess = 'BIG'
		else:
			raise RuntimeError('invalid endian type')

		self.version = int(a[3].decode())

		if self.pointer_size == 4:
			if self.endianess == 'LITTLE':
				s = struct.Struct("<4sIIII")
			else:
				s = struct.Struct(">4sIIII")

		else:
			if self.endianess == 'LITTLE':
				s = struct.Struct("<4sIQII")
			else:
				s = struct.Struct(">4sIQII")

		self.block_format_struct = s


class Block(object):
	'''
	more info: source/blender/blenloader/intern/writefile.c

	Data-Block:
		<code>         4 chars
		<len>          int,  len data after BHead
		<old>          void,  old pointer
		<SDNAnr>       int
		<nr>           int, in case of array: amount of structs
		data...

	'''
	def __init__(self, file, block_format_struct):
		self.code = None
		self.size = None
		self.address = None
		self.sdna_index = None
		self.count = None
		self.offset = None
		self.data = None

		data = file.read( block_format_struct.size )
		assert len(data) > 15  # no support for old blend files

		a = block_format_struct.unpack( data )
		self.code = a[0].decode().split('\0')[0]  ## block "Code"

		if self.code != 'ENDB':     # ENDB is the last block
			self.size = a[1]	    # total size of the block data (after the header)
			self.address = a[2]     # old pointer
			self.sdna_index = a[3]  # index of sdna struct type
			self.count = a[4]       # number of structs (array of structs)
			self.offset = file.tell()
			## read raw bytes ##
			self.data = file.read( self.size )

	def debug(self):
		for n in 'code size address sdna_index count offset'.split():
			print('%s = %s'%(n, getattr(self,n)))

class BlenderFile(object):
	def unpack_pointer(self, data, offset, array=1):
		return self._pointer_struct.unpack_from(data, offset)[0]

	UNPACK_CODES = {
		'ushort'	: 'H',
		'short'		: 'h',
		'uint'		: 'I',
		'int'		: 'i',
		'ulong'		: 'Q',
		'long'		: 'q',
		'float'		: 'f',

		'uint64_t'	: 'Q',
		'int64_t'	: 'q',
		'uint32_t'	: 'I',
		'int32_t'	: 'i',
		'uint16_t'	: 'H',
		'int16_t'	: 'h',

		## strings are special cases ##
		#'uchar'		: 'B',  ## unsigned byte
		#'char'		: 's',  ## array of char - this could also be "c"
	}
	def unpack(self, ctype, data, offset, array=None, dimensions=None):
		if dimensions:
			array = 1
			for dim in dimensions: array *= dim
			fmt = self._endian + str(array) + self.UNPACK_CODES[ctype]
		elif array and array > 1:
			fmt = self._endian + str(array) + self.UNPACK_CODES[ctype]
		else:
			fmt = self._endian + self.UNPACK_CODES[ctype]

		if fmt not in self._unpack_cache: self._unpack_cache[ fmt ] = struct.Struct( fmt )
		s = self._unpack_cache[ fmt ]

		if not array or array == 1:
			return s.unpack_from( data, offset )[0]

		elif dimensions and len(dimensions)==2:
			a = s.unpack_from( data, offset )
			x,y = dimensions
			r = []
			for i in range(x):
				r.append( [] )
				for j in range(y):
					v = a[ i*j ]
					r[-1].append( v )
			return r

		elif array > 1:
			return list( s.unpack_from(data,offset) )

		else:
			raise NotImplemented


	def __init__(self, file, lazy_attributes=False):
		'''
		loading with lazy_attributes is faster if you only want
		to read minimal data from a .blend
		'''
		self._unpack_cache = {}		# format : struct.Struct
		self.header = Header( file )
		if self.header.endianess == 'LITTLE':
			self._endian = '<'
			self._uint_struct = struct.Struct('<I')
			self._ulong_struct = struct.Struct('<Q')
		else:
			self._endian = '>'
			self._uint_struct = struct.Struct('>I')
			self._ulong_struct = struct.Struct('>Q')

		if self.header.pointer_size == 4:
			self._pointer_struct = self._uint_struct
		else:
			self._pointer_struct = self._ulong_struct


		self.blocks = []
		self.SDNA = None

		block = Block(file, self.header.block_format_struct)
		while block.code != 'ENDB':
			if block.code == 'DNA1':
				self.SDNA = SDNA(block, self)
			else:
				self.blocks.append( block )
			block.debug()
			print('-'*80)
			block = Block( file, self.header.block_format_struct)

		print('num blocks', len(self.blocks))
		assert self.SDNA

		self.objects = {}  # address : object
		types = {}

		## TODO FIXME - for some reason too much or too little bytes are unpacked
		## this might be caused by *void being read as zero bytes
		self.invalid_objects = []

		for block in self.blocks:
			proto = self.SDNA.prototypes[ block.sdna_index ]
			assert block.address not in self.objects
			size = len(block.data)

			if size == proto.size and block.count==1:  ## normal struct
				ob = proto( block.data )
				self.objects[ block.address ] = ob
				if proto.name not in types: types[ proto.name ] = []
				types[proto.name].append(ob)

			elif size > proto.size:  ## if size is larger than the typedef, then it is an array of struct
				items = []
				num = int(size / proto.size)
				if num != block.count:
					## this only happens with 4 blocks in the default scene,
					## blocks: REND, TEST, and two DATA blocks
					## they all have an sdna_index of zero, so thats probably wrong as well.
					print('WARN: block array count != len(bytes)/proto.size')
					print('size/proto.size = %s | block.count = %s' %(num,block.count))
					num = int(block.count)

				for i in range( num ):
					a = i * proto.size
					b = a + proto.size
					o = proto( block.data[a:b] )
					items.append( o )
				self.objects[ block.address ] = tuple( items )

			elif size < proto.size and proto.name == 'Link':
				## a Link struct is a special case where the block size be less than the sdna struct size,
				## this must mean that the "next" pointer is null, as a quick fix we just pad the data
				## with null bytes.
				#print('LINK HACK!', block.count)
				diff = proto.size - size
				ob = proto( block.data+(NULL_CHAR*diff) )
				self.objects[ block.address ] = ob
				if proto.name not in types: types[ proto.name ] = []
				types[proto.name].append(ob)

			else:
				#self.invalid_objects.append( block )
				#self.objects[ block.address ] = 'INVALID(required-size=%s, size=%s)'%(proto.size,size)
				print( proto.name )
				raise RuntimeError


		for name in types:
			items = types[name]
			print(name, len(items))
			if not lazy_attributes:
				for ob in items:
					with ob:
						## triggers read and cache all attributes
						pass

		self.database = types

		if self.invalid_objects:
			print('ERROR: invalid blocks or dna-structures: %s' %len(self.invalid_objects))
			raise RuntimeError


class Object(object):
	def __init__(self, dna, data):
		self.__dna = dna
		self.__data = data
		self.__cached = False
		self.__with_temp = []
		self.dna_type = dna.name
		assert 'dna_type' not in dna.fields.keys()

	def __exit__(self, etype, evalue, etraceback):
		while self.__with_temp:
			a = self.__with_temp.pop()
			with a: pass

	def __enter__(self):
		if not self.__cached:
			self.__with_temp = []
			for n in dir(self):
				a = getattr(self,n)
				if DEBUG: print(n,a)
				if isinstance(a,Object):
					self.__with_temp.append(a)
				elif type(a) is tuple:
					self.__with_temp.extend(a)
			self.__cached = True
			del self.__data  # saves memory
			#del self.__getattr__ # no longer required
		return self

	def __repr__(self):
		return '<%s at %s>'%(self.dna_type, id(self))

	def __str__(self):
		names = self.__dna.fields.keys()
		if not names:
			return '<%s>'%self.__dna.name
		else:
			m = len(max(names)) + 10
			a = ['<%s:'%self.__dna.name]
			for name in names:
				dna = self.__dna.fields[name]
				s = '  ' + name
				s += ' ' * ( m - len(name) )
				if dna.is_method: s += '(@'
				elif dna.is_pointer: s += '(*'
				else: s += '('
				s += '%s  %s)'%(dna.type, dna.size)
				if dna.dimensions: s += ' array:%s' %dna.dimensions
				if self.__cached:
					attr = getattr(self,name)
					if attr is not None:
						s += '\t\t= %s'%repr(attr)
				a.append(s)

			a.append('>')
			return '\n'.join(a)

	def __dir__(self):
		return list(self.__dna.fields.keys())

	def __getitem__(self, key):
		return getattr(self, key)

	def __getattr__(self, name):
		if name in self.__dna.fields:
			a = self.__dna.get(self.__data, name)
			setattr(self, name, a)	## cache value
			return a
		else:
			raise AttributeError

class DNA_Struct(object):
	'''
	acts like a "class prototype"
	'''
	def __call__(self, data):
		'''
		data can be from a raw block, or raw data from a struct field
		'''
		assert len(data) == self.size
		return Object(self, data)

	def __init__(self, name, fields, blenderfile, size=None):
		self.name = name
		self.fields = fields
		self.blenderfile = blenderfile
		self.size = size  ## total size of all fields - for debugging

	def get(self, data, name):
		assert name in self.fields
		dna = self.fields[ name ]
		offset = dna.offset

		if DEBUG:
			print('-'*80)
			print('object type: %s'%self.name )
			print('dna getting: %s'%name)
			print('dna offset: %s'%offset)
			if len(data) < 256: print(data)
			print('dna len data: %s'%len(data))

		if dna.is_method:
			pass
		elif dna.is_pointer and not dna.is_method:
			ptr = self.blenderfile.unpack_pointer(data,offset)  ## special case for pointer
			if not ptr:
				return None
			elif ptr not in self.blenderfile.objects:  ## TODO fixme
				#print('ERROR invalid pointer', name, ptr)
				#raise RuntimeError
				## this might be an index into a pointer?
				return None
			else:
				return self.blenderfile.objects[ ptr ]

		elif dna.type in self.blenderfile.UNPACK_CODES:
			return self.blenderfile.unpack(
				dna.type, 
				data, 
				offset,
				array=dna.array_length,
				dimensions=dna.dimensions)

		elif dna.type == 'char':
			s = struct.Struct(str(dna.array_length)+'s')
			a = s.unpack_from(data, offset)[0]
			return a.split(NULL_CHAR)[0].decode("iso-8859-1")

		elif dna.type in self.blenderfile.SDNA.structures:
			proto = self.blenderfile.SDNA.structures[ dna.type ]
			chunk = data[offset:]
			size = len(chunk)

			if size > proto.size:
				## there are cases where this is oversized, and only the first element is used,
				## example: object.id
				## but there is no way to test the other items to see if they are null,
				## we do not want a list-like-class, where the list acts like a C array, ie.
				## ob.id.name would become a shorthand for ob.id[0].name
				## see rna.py for cases that take the first item of the list, and reassign as an attribute.
				items = []
				num = int(size / proto.size)
				for i in range( num ):
					a = i * proto.size
					b = a + proto.size
					o = proto( chunk[a:b] )
					items.append( o )

				return tuple(items)

			elif size == proto.size:
				return proto( chunk )

			else:
				raise NotImplemented

		else:  ## this should not happen.
			print(dna)
			raise NotImplemented

class DNA_Name(object):
	def __init__(self, name):
		self._name = name
		self.name = name.replace('*','').replace('(','').replace(')','')
		if '*' in name: self.is_pointer = True
		else: self.is_pointer = False
		if '(*' in name: self.is_method = True
		else: self.is_method = False
		self.array_length = 1
		self.dimensions = []

		if '[' in name:
			a = self.name.split('[')
			self.name = a[0]
			for b in a[1:]:
				assert b.endswith(']')
				self.dimensions.append( int(b[:-1]) )

			for dim in self.dimensions:
				self.array_length *= dim

class DNA_Type(object):
	def __init__(self, name):
		self.name = name
		self.size = None

class DNA_Field(object):
	def __init__(self, dna_name, dna_type, offset=None):
		self.is_pointer = dna_name.is_pointer
		self.is_method = dna_name.is_method
		self.dimensions = dna_name.dimensions
		self.type = dna_type.name
		self.size = dna_type.size
		self.array_length = dna_name.array_length
		self.offset = offset

	def __str__(self):
		s = ['{DNA_Field: '+self.type]
		for n in 'is_pointer is_method size array_length dimensions'.split():
			s.append('  %s = %s'%(n,getattr(self,n)))
		s.append('}')
		return '\n'.join(s)

class SDNA(object):
	def _align(self):
		a = self._offset % 4
		if a: self._offset = self._offset + (4-a)

	def _unpack_num_names(self):
		num = self.blenderfile.unpack(
			'uint',
			self.block.data,
			self._offset
		)
		self._offset += 4
		return num

	def _parse_names( self ):
		num = self._unpack_num_names()
		res = []
		for i in range(num):
			a = unpack_c_string( self.block.data, self._offset )
			res.append( a )
			self._offset += len(a)+1
		self._align()
		self._offset += 4
		return res


	def __init__(self, block, blenderfile):
		self.block = block
		self.blenderfile = blenderfile
		self.prototypes = []  ## list of prototypes
		self.structures = {}  ## dict of prototypes

		self._offset = 8  ## set initial offset ##
		names = [DNA_Name(name) for name in self._parse_names()]
		types = [DNA_Type(name) for name in self._parse_names()]
		for t in types:  ## read length of types
			t.size = blenderfile.unpack('short', self.block.data, self._offset)
			## this can happen with *void and other pointers
			#if not t.size:
			#	#assert t.name == 'void'
			#	t.size = blenderfile.header.pointer_size

			self._offset += 2
		self._align()
		self._offset += 4

		## get number of structures ##
		num = self._unpack_num_names()
		for i in range(num):
			a = blenderfile.unpack( 'short', self.block.data, self._offset, array=2 )
			self._offset += 4
			type_name = types[ a[0] ].name  ## struct type name ##

			fields = collections.OrderedDict() ## save order of fields ##
			field_offset = 0
			num_fields = a[1]
			for j in range(num_fields):
				b = blenderfile.unpack( 'short', self.block.data, self._offset, array=2 )
				self._offset += 4
				dna_type = types[ b[0] ]
				dna_name = names[ b[1] ]

				if dna_type.size == 0 and not dna_name.is_pointer:  ## TODO FIXME
					print('WARN: zero byte field is not a pointer:')
					print(dna_type)
					print(dna_name)

				assert dna_name.name not in fields
				dna_field = DNA_Field(
					dna_name,
					dna_type,
					offset=field_offset
				)
				fields[ dna_name.name ] = dna_field

				if dna_name.is_pointer or dna_name.is_method:
					field_offset += blenderfile.header.pointer_size * dna_name.array_length
				else:
					assert dna_type.size
					assert dna_name.array_length
					field_offset += dna_type.size * dna_name.array_length

					
			proto = DNA_Struct( type_name, fields, blenderfile, size=field_offset )
			self.prototypes.append( proto )
			assert type_name not in self.structures
			self.structures[ type_name ] = proto







## API ##
def load(path):
	file = open( os.path.expanduser(path), 'rb')
	return BlenderFile( file )



if __name__ == '__main__':
	if len(sys.argv) > 1:
		assert sys.argv[-1].endwith('.blend')
		path = sys.argv[-1]
	else:
		path = '~/cube.blend'

	bf = load( path )
	ob = bf.database['Object'][0]
	print(ob)
	print('-'*80)
	print('object name: ' + ob.id.name)
	print('data name: ' + ob.data.id.name)

	assert len(ob.loc)==3

	print('import_blend.py test done')
