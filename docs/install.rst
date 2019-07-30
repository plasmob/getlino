.. _getlino.install:

==================
Installing getlino
==================

On a production server
======================

To install a production server, you need a Debian machine and a user account
which has permission to run ``sudo``. You must install getlino into the
system-wide Python.

Either the officially stable version::

   $ sudo pip3 install getlino

Or the development version::

   $ sudo pip3 install -e git+https://github.com/lino-framework/getlino.git#egg=getlino


On a development machine
========================

You can  use getlino to simply configure a development environment. In that case
you don't need root privileges.

Make sure your default working environment is activated.

We recommend to  install your own local clone::

   $ cd ~/repositories
   $ git clone git@github.com:lino-framework/getlino.git
   $ pip3 install -e getlino


Or the officially stable version::

   $ pip install getlino

Or a snapshot the development version::

   $ pip install -e git+https://github.com/lino-framework/getlino.git#egg=getlino
