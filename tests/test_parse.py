from cobang.messages import mecard_unescape, parse_wifi_message


def test_mecard_unescape():
    data_in = r'\"foo\;bar\\baz\"'
    out = mecard_unescape(data_in)
    assert out == r'"foo;bar\baz"'


def test_wifi_info():
    raw_data = 'WIFI:T:WPA;P:thithammuaxuan;S:Thi Tham Mua Xuan;'
    out = parse_wifi_message(raw_data)
    assert out.ssid == 'Thi Tham Mua Xuan'
    assert out.password == 'thithammuaxuan'
