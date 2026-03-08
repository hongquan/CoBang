from ..messages import mecard_unescape, parse_wifi_message


def test_mecard_unescape():
    data_in = r'\"foo\;bar\\baz\"'
    out = mecard_unescape(data_in)
    assert out == r'"foo;bar\baz"'


def test_wifi_info():
    raw_data = 'WIFI:T:WPA;P:thithammuaxuan;S:Thi Tham Mua Xuan;'
    out = parse_wifi_message(raw_data)
    assert out.ssid == 'Thi Tham Mua Xuan'
    assert out.password == 'thithammuaxuan'


def test_wifi_info2():
    raw_data = 'WIFI:S:my-network;T:WPA2;P:my-password;;'
    out = parse_wifi_message(raw_data)
    assert out.ssid == 'my-network'
    assert out.password == 'my-password'


def test_wifi_info_wpa3():
    raw_data = 'WIFI:S:wpa3-network;T:WPA3;P:super-secret;;'
    out = parse_wifi_message(raw_data)
    assert out.ssid == 'wpa3-network'
    assert out.password == 'super-secret'
    assert out.auth_type.value == 'WPA3'


def test_wifi_info_wpa3_sae_alias():
    raw_data = 'WIFI:S:wpa3-network;T:SAE;P:super-secret;;'
    out = parse_wifi_message(raw_data)
    assert out.ssid == 'wpa3-network'
    assert out.password == 'super-secret'
    assert out.auth_type.value == 'WPA3'
