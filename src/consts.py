from enum import IntEnum, StrEnum
from locale import gettext as _


SHORT_NAME = 'cobang'
BRAND_NAME = 'CoBang'
APP_ID = 'vn.hoabinh.quan.CoBang'

ENV_EMULATE_SANDBOX = 'COBANG_LIKE_IN_SANDBOX'


class JobName(StrEnum):
    SCANNER = 'scanner'
    GENERATOR = 'generator'


class ScanSourceName(StrEnum):
    WEBCAM = 'webcam'
    IMAGE = 'image'


class WebcamPageLayoutName(StrEnum):
    REQUESTING = 'webcam-requesting'
    AVAILABLE = 'webcam-available'
    UNAVAILABLE = 'webcam-unavailable'


class ScannerState(IntEnum):
    IDLE = 0
    SCANNING = 1
    NO_RESULT = 2
    WIFI_FOUND = 3
    URL_FOUND = 4
    TEXT_FOUND = 5


class GeneratorSubPage(StrEnum):
    STARTING = 'starting'
    WIFI = 'wifi'
    QR_CODE_RESULT = 'qr-code-result'


class DeviceSourceType(StrEnum):
    V4L2 = 'v4l2src'
    PIPEWIRE = 'pipewiresrc'


class ContentType(StrEnum):
    TEXT = 'text'
    WIFI = 'wifi'
    VCARD = 'vcard'

    def label(self) -> str:
        if self == self.TEXT:
            return _('Text / URL')
        if self == self.WIFI:
            return _('WiFi')
        return _('vCard')


# Ref: https://lazka.github.io/pgi-docs/#NM-1.0/classes/SettingWirelessSecurity.html#NM.SettingWirelessSecurity.props.key_mgmt
# Possible values: 'none', 'ieee8021x', 'owe', 'wpa-psk', 'sae', 'wpa-eap', 'wpa-eap-suite-b-192'.
class WifiAuthMethod(StrEnum):
    NONE = 'none'
    DYN_WEB = 'ieee8021x'
    OWE = 'owe'
    WPA_PSK = 'wpa-psk'
    SAE = 'sae'
    WPA_EAP = 'wpa-eap'
    WPA_EAP_SUITE_B_192 = 'wpa-eap-suite-b-192'

    def label(self) -> str:
        if self == self.NONE:
            return _('No Security')
        if self == self.DYN_WEB:
            return 'Dynamic WEP'
        if self == self.OWE:
            return 'OWE'
        if self == self.WPA_PSK:
            return _('WPA2 Personal')
        if self == self.SAE:
            return 'WPA3'
        if self == self.WPA_EAP:
            return _('WPA2 Enterprise')
        if self == self.WPA_EAP_SUITE_B_192:
            return _('WPA3 Enterprise')
        return _('Unknown')

    def qr_auth(self) -> str:
        """Map to the auth string used in the generator form's WiFi security store."""
        if self == self.NONE:
            return 'nopass'
        if self in (self.DYN_WEB, self.OWE):
            return 'WEP'
        if self == self.WPA_PSK:
            return 'WPA'
        if self == self.WPA_EAP:
            return 'WPA2-EAP'
        if self in (self.SAE, self.WPA_EAP_SUITE_B_192):
            return 'WPA3'
        return 'WPA'


GST_SOURCE_NAME = 'webcam_source'
GST_FLIP_FILTER_NAME = 'videoflip'
GST_SINK_NAME = 'widget_sink'
GST_APP_SINK_NAME = 'app_sink'
