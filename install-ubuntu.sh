#!/bin/bash

sudo apt-get install libfreenect-dev libfftw3-dev libCV-dev libhighgui-dev
sudo apt-get install libsdl-dev libopenal-dev libilmbase-dev libopenexr-dev
sudo apt-get install libopenjpeg-dev libspnav-dev python-wnck
sudo apt-get install libgtk-3-dev libfluidsynth-dev libode-dev libmlt-dev libavcodec-dev libavformat-dev

sudo apt-get install bluez bluetooth libbluetooth3-dev git cmake

cd /tmp
git clone http://github.com/rpavlik/wiiuse.git
cd wiiuse
mkdir build
cd build
cmake -g "Unix Makefiles" ../.
make
sudo make install
