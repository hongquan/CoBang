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


class WifiNetworkInfo(GObject.GObject):
    __gtype_name__ = 'WifiNetworkInfo'
    ssid = GObject.Property(type=str)
    password = GObject.Property(type=str)
    # Ref: https://lazka.github.io/pgi-docs/#NM-1.0/classes/SettingWirelessSecurity.html#NM.SettingWirelessSecurity.props.key_mgmt
    # Possible values: 'none', 'ieee8021x', 'owe', 'wpa-psk', 'sae', 'wpa-eap', 'wpa-eap-suite-b-192'.
    # If seeing unknown value, assume 'wpa-psk'.
    key_mgmt = GObject.Property(type=str, default='none')
    # Whether this network is currently active (connected)
    is_active = GObject.Property(type=bool, default=False)
    # Signal strength 0-100 (best effort; 0 if unknown)
    signal_strength = GObject.Property(type=int, default=0)
    # Icon name representing signal strength (e.g. network-wireless-signal-excellent-symbolic)
    signal_strength_icon = GObject.Property(type=str, default='network-wireless-signal-none-symbolic')

    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_LAST, None, ()),
    }

    def __init__(self, ssid: str, password: str = '', key_mgmt: str = 'none', is_active: bool = False, signal_strength: int = 0):
        super().__init__()
        self.ssid = ssid
        self.password = password
        self.key_mgmt = key_mgmt
        self.is_active = is_active
        self.signal_strength = signal_strength
        # Caller should update signal_strength_icon after setting strength.
