
from urllib.parse import urlunsplit
from urllib.parse import SplitResult as UrlSplitResult
from typing import Any

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('NM', '1.0')
gi.require_version('Gio', '2.0')

from gi.repository import Gtk, Gdk, NM, Gio

from .common import _
from .resources import get_ui_filepath
from .messages import WifiInfoMessage
from .net import is_connected_same_wifi, add_wifi_connection


def build_wifi_info_display(wifi: WifiInfoMessage) -> Gtk.Box:
    filepath = str(get_ui_filepath('wifi-display.glade'))
    builder = Gtk.Builder.new_from_file(filepath)
    box = builder.get_object('wifi-form')
    builder.get_object('ssid-value').set_text(wifi.ssid)
    if wifi.password:
        builder.get_object('password-value').set_text(wifi.password)
    btn: Gtk.Button = builder.get_object('btn-connect')
    if is_connected_same_wifi(wifi):
        btn.set_sensitive(False)
        btn.set_label(_('Connected'))
    builder.get_object('password-value').connect('icon-press', on_secondary_icon_pressed)
    btn.connect_after('clicked', on_btn_connect_clicked, wifi)
    return box


def on_secondary_icon_pressed(entry: Gtk.Entry, pos: Gtk.EntryIconPosition, event: Gdk.EventButton):
    visible = entry.get_visibility()
    entry.set_visibility(not visible)


def on_btn_connect_clicked(btn: Gtk.Button, wifi: WifiInfoMessage):
    add_wifi_connection(wifi, wifi_connect_done, btn)


def build_url_display(url: UrlSplitResult):
    filepath = str(get_ui_filepath('url-display.glade'))
    builder = Gtk.Builder.new_from_file(filepath)
    box = builder.get_object('box')
    btn: Gtk.LinkButton = builder.get_object('btn-link')
    btn.set_label(url.netloc)
    btn.set_uri(urlunsplit(url))
    return box


def wifi_connect_done(client: NM.Client, res: Gio.AsyncResult, user_data: Any):
    print(res)
    print(client.add_connection_finish(res))
