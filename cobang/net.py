from enum import Enum

import gi
gi.require_version('NM', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import GLib, NM

from .messages import WifiInfoMessage


class NMWifiKeyMn(str, Enum):
    WEP = 'none'
    WPA = 'wpa-psk'
    WPA2_EAP = 'wpa-eap'


def is_connected_same_wifi(info: WifiInfoMessage) -> bool:
    client = NM.Client.new()
    try:
        conn = next(c for c in client.get_active_connections()
                    if c.get_connection_type() == NM.SETTING_WIRELESS_SETTING_NAME)
    except StopIteration:
        return False
    # We don't need to compare password, because if we are connected to a wifi network
    # of the same SSID, the connected's password is more correct.
    return conn.get_id() == info.ssid


def add_wifi_connection(info: WifiInfoMessage):
    client = NM.Client.new()
    conn = NM.RemoteConnection()
    ssid = GLib.Bytes.new(info.ssid.encode())
    wireless = NM.SettingWireless.new()
    wireless.set_property(NM.SETTING_WIRELESS_SSID, ssid)
    wireless.set_property(NM.SETTING_WIRELESS_HIDDEN, info.hidden)
    secure = NM.SettingWirelessSecurity.new()
    key_mn = NMWifiKeyMn(info.auth_type.name) if info.auth_type else None
    if key_mn:
        secure.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, key_mn)
    if info.password:
        if key_mn == NMWifiKeyMn.WPA:
            secure.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, info.password)
        elif key_mn == NMWifiKeyMn.WEP:
            secure.set_property(NM.SETTING_WIRELESS_SECURITY_WEP_KEY0, info.password)
    conn.add_setting(wireless)
    conn.add_setting(secure)
    client.add_connection_async(conn, True, None, None)
