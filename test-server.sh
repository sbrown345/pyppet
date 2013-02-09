#!/bin/bash
echo $1
blender $1 -noaudio --python ./pyppet/Server.py