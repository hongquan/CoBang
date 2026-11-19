==============
CyperusCoi
==============

.. image:: https://madewithlove.now.sh/vn?heart=true&colorA=%23ffcd00&colorB=%23da251d

A native QR Code and barcode scanner application for Linux desktop.

.. image:: https://github.com/hongquan/CoBang/blob/main/data/vn.quokka.CyperusCoi.svg
    :width: 400


CyperusCoi can scan barcode, QR code from webcam or static image, local or remote.

This is a fork of `CoBang`_, ported from GTK 4 + libadwaita to **GTK 3 + libhandy**,
to improve performance and reliability for X11 users, where the GTK 4 GStreamer
video sink integration (`gtk4paintablesink`) suffers from GL context stalls and
high CPU/GPU usage. On X11, CyperusCoi renders the webcam feed with the
battle-tested Cairo-based ``gtksink`` (no GL context involved); on Wayland it
keeps GPU-accelerated rendering through ``gtkglsink``.


Name
++++

It is "`Cỏ cói <co_coi_>`_" (the mat sedge, genus *Cyperus*), in Vietnamese. This
plant is used for weaving chiếu mats, whose grid pattern looks like the modules
of a QR code. The name is a deliberate sibling of upstream CoBang, which is named
after "`Cỏ bàng <co_bang_>`_" (*Lepironia articulata*) — another weaving plant.
Same craft, lighter weave: GTK 3 + libhandy.

Motivation
++++++++++

QR codes are more and more widely used in daily life, even in developing countries like Việt Nam. While there already are lot of QR code scanner apps for mobile phones, very few exist for Linux desktop. All don't satisfy me in some aspects:

- `QtQR`_:

  + Pretty old code.
  + Its integration of other library is not good: cannot embed webcam video into its window.

- `zbarcam`_:

  + Command-line tool, it creates a very basic window with only video display, no control buttons, no result display, no label.
  + Users have to come back to Terminal to see the result, and the result are just raw text, no decoding for structured data like WiFi info, URL etc.

- Some Electron-based programs in GitHub:

  + Using Electron stack, which is unnecessary fat [1]_.
  + The UI doesn't look native.

So I build *CyperusCoi* (originally *CoBang*), a native Linux application for
scanning QR code, and this fork keeps that goal while choosing the GTK 3 stack
for smooth X11 operation.


Screenshots
+++++++++++

.. image:: https://i.imgur.com/a4KoZCg.png
.. image:: https://i.imgur.com/AigLax4.png
.. image:: https://i.imgur.com/Q9xwcep.png
.. image:: https://quan-images.b-cdn.net/app-screenshots/cobang/Generate-from-text-dark.png
.. image:: https://quan-images.b-cdn.net/app-screenshots/cobang/Generate-from-wifi-light.png


Install
+++++++

Due to dependence on GObject, GTK libraries and being a desktop app with extra desktop-integration files (icons, *\*.desktop* etc.),
CyperusCoi cannot be installed from `PyPI`_. You have to install it with OS package manager.

Because this fork is young, it is not yet packaged in the distribution
channels that upstream CoBang uses (PPA, AUR, COPR, FlatHub). For now, build
and install it from source (see `Development`_), with these Debian/Ubuntu
packages: *gir1.2-gtk-3.0*, *gir1.2-handy-1*, *gir1.2-xdpgtk3-1.0*,
*gstreamer1.0-gtk3* plus the rest of *deb-packages.txt*.

It installs under its own name and id (``cyperuscoi``, ``vn.quokka.CyperusCoi``),
so it can coexist with an upstream CoBang installation.

Upstream CoBang remains available for distros from the `PPA`_, `AUR`_, `COPR`_
and `FlatHub`_ channels:

.. code-block:: console

  $ flatpak install flathub vn.hoabinh.quan.CoBang


Compatibility
-------------

