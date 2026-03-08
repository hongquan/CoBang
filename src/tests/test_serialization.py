from ..custom_types import WifiNetworkInfo
from ..messages import WifiInfoMessage, serialize_wifi_message


def test_serialize_wifi():
    expected = 'WIFI:S:😻😻😻😻;T:WPA;P:password;;'
    wifi_info = WifiNetworkInfo(
        ssid='😻😻😻😻',
        password='password',
        key_mgmt='wpa-psk',
        is_active=False,
        uuid='test-uuid-123',
    )
    message = WifiInfoMessage.from_networkmanager_info(wifi_info)
    serialized = serialize_wifi_message(message)
    assert serialized == expected


def test_serialize_wifi_wpa3_from_sae():
    expected = 'WIFI:S:wpa3-network;T:WPA3;P:password123;;'
    wifi_info = WifiNetworkInfo(
        ssid='wpa3-network',
        password='password123',
        key_mgmt='sae',
        is_active=False,
        uuid='test-uuid-wpa3',
    )
    message = WifiInfoMessage.from_networkmanager_info(wifi_info)
    serialized = serialize_wifi_message(message)
    assert serialized == expected
