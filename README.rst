=======================
The ``getlino`` package
=======================

A script for configuring Lino production servers and installing Lino sites.

This package is meant to be installed into the system-wide Python of a Lino
production server::

    $ sudo pip3 install getlino

First you will create a system-wide getlino config file::

    $ sudo getlino.py config


Next step is to install system-wide dependencies according to your getlino
config file::

    $ sudo getlino.py setup

Last step is to create a Lino site.  For example::

    $ getlino.py startsite mysite noi





Testing using Docker file::

    $ docker build -t getlino .

