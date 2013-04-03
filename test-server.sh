#!/bin/bash
echo $1

#firefox -new-instance -new-window http://localhost:8080 &
#~/b26_54590_32bit_noomp/blender --python ./pyppet/Server.py
#~/b26_54590_32bit_noomp/blender --background --python ./pyppet/server_api.py
~/blender2.63/blender --background --python ./pyppet/server_api.py --python-console
