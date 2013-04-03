#!/bin/bash
sudo ~/blender2.63/blender --background --python ./pyppet/server_api.py --port=80 --ip=$1
