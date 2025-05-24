
from logbook import Logger
from gi.repository import Gio, Gst  # pyright: ignore[reportMissingModuleSource]


log = Logger(__name__)


def guess_mimetype(file: Gio.File) -> str:
    # If file is local, we check magic bytes to determine the content type, otherwise we guess from file extension.
    attr = Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE if file.is_native() else Gio.FILE_ATTRIBUTE_STANDARD_FAST_CONTENT_TYPE
    log.debug('Querying attribute: {}', attr)
    info = file.query_info(attr, Gio.FileQueryInfoFlags.NONE, None)
    return info.get_attribute_string(attr)


def get_device_path(device: Gst.Device) -> tuple[str, str]:
    """Get the device path and type name from a Gst.Device object."""
    type_name = device.__class__.__name__
    # GstPipeWireDevice doesn't have dedicated GIR binding yet,
    # so we have to access its "device.path" in general GStreamer way
    if type_name == 'GstPipeWireDevice':
        properties = device.get_properties()
        log.info('GstPipeWireDevice properties: {}', properties)
        serial = device.get_property('serial')
        log.info('GstPipeWireDevice serial: {}', serial)
        return str(serial), 'pipewiresrc'

    if type_name == 'GstV4l2Device':
        return device.get_property('device_path'), 'v4l2src'

    # GstLibcameraDevice or some other unknown device type
    return '', type_name
