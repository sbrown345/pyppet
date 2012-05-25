#!/bin/bash
sudo yum clean all

sudo yum install SDL-devel
sudo yum install opencv-devel
sudo yum install ode-devel
sudo yum install openal-devel
sudo yum install fluidsynth-devel
sudo yum install gdouros-symbola-fonts

sudo yum install chromium
sudo yum install google-chrome-stable

#sudo apt-get install bluez bluetooth libbluetooth3-dev git cmake
sudo yum install git cmake

cd /tmp
git clone http://github.com/rpavlik/wiiuse.git
cd wiiuse
mkdir build
cd build
cmake -g "Unix Makefiles" ../.
make
sudo make install
