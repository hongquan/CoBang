from enum import StrEnum
from dataclasses import dataclass
from locale import gettext as _


class WifiAuthType(StrEnum):
    WEP = 'WEP'
    WPA = 'WPA'
    WPA2 = 'WPA2'
    WPA2_EAP = 'WPA2-EAP'


@dataclass
class WifiInfoMessage:
    ssid: str = ''
    password: str | None = None
    # Value: WEP, WPA, WPA2-EAP, nopass
    auth_type: WifiAuthType | None = WifiAuthType.WPA
    hidden: bool = False


# Want to define this string in window.blp but Blueprint and xgettext treat the newline differently.
IMAGE_GUIDE = _('Please add an image file by one of these methods:\n\n\
- Drag and drop here.\n\
- Copy from somewhere and paste (Ctrl+V) here.\n\
- Choose with button below (non Flatpak).\n\n\
Remote image (from http://..., sftp://...) is allowed.')


def parse_to_boolean(value: str) -> bool:
    return value.lower() in ('true', 'yes', 't', 'y')


# Ref: https://en.wikipedia.org/wiki/QR_code#Joining_a_Wi%E2%80%91Fi_network
def mecard_unescape(string: str):
    return (string.replace(r'\"', '"').replace(r'\;', ';')
            .replace(r'\,', ',').replace(r'\\', '\\'))


# Ref: https://github.com/zxing/zxing/wiki/Barcode-Contents#wifi-network-config-android
def parse_wifi_message(string: str) -> WifiInfoMessage | None:
    # Example: WIFI:S:Wikipedia;T:WPA;P:Password1!;;
    string = string.strip()
    if not string.startswith('WIFI:'):
        return None
    parts = string[5:].split(';')
    winfo = WifiInfoMessage()
    for p in parts:
        if p.startswith('S:'):
            winfo.ssid = mecard_unescape(p[2:])
        elif p.startswith('P:'):
            winfo.password = mecard_unescape(p[2:])
        elif p.startswith('T:'):
            auth_type = p[2:]
            winfo.auth_type = WifiAuthType(auth_type) if auth_type != 'nopass' else None
        elif p.startswith('H:'):
            winfo.hidden = parse_to_boolean(p[2:])
    if not winfo.auth_type:
        winfo.password = None
    return winfo
