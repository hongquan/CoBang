from gi.repository import Gio, Gst  # pyright: ignore[reportMissingModuleSource]
from logbook import Logger
from PIL import Image, ImageOps

from .consts import DeviceSourceType


log = Logger(__name__)


def guess_mimetype(file: Gio.File) -> str:
    # If file is local, we check magic bytes to determine the content type, otherwise we guess from file extension.
    attr = (
        Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE if file.is_native() else Gio.FILE_ATTRIBUTE_STANDARD_FAST_CONTENT_TYPE
    )
    log.debug('Querying attribute: {}', attr)
    info = file.query_info(attr, Gio.FileQueryInfoFlags.NONE, None)
    return info.get_attribute_string(attr) or 'application/octet-stream'


def get_device_path(device: Gst.Device) -> tuple[str, DeviceSourceType]:
    """
    Retrieve the device path and source type from a Gst.Device object.

    This function determines the device path and its corresponding source type based on the
    specific Gst.Device subclass. For unsupported device types, an empty path is returned,
    but the source type defaults to V4L2.

    :param device: The GStreamer device object to extract information from.
    :type device: Gst.Device

    :returns: A tuple containing the device path as a string and the source type as a DeviceSourceType enum value.
    :rtype: tuple[str, DeviceSourceType]
    """
    type_name = device.__class__.__name__
    # GstPipeWireDevice doesn't have dedicated GIR binding yet,
    # so we have to access its "device.path" in general GStreamer way
    if type_name == 'GstPipeWireDevice':
        properties = device.get_properties()
        log.info('GstPipeWireDevice properties: {}', properties)
        serial = device.get_property('serial')
        log.info('GstPipeWireDevice serial: {}', serial)
        return str(serial), DeviceSourceType.PIPEWIRE

    if type_name == 'GstV4l2Device':
        return device.get_property('device_path'), DeviceSourceType.V4L2

    # GstLibcameraDevice or some other unknown device type
    log.info('Unknown type {}', type_name)
    properties = device.get_properties()
    log.info('Unsupported GstDevice properties: {}', properties)
    return '', DeviceSourceType.V4L2


def make_grayscale(rgba_img: Image.Image, width: int, height: int) -> Image.Image:
    """Convert RGBA image to grayscale image which is ready to pass to ZBar."""
    # ZBar doesn't accept transparency, so we need to convert alpha channel to white.
    grayscale = rgba_img.convert('LA')
    # Create an all-white image as background.
    canvas = Image.new('LA', (width, height), (255, 255))
    canvas.paste(grayscale, mask=grayscale)
    return canvas.convert('L')


def is_image_almost_black_white(rgba_img: Image.Image):
    total_pixel = rgba_img.width * rgba_img.height
    # Get histogram
    htg = rgba_img.histogram()
    # Count pixels at the left most and right most of each RGB channel
    polar_red = sum(htg[:10] + htg[256 - 10 : 256])
    polar_green = sum(htg[256 : 256 + 10] + htg[512 - 10 : 512])
    polar_blue = sum(htg[512 : 512 + 10] + htg[768 - 10 : 768])
    # Image is almost black-white if most of the pixels gather at the two ends of histogram.
    return (polar_red / total_pixel > 0.9) and (polar_green / total_pixel > 0.9) and (polar_blue / total_pixel > 0.9)


def invert_and_make_grayscale(rgba_img: Image.Image, width: int, height: int) -> Image.Image:
    """Invert and convert RGBA image to grayscale image which is ready to pass to ZBar."""
    gray_scale = make_grayscale(rgba_img, width, height)
    # invert() only accepts RGB
    iv_image = ImageOps.invert(gray_scale.convert('RGB'))
    return iv_image.convert('L')
