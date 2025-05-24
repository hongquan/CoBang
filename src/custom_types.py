from gi.repository import GObject  # pyright: ignore[reportMissingModuleSource]

from .consts import DeviceSourceType


class WebcamDeviceInfo(GObject.GObject):
    __gtype_name__ = 'WebcamDeviceInfo'
    # pipewiresrc / v4l2src. The type should be DeviceSourceType but PyGobject doesn't support Enum yet.
    source_type = GObject.Property(type=str, default='v4l2src')
    # The device path, e.g. /dev/video0 or /dev/video1
    # or PipeWire serial number.
    path = GObject.Property(type=str)
    name = GObject.Property(type=str)
    # When GStreamer DeviceMonitor reports both V4L2 and PipeWire devices,
    # we will use this field to ignore the PipeWire ones.
    enabled = GObject.Property(type=bool, default=True)

    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_LAST, None, ()),
    }

    def __init__(self, source_type: DeviceSourceType, path: str, name: str, enabled: bool = True):
        super().__init__()
        self.source_type = source_type
        self.path = path
        self.name = name
        self.enabled = enabled
