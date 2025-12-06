from locale import gettext as _
from typing import cast
from urllib.parse import SplitResult

from gi.repository import Gtk  # pyright: ignore[reportMissingModuleSource]
from logbook import Logger

from .messages import WifiInfoMessage


log = Logger(__name__)


def build_wifi_info_display(wifi: WifiInfoMessage) -> tuple[Gtk.Box, Gtk.Button] | None:
    builder = Gtk.Builder.new_from_resource('/vn/hoabinh/quan/CoBang/gtk/wifi-display.ui')
    box = cast(Gtk.Box | None, builder.get_object('wifi_form'))
    if not box:
        return None
    if label_ssid_value := cast(Gtk.Label | None, builder.get_object('ssid_value')):
        label_ssid_value.set_text(wifi.ssid)
    if label_password_value := cast(Gtk.Label | None, builder.get_object('password_value')):
        label_password_value.set_text(wifi.password or '')
    btn = cast(Gtk.Button | None, builder.get_object('btn_connect'))
    if wifi.connected and btn:
        log.debug('Set sensitive for {}', btn)
        btn.set_sensitive(False)
        btn.set_label(_('Connected'))
    if password_entry := builder.get_object('password_value'):
        password_entry.connect('icon-press', on_secondary_icon_pressed)
    return box, btn


def build_url_display(url: SplitResult) -> Gtk.Box | None:
    builder = Gtk.Builder.new_from_resource('/vn/hoabinh/quan/CoBang/gtk/url-display.ui')
    btn = cast(Gtk.LinkButton | None, builder.get_object('btn_link'))
    box = cast(Gtk.Box | None, builder.get_object('box_url'))
    if btn:
        btn.set_uri(url.geturl())
        btn.set_label(url.netloc)
    return box


def on_secondary_icon_pressed(entry: Gtk.Entry, pos: Gtk.EntryIconPosition):
    visible = entry.get_visibility()
    entry.set_visibility(not visible)


def icon_name_for_wifi_strength(strength: int) -> str:
    """Get the icon name for the given WiFi signal strength (0-100)."""
    if strength >= 75:
        return 'network-wireless-signal-excellent-symbolic'
    elif strength >= 50:
        return 'network-wireless-signal-good-symbolic'
    elif strength >= 25:
        return 'network-wireless-signal-ok-symbolic'
    elif strength > 0:
        return 'network-wireless-signal-weak-symbolic'
    else:
        return 'network-wireless-signal-none-symbolic'
