#!/bin/bash
echo $1

#firefox -new-instance -new-window http://localhost:8080 &
#~/b26_54590_32bit_noomp/blender --python ./pyppet/Server.py
~/b26_54590_32bit_noomp/blender --python ./pyppet/server_api.py
