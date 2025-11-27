#
# Copyright 2025 Nguyễn Hồng Quân
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from gi.repository import Adw, Gio, GObject, Gtk  # pyright: ignore[reportMissingModuleSource]
from logbook import Logger

from ..custom_types import WifiNetworkInfo


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator-wifi-page.ui')
class GeneratorWiFiPage(Adw.Bin):
    """A page for generating WiFi QR codes."""

    __gtype_name__ = 'GeneratorWiFiPage'

    wifi_list_store: Gio.ListStore = Gtk.Template.Child()
    wifi_list_view: Gtk.ListView = Gtk.Template.Child()

    __gsignals__ = {
        'request-saved-wifi-networks': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'generate-qr-for-wifi': (GObject.SignalFlags.RUN_FIRST, None, (WifiNetworkInfo,)),
        'back-to-start': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def populate_wifi_networks(self, wifi_networks: list[WifiNetworkInfo]):
        """Populate the wifi list store with the given networks."""
        self.wifi_list_store.remove_all()
        for wifi_info in wifi_networks:
            self.wifi_list_store.append(wifi_info)
        log.info('Populated {} WiFi networks in list store', len(wifi_networks))

    def update_wifi_password(self, uuid: str, password: str):
        """Update the password for a WiFi network identified by UUID."""
        for item in self.wifi_list_store:
            if item.uuid == uuid:
                item.password = password
                log.debug('Updated password for WiFi network UUID: {}', uuid)
                return
        log.warning('WiFi network with UUID {} not found in list store', uuid)

    @Gtk.Template.Callback()
    def on_wifi_list_view_activated(self, list_view: Gtk.ListView, position: int):
        item = self.wifi_list_store.get_item(position)
        log.info('Generate QR for WiFi (activated): {}', item.ssid)
        self.emit('generate-qr-for-wifi', item)

    @Gtk.Template.Callback()
    def on_btn_back_clicked(self, button: Gtk.Button):
        self.emit('back-to-start')
