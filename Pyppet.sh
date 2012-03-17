#!/bin/bash
## note: chrome must not have "system titlebar and borders" shown to xembed
google-chrome &
## assumes that Nautilus opens with window named "Home"
#nautilus &
#gimp --no-splash &

## --window-borderless is not compatible with wnck hack
#~/Blender2.6/blender --window-borderless --python ./pyppet.py
#wine ~/blender-mingw/blender.exe --python ./pyppet.py
echo $1
~/Blender2.6/blender $1 -noaudio --python ./pyppet/pyppet.py
