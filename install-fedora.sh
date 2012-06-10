#!/bin/bash
sudo yum clean all

sudo yum install SDL-devel
sudo yum install opencv-devel
sudo yum install ode-devel
sudo yum install openal-devel
sudo yum install fluidsynth-devel
sudo yum install gdouros-symbola-fonts

sudo yum install libjpeg-devel
sudo yum install openjpeg-devel
sudo yum install libpng-devel
sudo yum install freetype-devel
sudo yum install openexr-devel
sudo yum install libXi-devel

sudo yum install chromium
#sudo yum install google-chrome-stable

sudo yum install bluez-libs-devel
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
