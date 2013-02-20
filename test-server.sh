#!/bin/bash
echo $1

firefox -new-instance -new-window http://localhost:8080 &
#blender $1 -noaudio --python ./pyppet/Server.py

~/b26_54590_32bit_noomp/blender --python ./pyppet/Server.py
