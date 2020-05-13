# Utitlities to work with Wayland.
# At the time of writing, the API for GdkWayland is not exposed to Python, so we have to use ctype
# to access some C API.

# Ref: https://gist.github.com/jonasl/92c1ef32cfd87047e15f5ae24c6b510e


import ctypes
from ctypes.util import find_library

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gdk, Gtk, Gst


libgdk = ctypes.CDLL(find_library('gdk-3'))
libgdk.gdk_wayland_window_get_wl_surface.restype = ctypes.c_void_p
libgdk.gdk_wayland_window_get_wl_surface.argtypes = [ctypes.c_void_p]
libgdk.gdk_wayland_display_get_wl_display.restype = ctypes.c_void_p
libgdk.gdk_wayland_display_get_wl_display.argtypes = [ctypes.c_void_p]

libgst = ctypes.CDLL(find_library('gstreamer-1.0'))
libgst.gst_context_writable_structure.restype = ctypes.c_void_p
libgst.gst_context_writable_structure.argtypes = [ctypes.c_void_p]
libgst.gst_structure_set.restype = ctypes.c_void_p
libgst.gst_structure_set.argtypes = [
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
]


def get_wayland_window_handle(widget: Gtk.Widget):
    return libgdk.gdk_wayland_window_get_wl_surface(hash(widget.get_window()))


def get_default_wayland_display_context():
    wl_display = libgdk.gdk_wayland_display_get_wl_display(
        hash(Gdk.Display.get_default())
    )
    context = Gst.Context.new('GstWaylandDisplayHandleContextType', True)
    structure = libgst.gst_context_writable_structure(hash(context))
    libgst.gst_structure_set(
        structure,
        ctypes.c_char_p('display'.encode()),
        hash(GObject.TYPE_POINTER),
        wl_display,
        0,
    )
    return context


def get_wayland_display_context(widget: Gtk.Widget):
    display: Gdk.Display = widget.get_display()
    display_handle = libgdk.gdk_wayland_display_get_wl_display(hash(display))
    context: Gst.Context = Gst.Context.new('GstWaylandDisplayHandleContextType', True)
    # structure: Gst.Structure = context.writable_structure()
    # structure.set_value('handle', display_handle)
    structure = libgst.gst_context_writable_structure(hash(context))
    libgst.gst_structure_set(
        structure,
        ctypes.c_char_p('handle'.encode()),
        hash(GObject.TYPE_POINTER),
        display_handle,
        0,
    )
    return context
