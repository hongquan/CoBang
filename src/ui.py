from gettext import gettext as _
from urllib.parse import SplitResult
from typing import cast

from logbook import Logger
from gi.repository import Gtk, Gio, NM  # pyright: ignore[reportMissingModuleSource]

from .messages import WifiInfoMessage
from .net import is_connected_same_wifi, add_wifi_connection


log = Logger(__name__)


def build_wifi_info_display(wifi: WifiInfoMessage, nm_client: NM.Client | None) -> Gtk.Box | None:
    builder = Gtk.Builder.new_from_resource('/vn/hoabinh/quan/CoBang/gtk/wifi-display.ui')
    box = cast(Gtk.Box | None, builder.get_object('wifi_form'))
    if not box:
        return None
    if label_ssid_value := cast(Gtk.Label | None, builder.get_object('ssid_value')):
        label_ssid_value.set_text(wifi.ssid)
    if label_password_value := cast(Gtk.Label | None, builder.get_object('password_value')):
        label_password_value.set_text(wifi.password or '')
    btn = cast(Gtk.Button | None, builder.get_object('btn_connect'))
    if nm_client and is_connected_same_wifi(wifi, nm_client) and btn:
        log.debug('Set sensitive for {}', btn)
        btn.set_sensitive(False)
        btn.set_label(_('Connected'))
    log.debug('Connect handlers for Wifi UI')
    if password_entry := builder.get_object('password_value'):
        password_entry.connect('icon-press', on_secondary_icon_pressed)
    if nm_client and btn:
        btn.connect_after('clicked', on_btn_connect_clicked, wifi, nm_client)
    return box


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


def on_btn_connect_clicked(btn: Gtk.Button, wifi: WifiInfoMessage, nm_client: NM.Client):
    add_wifi_connection(wifi, wifi_connect_done, btn, nm_client)


def wifi_connect_done(client: NM.Client, res: Gio.AsyncResult, button: Gtk.Button):
    created = client.add_connection_finish(res)
    log.debug('NetworkManager created connection: {}', created)
    if created:
        button.set_label(_('Saved'))
        button.set_sensitive(False)
