#!/bin/bash
echo $1
bits=`getconf LONG_BIT`
if [ $bits -eq 32 ]; then
	bin/blender32bits/blender $1 -noaudio --python ./pyppet/pyppet.py -- pyppet-lite
else
	bin/blender64bits/blender $1 -noaudio --python ./pyppet/pyppet.py -- pyppet-lite
fi
