#!/bin/bash

# it is required that chrome is run first from this shell script - allows proper port shutdown #
#killall chromium-browser
#chromium-browser &
killall firefox
#firefox -new-instance -new-window http://localhost:8080 &


rm -rf /tmp/texture-cache

#python IcarusTouch/src/main.py &

## assumes that Nautilus opens with window named "Home"
#nautilus &
#gimp --no-splash &

## --window-borderless is not compatible with wnck hack
#~/Blender2.6/blender --window-borderless --python ./pyppet.py
#wine ~/blender-mingw/blender.exe --python ./pyppet.py
echo $1

#bits=`getconf LONG_BIT`
#if [ $bits -eq 32 ]; then
#	bin/blender32bits/blender $1 -noaudio --python ./pyppet/pyppet.py
#else
#	bin/blender64bits/blender $1 -noaudio --python ./pyppet/pyppet.py
#fi

#--------------------------------------------------------------------------------#
# need to use local blender because the one in ubuntu repos do not include Collada
#blender $1 --python ./pyppet/pyppet.py

## to run DerFish'es build: apt-get install python3.3
~/b26_54590_32bit_noomp/blender $1 --python ./pyppet/pyppet.py


## this fails even with gtk2, when trying create a gtk element
#(blender:6889): GLib-WARNING **: unknown option bit(s) set
#(blender:6889): GLib-CRITICAL **: g_regex_match_full: assertion `regex != NULL' failed
#~/blender.org-265-crashes/blender $1 -noaudio --python ./pyppet/pyppet.py

