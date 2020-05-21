======
CoBang
======

.. image:: https://madewithlove.now.sh/vn?heart=true&colorA=%23ffcd00&colorB=%23da251d

A missing native QR Code scanner application for Linux desktop.

.. image:: https://image.flaticon.com/icons/svg/376/376345.svg
    :width: 400


*This work is in progress*.


Name
++++

It is "`Cỏ bàng <co_bang_>`_" (Lepironia articulata), in Vietnamese (I failed to find exact icon for this plant).

Motivation
++++++++++

QR codes are more and more widely used in daily life, even in developing countries like Việt Nam. While there already are lot of QR code scanner apps for mobile phones, very few exist for Linux desktop. All don't satisfy me in some aspects:

- `QtQR`_:

  + Pretty old code.
  + Its integration of other library is not good: cannot embed webcam video into its window.
  + Depend on X Window System.

- Some Electron-based programs in GitHub:

  + Using Electron stack, which is unnecessary fat [1]_.
  + The UI doesn't look native.
  + Depend on X Window System.

X-dependence is a major concern because I want to boost up the migration of Linux desktop from old X Window System to more modern Wayland. Those X-dependent applications drag the transition, not only does it make the OS installation big (have to include an X server next to Wayland compositor), but also waste time fixing bugs of X - Wayland cooperation.

So I decide to build *CoBang*, a new, native Linux application for scanning QR code.


Development
+++++++++++


Install dependencies
--------------------

1. Create Python virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This application is written in Python, using `GTK+ <gtk_>`_ for UI, `GStreamer`_ for webcam capture and a part of `ZBar`_ for decode QR code from image.

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

Note that, please don't install *gstreamer1.0-pipewire*. We are having conflict issue with that software (will be solved later).

3. Install PyPI-hosted Python packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Screenshots
+++++++++++

.. image:: https://i.imgur.com/78OKyyL.png


Credit
++++++

- Brought to you by `Nguyễn Hồng Quân <author_>`_.

- Icons from `www.flaticon.com`_, made by `Freepik`_, `Good Ware <good_ware_>`_.

.. [1] Every Electron application brings along a pair of NodeJS + Chromium, which make the package size > 50MB, no matter how small the application code is. To make the situation worse, those NodeJS + Chromium set are not shared. It means that if you installed two Electron apps, you end up having two set of NodeJS & Chromium in your system!


.. _co_bang: https://nhipsongquehuong.com/bien-co-bang-thanh-do-thu-cong-dep-mat
.. _gtk: https://www.gtk.org/
.. _GStreamer: https://gstreamer.freedesktop.org/
.. _ZBar: https://github.com/ZBar/ZBar
.. _QtQR: https://launchpad.net/qr-tools
.. _PyPI: https://pypi.org/
.. _virtualenvwrapper: https://pypi.org/project/virtualenvwrapper/
.. _poetry: https://python-poetry.org/
.. _pipenv: https://pipenv.pypa.io
.. _logbook: https://pypi.org/project/Logbook/
.. _author: https://quan.hoabinh.vn
.. _freepik: https://www.flaticon.com/authors/freepik
.. _www.flaticon.com: https://www.flaticon.com
.. _good_ware: https://www.flaticon.com/authors/good-ware
