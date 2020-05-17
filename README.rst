======
CoBang
======

.. image:: https://madewithlove.now.sh/vn?heart=true&colorA=%23ffcd00&colorB=%23da251d

A missing native QR Code scanner application for Linux desktop.

.. image:: https://image.flaticon.com/icons/svg/376/376345.svg
    :width: 400


*This work is in progress*.

Development
+++++++++++


Install dependencies
--------------------

1. Create Python virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This application is written in Python, using `GTK+ <gtk>`_ for UI and `GStreamer`_ for capturing webcam.

Because Python binding of many GObject-based libraries (like GTK+, GStreamer) are not distributable via `PyPI`_, you have to create a Python virtual environment with ``--system-site-packages`` flag,
so that the project can access those system-installed Python libraries.

My recommended tool is `virtualenvwrapper`_. Because of the requirement of ``--system-site-packages`` flag, you cannot use more modern tool, like `Poetry`_, for this task yet.

Example:

.. code-block:: sh

    $ mkvirtualenv cobang --system-site-packages

    $ workon cobang

2. Install GObject-based Python packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The GObject-based dependencies are listed in *deb-packages.txt* file, under the name of Debian packages. On Debian, Ubuntu and derivates, you can quickly install them with this command:

.. code-block:: sh

    xargs -a deb-packages.txt sudo apt install


On other distros (Fedora, ArchLinux etc.), please try to figure out equivalent package names and install with your favorite package manager.

2. Install PyPI-distributable Python packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For other Python dependencies, this project is using `Poetry`_ to manage. Please install it, then, inside the created virtual environment, run:

.. code-block:: sh

    poetry install --no-root

to install those dependencies.


Package for Debian/Ubuntu
-------------------------

Will try to figure out later. Currently, we have `Logbook`_ as one dependency and it has not gone into in Debian/Ubuntu repo yet. That will block our packaging process, or we have to package Logbook ourselves.


Run
+++

Because the software is not packaged, you have to run it from development source folder:

.. code-block:: sh

    python3 -m cobang


Add ``-v`` option to see more detailed log.


Credit
++++++

- Brought to you by `Nguyễn Hồng Quân <author_>`_.

- Icon from `Freepik`_.


.. _gtk: https://www.gtk.org/
.. _GStreamer: https://gstreamer.freedesktop.org/
.. _PyPI: https://pypi.org/
.. _virtualenvwrapper: https://pypi.org/project/virtualenvwrapper/
.. _poetry: https://python-poetry.org/
.. _pipenv: https://pipenv.pypa.io
.. _logbook: https://pypi.org/project/Logbook/
.. _author: https://quan.hoabinh.vn
.. _freepik: https://www.freepik.com/
