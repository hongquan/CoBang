======
CoBang
======

.. image:: https://madewithlove.now.sh/vn?heart=true&colorA=%23ffcd00&colorB=%23da251d

A native QR Code and barcode scanner application for Linux desktop.

.. image:: https://github.com/hongquan/CoBang/blob/main/data/vn.hoabinh.quan.CoBang.svg
    :width: 400


CoBang can scan barcode, QR code from webcam or static image, local or remote.


Name
++++

It is "`Cỏ bàng <co_bang_>`_" (Lepironia articulata), in Vietnamese. This plant is used for making handicraft which has pattern like QR code.

Motivation
++++++++++

QR codes are more and more widely used in daily life, even in developing countries like Việt Nam. While there already are lot of QR code scanner apps for mobile phones, very few exist for Linux desktop. All don't satisfy me in some aspects:

- `QtQR`_:

  + Pretty old code.
  + Its integration of other library is not good: cannot embed webcam video into its window.
  + Depend on X Window System.

- `zbarcam`_:

  + Command-line tool, it creates a very basic window with only video display, no control buttons, no result display, no label.
  + Users have to come back to Terminal to see the result, and the result are just raw text, no decoding for structured data like WiFi info, URL etc.
  + Depend on X Window System.

- Some Electron-based programs in GitHub:

  + Using Electron stack, which is unnecessary fat [1]_.
  + The UI doesn't look native.
  + Depend on X Window System.

X-dependence is a major concern because I want to boost up the migration of Linux desktop from old X Window System to more modern Wayland. Those X-dependent applications drag the transition, not only does it make the OS installation big (have to include an X server next to Wayland compositor), but also waste time fixing bugs of X - Wayland cooperation.

So I decide to build *CoBang*, a new, native Linux application for scanning QR code.


Screenshots
+++++++++++

.. image:: https://i.imgur.com/a4KoZCg.png
.. image:: https://i.imgur.com/AigLax4.png
.. image:: https://i.imgur.com/Q9xwcep.png
.. image:: https://cdn.imgchest.com/files/2e65266f6f59.png
.. image:: https://cdn.imgchest.com/files/0edc6ec2c4aa.png


Install
+++++++

Due to dependence on GObject, GTK libraries and being a desktop app with extra desktop-integration files (icons, *\*.desktop* etc.),
CoBang cannot be installed from `PyPI`_. You have to install it with OS package manager.

Ubuntu
------

CoBang is packaged as *\*.deb* file for Ubuntu and derivatives (Linux Mint etc.). You can install it from `PPA`_:

.. code-block:: console

  $ sudo add-apt-repository ppa:ng-hong-quan/ppa
  $ sudo apt update
  $ sudo apt install cobang

Version 1+ is only available on distros which are as new as Ubuntu v24.10.


ArchLinux
---------

CoBang is available via AUR_.


Fedora
------

CoBang is available via COPR_.


Other distros
-------------

Users of other distros can install CoBang from `FlatHub`_.

.. code-block:: console

  $ flatpak install flathub vn.hoabinh.quan.CoBang

The release on FlatHub is lagging behind traditional distribution channels (PPA, AUR, COPR) because I often having difficulty building CoBang as Flatpak.


Compatibility
-------------

Though being targeted at Wayland, this app can still work in X11 desktop environments, like `KDE`_ (in Kubuntu), `Xfce`_ (in Xubuntu), `LxQt`_ (in Lubuntu).
But due to a gap between GTK and Qt, the app gets some minor quirky issue when running in Qt-based DEs like KDE and LxQt.
CoBang should not be tried in VirtualBox virtual machine, because of poor graphics stack VirtualBox provides.

Since v1.6, CoBang has different webcam access methods, depending on whether it runs inside sandbox (Flatpak) or not. Outside sandbox, it tries to access webcam directly as V4L2 device.
Inside sandbox, it accesses indirectly via `xdg-desktop-portal`_, and depending on how much the portal supports, CoBang may not see your webcam.

From v1.0 to v1.5, CoBang only accessed webcam via `xdg-desktop-portal`_.


Development
+++++++++++

This section is for someone who wants to join development of CoBang.

CoBang is written in Python, using `GTK+ <gtk_>`_ for UI, `GStreamer`_ for webcam capture and a part of `ZBar`_ for decoding QR code from image.


Install dependencies
--------------------

Though being written in Python, but as a GTK app, most of CoBang's Python dependencies can be only installed from OS package manager.
They are listed in *deb-packages.txt* file, under the name of Debian packages. On Debian, Ubuntu and derivates, you can quickly install them with this command:

.. code-block:: console

  $ xargs -a deb-packages.txt sudo apt install

.. code-block:: nu

  > open --raw deb-packages.txt | lines | sudo apt install ...$in

On other distros (Fedora, ArchLinux etc.), please try to figure out equivalent package names and install with your favorite package manager.

