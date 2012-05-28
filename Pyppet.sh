#!/bin/bash
## note: chrome must not have "system titlebar and borders" shown to xembed
#google-chrome &
killall chromium-browser
chromium-browser localhost:8080 &

#python IcarusTouch/src/main.py &

## assumes that Nautilus opens with window named "Home"
#nautilus &
#gimp --no-splash &

## --window-borderless is not compatible with wnck hack
#~/Blender2.6/blender --window-borderless --python ./pyppet.py
#wine ~/blender-mingw/blender.exe --python ./pyppet.py
echo $1

bits=`getconf LONG_BIT`
if [ $bits -eq 32 ]; then
	bin/blender32bits/blender $1 -noaudio --python ./pyppet/pyppet.py
else
	bin/blender64bits/blender $1 -noaudio --python ./pyppet/pyppet.py
fi
