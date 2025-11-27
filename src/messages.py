from typing import Self

from dataclasses import dataclass
from enum import StrEnum
from locale import gettext as _

from .custom_types import WifiNetworkInfo


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
    # Extra field (not in QR code)
    connected: bool = False

    @classmethod
    def from_networkmanager_info(cls, wifi_info: WifiNetworkInfo) -> Self:
        match wifi_info.key_mgmt:
            case 'none':
                auth_type = None
            case 'wpa-psk' | 'sae':
                auth_type = WifiAuthType.WPA
            case 'wpa-eap':
                auth_type = WifiAuthType.WPA2_EAP
            case _:
                auth_type = WifiAuthType.WPA2
        password = None if wifi_info.key_mgmt == 'none' else wifi_info.password
        return cls(
            ssid=wifi_info.ssid,
            password=password,
            auth_type=auth_type,
            connected=wifi_info.is_active,
        )


IMAGE_GUIDE = _(
    'Add an image by:\n\n\
- Dragging and dropping it here.\n\
- Copying and pasting (Ctrl+V).\n\
- Clicking the button below (non-Flatpak).\n\n\
Remote images (http://..., sftp://...) work too!'
)


def parse_to_boolean(value: str) -> bool:
    return value.lower() in ('true', 'yes', 't', 'y')


# Ref: https://en.wikipedia.org/wiki/QR_code#Joining_a_Wi%E2%80%91Fi_network
def mecard_unescape(string: str):
    return string.replace(r'\"', '"').replace(r'\;', ';').replace(r'\,', ',').replace(r'\\', '\\')


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


def serialize_wifi_message(wifi_info: WifiInfoMessage) -> str:
    parts = [f'S:{wifi_info.ssid}']
    auth_type = wifi_info.auth_type.value if wifi_info.auth_type else 'nopass'
    parts.append(f'T:{auth_type}')
    if auth_type != 'nopass' and wifi_info.password:
        parts.append(f'P:{wifi_info.password}')
    if wifi_info.hidden:
        parts.append('H:true')
    text = 'WIFI:' + ';'.join(parts) + ';;'
    return text
