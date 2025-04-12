from gi.repository import GObject  # pyright: ignore[reportMissingModuleSource]


class WebcamDeviceInfo(GObject.GObject):
    __gtype_name__ = 'WebcamDeviceInfo'
    path = GObject.Property(type=str)
    name = GObject.Property(type=str)

    def __init__(self, path: str, name: str):
        super().__init__()
        self.path = path
        self.name = name
