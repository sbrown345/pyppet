#!/bin/bash
gimp &
bits=`getconf LONG_BIT`
if [ $bits -eq 32 ]; then
	bin/blender32bits/blender -noaudio --python ./pyppet/helloworld-gimp.py
else
	bin/blender64bits/blender -noaudio --python ./pyppet/helloworld-gimp.py
fi

