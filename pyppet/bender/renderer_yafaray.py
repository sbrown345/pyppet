#!/usr/bin/python
# yafaray rendering backend - copyright 2013 - Brett Hartshorn
# License: "New" BSD

'''
Fedora 17:
  yum install swig libxml2-devel python-devel qt-devel

Installing Yafaray Python:
  change Core-master/src/bindings/CMakeLists.txt : line 40
    set(REQUIRED_PYTHON_VERSION 2.7)
  notes:
    . the python bindings will not load the yafaray core libraries from /usr/local/lib
      you need to install to /usr/lib
    . after compiling you need to copy these to your site-packages
      Core-master/bindings/python/yafarayinterface.py
      Core-master/bindings/python/_yafarayinterface.so


'''

import yafarayinterface