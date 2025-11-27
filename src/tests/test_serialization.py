from ..custom_types import WifiNetworkInfo
from ..messages import serialize_wifi_message, WifiInfoMessage


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
