## Installing: ##
> install and/or compile these libraries: gtk3, opencv, SDL, libfreenect, ode (open dynamics engine), wnck, fftw3, openAL.

> Ubuntu:
> > you can apt-get all of the required librarys


> Wnck:
> > sudo apt-get install python-wnck


> Libfreenect:
> > git clone https://github.com/OpenKinect/libfreenect.git
> > cd libfreenect
> > mkdir build
> > cd build
> > cmake -g "Unix Makefiles" ../.
> > make
> > sudo make install


> Wiiuse:
> > apt-get install bluez bluetooth
> > git clone http://github.com/rpavlik/wiiuse.git