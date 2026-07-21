# generator_wifi_network_picker.py
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

from collections.abc import Iterable

from gi.repository import (  # pyright: ignore[reportMissingModuleSource]
    Adw,  # pyright: ignore[reportMissingModuleSource]
    Gio,  # pyright: ignore[reportMissingModuleSource]
    GObject,  # pyright: ignore[reportMissingModuleSource]
    Gtk,  # pyright: ignore[reportMissingModuleSource]
)
from logbook import Logger

from ..custom_types import WifiNetworkInfo


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator/wifi-network-picker-dialog.ui')
class GeneratorWifiNetworkPickerDialog(Adw.Dialog):
    """A modal dialog letting the user pick a saved Wi-Fi network."""

    __gtype_name__ = 'GeneratorWifiNetworkPickerDialog'

    wifi_network_picker_list_store: Gio.ListStore = Gtk.Template.Child()
    wifi_network_picker_list_view: Gtk.ListView = Gtk.Template.Child()
    wifi_network_picker_search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    wifi_network_picker_filter: Gtk.StringFilter = Gtk.Template.Child()
    wifi_network_picker_filter_model: Gtk.FilterListModel = Gtk.Template.Child()
    wifi_network_picker_selection: Gtk.SingleSelection = Gtk.Template.Child()
    wifi_network_picker_back_button: Gtk.Button = Gtk.Template.Child()

    __gsignals__ = {
        'wifi-picked': (GObject.SignalFlags.RUN_FIRST, None, (WifiNetworkInfo,)),
    }

    def populate_wifi_networks(self, wifi_networks: Iterable[WifiNetworkInfo]):
        """Populate the picker list store with the given networks."""
        self.wifi_network_picker_list_store.remove_all()
        for wifi_info in wifi_networks:
            self.wifi_network_picker_list_store.append(wifi_info)
        log.info('Populated {} WiFi networks in picker dialog', len(list(wifi_networks)))

    def update_wifi_password(self, uuid: str, password: str):
        """Update the password for a WiFi network identified by UUID."""
        for item in self.wifi_network_picker_list_store:
            if item.uuid == uuid:
                item.password = password
                return
        log.warning('WiFi network with UUID {} not found in picker dialog list store', uuid)

    def set_network_error(self, uuid: str):
        """Set the erroneous field for a WiFi network identified by UUID."""
        for item in self.wifi_network_picker_list_store:
            if item.uuid == uuid:
                item.erroneous = True
                return
        log.warning('WiFi network with UUID {} not found in picker dialog list store', uuid)

    @Gtk.Template.Callback()
    def on_network_activated(self, *args):
        """Handle activation of a list item (Enter / double-click)."""
        if not (item := self.wifi_network_picker_selection.get_selected_item()):
            return
        self.pick_and_close(item)

    @Gtk.Template.Callback()
    def on_back_clicked(self, button: Gtk.Button):
        """Close the dialog without picking a network."""
        self.close()

    @Gtk.Template.Callback()
    def on_search_stopped(self, search_entry: Gtk.SearchEntry):
        """Clear the search field on Escape."""
        search_entry.set_text('')

    def pick_and_close(self, wifi_info: WifiNetworkInfo):
        """Emit the wifi-picked signal and close the dialog."""
        log.info('WiFi network picked from dialog: {}', wifi_info.ssid)
        self.emit('wifi-picked', wifi_info)
        self.close()