This fork is primarily targeted at X11 desktop environments (KDE, Xfce, LxQt,
Cinnamon, ...), where it uses the Cairo-based ``gtksink`` for the webcam view.
On Wayland sessions it uses the GL-accelerated ``gtkglsink`` instead.

Since v1.6, this app has different webcam access methods, depending on whether it runs inside sandbox (Flatpak) or not. Outside sandbox, it tries to access webcam directly as V4L2 device.
Inside sandbox, it accesses indirectly via `xdg-desktop-portal`_, and depending on how much the portal supports, the app may not see your webcam.


Development
+++++++++++

This section is for someone who wants to join development of CyperusCoi.

CyperusCoi is written in Python, using `GTK+ <gtk_>`_ 3 with `libhandy`_ for UI,
`GStreamer`_ for webcam capture and a part of `ZBar`_ for decoding QR code from image.


Install dependencies
--------------------

Though being written in Python, but as a GTK app, most of CyperusCoi's Python dependencies can be only installed from OS package manager.
They are listed in *deb-packages.txt* file, under the name of Debian packages. On Debian, Ubuntu and derivates, you can quickly install them with this command:

.. code-block:: console

  $ xargs -a deb-packages.txt sudo apt install

On other distros (Fedora, ArchLinux etc.), please try to figure out equivalent package names and install with your favorite package manager.

Some Python packages which aid development can be installed with ``pip``, and listed in *requirements-dev.txt*. If you want to install them to a virtual environment, remember to create it with ``--system-site-packages`` flag.


Run from source
---------------

Due to the dependence on system libraries and GTK ecosystem, CyperusCoi requires a build step and cannot be run directly from source.
However, you can still try running it in development by:

.. code-block:: console

  $ meson setup build --prefix ~/.local/
  $ meson compile -C build
  $ meson install -C build
  $ G_MESSAGES_DEBUG=cyperuscoi cyperuscoi

These steps will install CyperusCoi to *~/.local/*. Everytime we modify source code, we only need to run the ``meson install ...`` step again.

To uninstall, do:

.. code-block:: console

  $ ninja -C build uninstall

Non-visual UI tests (useful in headless environments) and resource consistency
checks:

.. code-block:: console

  $ xvfb-run -a python3 dev/ui_smoke.py
  $ python3 dev/check_ui_paths.py


Translation
-----------

Strings are extracted with ``xgettext`` (the ``.ui`` files are extracted as Glade):

.. code-block:: console

  $ ./dev/extract-for-translating.nu
  $ ./dev/update-translated.nu

The gettext domain stays ``cobang``, so existing CoBang translations carry over.


Package for Debian/Ubuntu
-------------------------

Follow the packaging flow of upstream CoBang (see the upstream README), adapting
the package name to *cyperuscoi* and the app id to *vn.quokka.CyperusCoi*.


.. _CoBang: https://github.com/hongquan/CoBang
.. _QtQR: https://launchpad.net/qr-tools
.. _zbarcam: https://github.com/mchehab/zbar
.. _PyPI: https://pypi.org
.. _PPA: https://launchpad.net/~ng-hong-quan/+archive/ubuntu/ppa
.. _AUR: https://aur.archlinux.org/packages/cobang
.. _COPR: https://copr.fedorainfracloud.org/coprs/ng-hong-quan/CoBang/
.. _FlatHub: https://flathub.org/apps/details/vn.hoabinh.quan.CoBang
.. _gtk: https://www.gtk.org/
.. _libhandy: https://gitlab.gnome.org/GNOME/libhandy
.. _GStreamer: https://gstreamer.freedesktop.org/
.. _ZBar: https://zbar.sourceforge.net/
.. _Nu: https://www.nushell.sh
.. _xdg-desktop-portal: https://github.com/flatpak/xdg-desktop-portal
.. _KDE: https://kde.org/
.. _Xfce: https://xfce.org/
.. _LxQt: https://lxqt-project.org/
.. _co_coi: https://en.wikipedia.org/wiki/Cyperus_corymbosus
.. _co_bang: https://en.wikipedia.org/wiki/Lepironia
