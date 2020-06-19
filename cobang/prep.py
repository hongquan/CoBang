import io
from fractions import Fraction
from typing import Sequence, Optional

import gi

gi.require_version('Gio', '2.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Rsvg', '2.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gio, GdkPixbuf, Rsvg, Gst

from .resources import is_local_real_image, maybe_remote_image


def choose_first_image(uris: Sequence[str]) -> Optional[Gio.File]:
    for u in uris:
        gfile: Gio.File = Gio.file_new_for_uri(u)
        # Is local?
        local_path = gfile.get_path()
        if local_path:
            if is_local_real_image(local_path):
                return gfile
        # Is remote
        if maybe_remote_image(u):
            return gfile


def get_device_path(device: Gst.Device):
    type_name = device.__class__.__name__
    # GstPipeWireDevice doesn't have dedicated GIR binding yet,
    # so we have to access its "device.path" in general GStreamer way
    if type_name == 'GstPipeWireDevice':
        properties = device.get_properties()
        return properties['device.path']
    # Assume GstV4l2Device
    return device.get_property('device_path')


def scale_pixbuf(pixbuf: GdkPixbuf.Pixbuf, outer_width: int, outer_height):
    # Get original size
    ow = pixbuf.get_width()
    oh = pixbuf.get_height()
    # Get aspect ration
    ratio = Fraction(ow, oh)
    # Try scaling to outer_height
    scaled_height = outer_height
    scaled_width = int(ratio * outer_height)
    # If it is larger than outer_width, fixed by width
    if scaled_width > outer_width:
        scaled_width = outer_width
        scaled_height = int(scaled_width / ratio)
    # Now scale with calculated size
    return pixbuf.scale_simple(scaled_width, scaled_height, GdkPixbuf.InterpType.BILINEAR)


def export_svg(svg: Rsvg.Handle) -> io.BytesIO:
    stream = io.BytesIO()
    pix: GdkPixbuf.Pixbuf = svg.get_pixbuf()

    def write(buf: bytes, size, user_data=None):
        stream.write(buf)
        return True, None
    pix.save_to_callbackv(write, None, 'bmp', [], [])
    stream.seek(0)
    return stream
