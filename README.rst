======
CoBang
======

.. image:: https://madewithlove.now.sh/vn?heart=true&colorA=%23ffcd00&colorB=%23da251d

A missing native QR Code scanner application for Linux desktop.

.. image:: https://github.com/hongquan/CoBang/blob/main/data/vn.hoabinh.quan.CoBang.svg
    :width: 400


CoBang can scan barcode, QR code from webcam or static image, local or remote.

In the future, it will support generating QR code and running on Linux phones.


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


Screenshots
+++++++++++

.. image:: https://i.imgur.com/K3TU9bm.png
.. image:: https://i.imgur.com/bIV57cV.png
.. image:: https://i.imgur.com/ldynPU6.png
.. image:: https://i.imgur.com/gtmPSpM.png
.. image:: https://i.imgur.com/MyH9CEC.png
.. image:: https://i.imgur.com/065FVXb.png


Install
+++++++

For now, there is no way to install with Python standard tools (``pip``, Poetry) because we cannot tell them to install desktop-integration files (icons, \*.desktop etc.) to correct places for a desktop app. You have to install it with OS package manager.

Ubuntu
------

CoBang is packaged as *\*.deb* file for Ubuntu and derivatives (Linux Mint etc.). You can install it from `PPA`_:

.. code-block:: sh

    sudo add-apt-repository ppa:ng-hong-quan/ppa
    sudo apt update
    sudo apt install cobang


ArchLinux
---------

CoBang is available via AUR_.


Fedora
------

CoBang is available via COPR_.


Other distros
-------------

Users of other distros can install CoBang from `FlatHub`_.

.. code-block:: sh

    flatpak install flathub vn.hoabinh.quan.CoBang

The release on FlatHub is lagging behind traditional distribution channels (PPA, AUR, COPR) because I often having difficulty building CoBang as Flatpak.


Compatibility
-------------

Though being targeted at Wayland, this app can still work in X11 desktop environments, like `KDE`_ (in Kubuntu), `Xfce`_ (in Xubuntu), `LxQt`_ (in Lubuntu). But due to a gap between GTK and Qt, the app gets some minor quirky issue when running in Qt-based DEs like KDE and LxQt. CoBang should not be tried in VirtualBox virtual machine, because of poor graphics stack VirtualBox provides.

There is an known issue with file chooser button when running from Flatpak. Hope that it can be solved in the future.


Development
+++++++++++

This section is for someone who wants to join development of CoBang.

CoBang is written in Python, using `GTK+ <gtk_>`_ for UI, `GStreamer`_ for webcam capture and a part of `ZBar`_ for decoding QR code from image.


Install dependencies
--------------------

1. Create Python virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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


3. Install PyPI-hosted Python packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For other Python dependencies, this project is using `Poetry`_ to manage. Please install it, then, inside the created virtual environment, run:

.. code-block:: sh

    poetry install --no-root

to install those dependencies.


Run from source
---------------

.. code-block:: sh

    python3 -m cobang


Add ``-v`` option to see more detailed log.


Translation
-----------

.. code-block:: sh

  pybabel extract -F babel.cfg -o po/cobang.pot .
  ./devtool.py update-translation
  ./devtool.py compile-translation


Package for Debian/Ubuntu
-------------------------

This repo is organized in two branches:

- ``main``: Main place for development. Latest code is here.
- ``packaging/ubuntu``: This branch is based on ``main``, but added *debian* folder, used for building *\*.deb* file.

Follow this step to package:

- Checkout to ``main`` branch, and export source code:

  .. code-block:: sh

    export VER='0.1.0'  # Change to version you want
    git archive --format=tar --prefix=cobang-$VER/ HEAD | gzip -c > ../cobang_$VER.orig.tar.gz

- Move the *\*.orig.tar.gz* file to somewhere, then extract it, as *cobang-0.1.0* for example.

- Checkout to ``packaging/ubuntu`` branch, copy *debian* folder and *setup.py* file, putting to just-extracted *cobang-0.1.0* folder.

- If you are about to build *deb* file locally, run:

  .. code-block:: sh

    debuild -us -uc

- If you are about to create source package which are suitable to build on Ubuntu's PPA [2]_, run:

  .. code-block:: sh

    debuild -S


Package as Flatpak
------------------

You can package as Flatpak from the source.

.. code-block:: sh

    flatpak-builder _build --force-clean vn.hoabinh.quan.CoBang.yaml
    flatpak-builder --run _build vn.hoabinh.quan.CoBang.yaml cobang


Alternatives
++++++++++++

These applications were born after CoBang, that is why they are not mentioned in "Motivation" section.

- `Decoder`_: Scan and generate QR code. Built with GTK4 and targeting Flatpak environment.
- `Megapixels`_: Camera application for Linux phones. The only one can access PinePhone camera. Can read QR code.


Credit
++++++

- Brought to you by `Nguyễn Hồng Quân <author_>`_.
- Application logo is from `www.flaticon.com`_, made by `Freepik`_.
- One icon is composed from ones made by `Good Ware <good_ware_>`_ (allowed by Flaticon license).
- Some contributors who proposed nicer UI for this app.

.. [1] Every Electron application brings along a pair of NodeJS + Chromium, which make the package size > 50MB, no matter how small the application code is. To make the situation worse, those NodeJS + Chromium set are not shared. It means that if you installed two Electron apps, you end up having two set of NodeJS & Chromium in your system!
.. [2] Ubuntu PPA requires to upload source package, not prebuilt binary. Read more at: https://help.launchpad.net/Packaging/PPA/Uploading


.. _co_bang: https://nhipsongquehuong.com/bien-co-bang-thanh-do-thu-cong-dep-mat
.. _Gtk: https://www.gtk.org/
.. _GStreamer: https://gstreamer.freedesktop.org/
.. _ZBar: https://github.com/mchehab/zbar
.. _QtQR: https://launchpad.net/qr-tools
.. _PyPI: https://pypi.org/
.. _PPA: https://launchpad.net/~ng-hong-quan/+archive/ubuntu/ppa
.. _AUR: https://aur.archlinux.org/packages/cobang/
.. _COPR: https://copr.fedorainfracloud.org/coprs/xoloitzcuintle/CoBang/
.. _KDE: https://kde.org/
.. _Xfce: https://www.xfce.org/
.. _LxQt: https://lxqt.github.io/
.. _virtualenvwrapper: https://pypi.org/project/virtualenvwrapper/
.. _Poetry: https://python-poetry.org/
.. _Pipenv: https://pipenv.pypa.io
.. _Logbook: https://pypi.org/project/Logbook/
.. _FlatHub: https://flathub.org/apps/details/vn.hoabinh.quan.CoBang
.. _Decoder: https://gitlab.gnome.org/World/decoder/
.. _Megapixels: https://git.sr.ht/~martijnbraam/megapixels
.. _author: https://quan.hoabinh.vn
.. _Freepik: https://www.flaticon.com/authors/freepik
.. _www.flaticon.com: https://www.flaticon.com
.. _good_ware: https://www.flaticon.com/authors/good-ware
