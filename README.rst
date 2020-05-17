======
CoBang
======

.. image:: https://madewithlove.now.sh/vn?heart=true&colorA=%23ffcd00&colorB=%23da251d

A missing native QR Code scanner application for Linux desktop.

.. image:: https://image.flaticon.com/icons/svg/376/376345.svg


*This work is in progress*.

Development
+++++++++++


Install dependencies
--------------------

This application is written in Python, using `GTK+ <gtk>`_ for UI and `GStreamer`_ for capturing webcam.

Because Python binding of many GObject-based libraries (like GTK+, GStreamer) are not distributable via `PyPI`_, you have to create a Python virtual environment with ``--system-site-packages`` flag,
so that the project can access those system-installed Python libraries.


The GObject-based dependencies are listed in *deb-packages.txt* file, under the name of Debian packages. On Debian, Ubuntu and derivates, you can quickly install them with this command:

.. code-block:: sh

    xargs -a deb-packages.txt sudo apt install


On other distros (Fedora, ArchLinux etc.), please try to figure out equivalent package names and install with your favorite package manager.

For other Python dependencies, this project is using `Poetry`_ to manage. Please install it, then, inside the created virtual environment, run:

.. code-block:: sh

    poetry install --no-root

to install them.

You can also use `Poetry`_ to create virtual environment.

Package for Debian/Ubuntu
-------------------------

Will try to figure out later. Currently, we have `Logbook`_ as one dependency and it has not gone into in Debian/Ubuntu repo yet. That will block our packaging process, or we have to package Logbook ourselves.


Credit
++++++

- Brought to you by `Nguyễn Hồng Quân <author_>`_.

- Icon from `Freepik`_.


.. _gtk: https://www.gtk.org/
.. _GStreamer: https://gstreamer.freedesktop.org/
.. _PyPI: https://pypi.org/
.. _poetry: https://python-poetry.org/
.. _logbook: https://pypi.org/project/Logbook/
.. _author: https://quan.hoabinh.vn
.. _freepik: https://www.freepik.com/
