from enum import Enum
from typing import Optional, Callable, Any

import gi
gi.require_version('NM', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('Gio', '2.0')
from gi.repository import GLib, NM

from .consts import BRAND_NAME
from .messages import WifiInfoMessage


class NMWifiKeyMn(str, Enum):
    WEP = 'none'
    WPA = 'wpa-psk'
    WPA2 = 'wpa-psk'
    WPA2_EAP = 'wpa-eap'


def is_connected_same_wifi(info: WifiInfoMessage, client: NM.Client) -> bool:
    try:
        conn = next(c for c in client.get_active_connections()
                    if c.get_connection_type() == NM.SETTING_WIRELESS_SETTING_NAME)
    except StopIteration:
        return False
    # We don't need to compare password, because if we are connected to a wifi network
    # of the same SSID, the connected's password is more correct.
    return conn.get_id() == info.ssid


def add_wifi_connection(info: WifiInfoMessage, callback: Optional[Callable], btn: Any, nm_client: Optional[NM.Client]):
    conn = NM.RemoteConnection()
    base = NM.SettingConnection.new()
    connection_name = f'{info.ssid} ({BRAND_NAME})'
    base.set_property(NM.SETTING_CONNECTION_ID, connection_name)
    conn.add_setting(base)
    ssid = GLib.Bytes.new(info.ssid.encode())
    wireless = NM.SettingWireless.new()
    wireless.set_property(NM.SETTING_WIRELESS_SSID, ssid)
    wireless.set_property(NM.SETTING_WIRELESS_HIDDEN, info.hidden)
    secure = NM.SettingWirelessSecurity.new()
    try:
        key_mn = NMWifiKeyMn[info.auth_type.name] if info.auth_type else None
    except KeyError:
        pass
    if key_mn:
        secure.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, key_mn)
    if info.password:
        if key_mn == NMWifiKeyMn.WPA:
            secure.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, info.password)
        elif key_mn == NMWifiKeyMn.WEP:
            secure.set_property(NM.SETTING_WIRELESS_SECURITY_WEP_KEY0, info.password)
    conn.add_setting(wireless)
    conn.add_setting(secure)
    nm_client.add_connection_async(conn, True, None, callback, btn)
