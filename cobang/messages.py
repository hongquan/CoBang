from enum import Enum
from dataclasses import dataclass
from typing import Optional


class WifiAuthType(str, Enum):
    WEP = 'WEP'
    WPA = 'WPA'
    WPA2 = 'WPA2'
    WPA2_EAP = 'WPA2-EAP'


@dataclass
class WifiInfoMessage:
    ssid: str = ''
    password: Optional[str] = None
    # Value: WEP, WPA, WPA2-EAP, nopass
    auth_type: Optional[WifiAuthType] = WifiAuthType.WPA
    hidden: bool = False


def parse_true(value: str):
    if value.lower() in ('true', 'yes', 't', 'y'):
        return True
    return False


# Ref: https://en.wikipedia.org/wiki/QR_code#Joining_a_Wi%E2%80%91Fi_network
def mecard_unescape(string: str):
    return (string.replace(r'\"', '"').replace(r'\;', ';')
            .replace(r'\,', ',').replace(r'\\', '\\'))


# Ref: https://github.com/zxing/zxing/wiki/Barcode-Contents#wifi-network-config-android
def parse_wifi_message(string: str) -> WifiInfoMessage:
    # Example: WIFI:S:Wikipedia;T:WPA;P:Password1!;;
    string = string.strip()
    if not string.startswith('WIFI:'):
        raise ValueError('Not starts with WIFI:')
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
            winfo.hidden = parse_true(p[2:])
    if not winfo.auth_type:
        winfo.password = None
    return winfo
