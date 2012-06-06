#!/bin/bash
bits=`getconf LONG_BIT`
if [ $bits -eq 32 ]; then
	bin/blender32bits/blender $1 -noaudio --python ./pyppet/helloworld-dnd.py
else
	bin/blender64bits/blender $1 -noaudio --python ./pyppet/helloworld-dnd.py
fi