Some Python packages which aid development can be installed with ``pip``, and listed in *requirements-dev.txt*. If you want to install them to a virtual environment, remember to create it with ``--system-site-packages`` flag.


Run from source
---------------

Due to the dependence on system libraries and GTK ecosystem, CoBang requires a build step and cannot be run directly from source.
However, you can still try running it in development by:

.. code-block:: console

  $ meson setup __build --prefix ~/.local/
  $ ninja -C __build
  $ meson install -C __build
  $ G_MESSAGES_DEBUG=cobang cobang

These steps will install CoBang to *~/.local/*. Everytime we modify source code, we only need to run the ``meson install ...`` step again.

To uninstall, do:

.. code-block:: console

  $ ninja -C __build uninstall


Translation
-----------

Script to extract strings for translation and to update *\*.po* files are written in Nu shell. Please install `Nu`_ before running.

.. code-block:: nu

  > ./dev/extract-for-translating.nu
  > ./dev/update-translated.nu


Package for Debian/Ubuntu
-------------------------

This repo is organized in two branches:

- ``main``: Main place for development. Latest code is here.
- ``packaging/ubuntu``: This branch is based on ``main``, but added *debian* folder, used for building *\*.deb* file.

Follow this step to package:

- Checkout to ``main`` branch, and export source code:

  .. code-block:: console

    $ export VER='0.1.0'  # Change to version you want
    $ git archive --format=tar --prefix=cobang-$VER/ HEAD | gzip -c > ../cobang_$VER.orig.tar.gz

  .. code-block:: nu

    > let VER = '0.1.0'  # Change to version you want
    > git archive --format=tar --prefix=cobang-($VER)/ HEAD | gzip -c o> ../cobang_($VER).orig.tar.gz

- Move the *\*.orig.tar.gz* file to somewhere, then extract it, as *cobang-0.1.0* for example.

- Checkout to ``packaging/ubuntu`` branch, copy *debian* folder and *setup.py* file, putting to just-extracted *cobang-0.1.0* folder.

- If you are about to build *deb* file locally, run:

  .. code-block:: console

    $ debuild -us -uc

- If you are about to create source package which are suitable to build on Ubuntu's PPA [2]_, run:

  .. code-block:: console

    $ debuild -S


Package as Flatpak
------------------

You can package as Flatpak from the source.

.. code-block:: console

  $ flatpak-builder _build --force-clean vn.hoabinh.quan.CoBang.yaml
  $ flatpak-builder --run _build vn.hoabinh.quan.CoBang.yaml cobang


Alternatives
++++++++++++

These applications were born after CoBang, that is why they are not mentioned in "Motivation" section.

- `Decoder`_: Scan and generate QR code. Built with GTK4 and targeting Flatpak environment.
- `Megapixels`_: Camera application for Linux phones. The only one can access PinePhone camera. Can read QR code.


Credit
++++++

- Brought to you by `Nguyễn Hồng Quân <author_>`_.
- Application logo is from Shadd Gallegos.
- Picture icon is modified from `Lucide`_ (available under `ISC license <lucide_license_>`_).
- Some contributors who proposed nicer UI for this app.

.. [1] Every Electron application brings along a pair of NodeJS + Chromium, which make the package size > 50MB, no matter how small the application code is. To make the situation worse, those NodeJS + Chromium set are not shared. It means that if you installed two Electron apps, you end up having two set of NodeJS & Chromium in your system!
.. [2] Ubuntu PPA requires to upload source package, not prebuilt binary. Read more at: https://help.launchpad.net/Packaging/PPA/Uploading


.. _co_bang: https://nhipsongquehuong.com/bien-co-bang-thanh-do-thu-cong-dep-mat
.. _Gtk: https://www.gtk.org/
.. _GStreamer: https://gstreamer.freedesktop.org/
.. _ZBar: https://github.com/mchehab/zbar
.. _zbarcam: https://github.com/mchehab/zbar
.. _QtQR: https://launchpad.net/qr-tools
.. _PyPI: https://pypi.org/
.. _PPA: https://launchpad.net/~ng-hong-quan/+archive/ubuntu/ppa
.. _AUR: https://aur.archlinux.org/packages/cobang/
.. _COPR: https://copr.fedorainfracloud.org/coprs/nunodias/CoBang/
.. _KDE: https://kde.org/
.. _Xfce: https://www.xfce.org/
.. _LxQt: https://lxqt.github.io/
.. _Logbook: https://pypi.org/project/Logbook/
.. _FlatHub: https://flathub.org/apps/details/vn.hoabinh.quan.CoBang
.. _Decoder: https://gitlab.gnome.org/World/decoder/
.. _Megapixels: https://git.sr.ht/~martijnbraam/megapixels
.. _author: https://quan.hoabinh.vn
.. _lucide: https://lucide.dev/icons/image-plus
.. _lucide_license: https://lucide.dev/license
.. _nu: https://www.nushell.sh/
.. _xdg-desktop-portal: https://flatpak.github.io/xdg-desktop-portal/
..
