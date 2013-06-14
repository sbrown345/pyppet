#!/usr/bin/python
# Bender - copyright 2013 - Brett Hartshorn
# License: "New" BSD

import os, sys, time
import collections

from bender import rna
from bender.importers import import_blend

try:
	import yafarayinterface
	USE_YAFARAY = True
except:
	print('WARN: yafaray python bindings not found')
	USE_YAFARAY = False

if USE_YAFARAY:
	import renderer_yafaray as yaf


class Bender(object):
	def __init__(self):
		self.dbs = collections.OrderedDict()

	def load_blend(self, path):
		bf = import_blend.load( path )
		rna_db = rna.RNA_Database( bf.database )
		self.dbs[path] = rna_db
		return rna_db





if __name__ == '__main__':
	b = Bender()
	if len(sys.argv) > 1:
		for arg in sys.argv:
			if arg.endswith('.blend'):
				db = b.load_blend( arg )
		print(b)
		print(db)
	else:
		db = b.load_blend( '~/cube.blend' )	
		m = db.meshes['Cube']
		print(m)
		print('-'*80)
		print('Vertices:')
		for vert in m.vertices:
			print(vert)

		print('-'*80)
		print('Edges:')
		for edge in m.edges:
			print(edge)

		print('-'*80)
		print('Materials:')
		if m.materials:
			for name in m.materials:
				material = m.materials[name]
				print(name)
				#print(material)

