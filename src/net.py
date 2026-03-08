from collections.abc import Callable
from enum import StrEnum

import gi


gi.require_version('NM', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('Gio', '2.0')
gi.require_version('GObject', '2.0')
from gi.repository import NM, Gio, GLib, GObject  # pyright: ignore[reportMissingModuleSource]
from logbook import Logger

from .consts import BRAND_NAME
from .custom_types import WifiNetworkInfo
from .messages import WifiInfoMessage


log = Logger(__name__)


class NMWifiKeyMn(StrEnum):
    WEP = 'none'
    WPA = 'wpa-psk'
    WPA2 = 'wpa-psk'
    WPA3 = 'sae'
    WPA2_EAP = 'wpa-eap'


class NMWifiSecretsRetriever(GObject.GObject):
    __gtype_name__ = 'NMWifiSecretsRetriever'

    __gsignals__ = {
        # Emits only terminal outcomes:
        # - failed=True when get_secrets_finish() fails.
        # - failed=False with password when a non-empty password string is retrieved.
        'wifi-secrets-retrieved': (GObject.SignalFlags.RUN_LAST, None, (str, bool, str)),
    }

    def request_saved_wifi_secrets(self, nm_client: NM.Client):
        """Request wireless secrets asynchronously for all saved WiFi connections."""
        for conn in nm_client.get_connections():
            if conn.get_setting_wireless():
                conn.get_secrets_async(
                    NM.SETTING_WIRELESS_SECURITY_SETTING_NAME,
                    None,
                    self.on_wifi_secrets_retrieved,
                )

    def on_wifi_secrets_retrieved(self, conn: NM.RemoteConnection, res: Gio.AsyncResult):
        uuid = conn.get_uuid()
        try:
            secrets_variant = conn.get_secrets_finish(res)
        except GLib.Error as e:
            log.warning('get_secrets_async for connection {} threw an error: {}', uuid, e)
            self.emit('wifi-secrets-retrieved', uuid, True, '')
            return

        if not secrets_variant:
            return

        # The variant is a dict with setting names as keys.
        # e.g., {'802-11-wireless-security': {'psk': 'password'}}
        secrets = secrets_variant.unpack()
        wireless_security = secrets.get(NM.SETTING_WIRELESS_SECURITY_SETTING_NAME, {})
        if not wireless_security:
            # Log here to debug later.
            log.debug('No wireless_security found for WiFi connection {}. Secrets: {}', uuid, secrets)
            return

        password = (
            wireless_security.get('psk')
            or wireless_security.get('wep-key0')
            or wireless_security.get('leap-password')
            or ''
        )
        if isinstance(password, str) and password:
            self.emit('wifi-secrets-retrieved', uuid, False, password)
            return
        # Sometimes we failed to get secrets, log here to debug later.
        log.debug('Retrieved secrets for WiFi connection {}: {}', uuid, secrets)


def is_connected_same_wifi(ssid: str, client: NM.Client) -> bool:
    try:
        conn = next(
            c for c in client.get_active_connections() if c.get_connection_type() == NM.SETTING_WIRELESS_SETTING_NAME
        )
    except StopIteration:
        return False
    # We don't need to compare password, because if we are connected to a wifi network
    # of the same SSID, the connected's password is more correct.
    return conn.get_id() == ssid


def add_wifi_connection(info: WifiInfoMessage, callback: Callable, nm_client: NM.Client):
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
        key_mn = None
    if key_mn:
        secure.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, key_mn)
    if info.password:
        if key_mn == NMWifiKeyMn.WPA:
            secure.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, info.password)
        elif key_mn == NMWifiKeyMn.WEP:
            secure.set_property(NM.SETTING_WIRELESS_SECURITY_WEP_KEY0, info.password)
    conn.add_setting(wireless)
    conn.add_setting(secure)
    nm_client.add_connection_async(conn, True, None, callback)


def get_saved_wifi_networks(nm_client: NM.Client) -> list[WifiNetworkInfo]:
    """Return saved WiFi networks with active state and best-known signal strength."""
    wifi_networks: list[WifiNetworkInfo] = []
    connections = nm_client.get_connections()

    # Map SSID -> strongest signal (0-100)
    strengths: dict[str, int] = {}
    for device in nm_client.get_devices():  # type: ignore[attr-defined]
        if device.get_device_type() != NM.DeviceType.WIFI:
            continue
        for ap in device.get_access_points():
            ssid_bytes = ap.get_ssid()
            if not ssid_bytes:
                continue
            ssid = ssid_bytes.get_data().decode('utf-8', errors='ignore')
            strengths[ssid] = max(strengths.get(ssid, 0), ap.get_strength())

    # Currently active WiFi SSIDs
    active_ssids = {
        ac.get_id()
        for ac in nm_client.get_active_connections()
        if ac.get_connection_type() == NM.SETTING_WIRELESS_SETTING_NAME
    }

    for conn in connections:
        wireless_setting = conn.get_setting_wireless()
        if not wireless_setting:
            continue
        ssid_bytes = wireless_setting.get_ssid()
        if not ssid_bytes:
            continue
        ssid = ssid_bytes.get_data().decode('utf-8', errors='ignore')

        # It is not possible to get Wi-Fi password from NM.SettingWirelessSecurity.
        key_mgmt = 'none'
        if wireless_security := conn.get_setting_wireless_security():
            key_mgmt = wireless_security.get_key_mgmt() or 'none'

        wifi_networks.append(
            WifiNetworkInfo(
                uuid=conn.get_uuid(),
                ssid=ssid,
                password='',
                key_mgmt=key_mgmt,
                is_active=ssid in active_ssids,
                signal_strength=strengths.get(ssid, 0),
            )
        )

    # Sort: active first, then by descending signal strength.
    wifi_networks.sort(key=lambda w: (w.is_active, w.signal_strength), reverse=True)
    return wifi_networks
