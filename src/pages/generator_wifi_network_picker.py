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

import gi


gi.require_version('Gtk', '3.0')
gi.require_version('Handy', '1')

from gi.repository import (
    GObject,
    Gtk,
)
from logbook import Logger

from ..custom_types import WifiNetworkInfo


log = Logger(__name__)


# GtkListStore columns
COL_SSID = 0
COL_SIGNAL_ICON = 1
COL_ERRONEOUS = 2
COL_IS_ACTIVE = 3
COL_NETWORK = 4


@Gtk.Template.from_resource('/vn/quokka/CyperusCoi/gtk/generator/wifi-network-picker-dialog.ui')
class GeneratorWifiNetworkPickerDialog(Gtk.Dialog):
    """A modal dialog letting the user pick a saved Wi-Fi network."""

    __gtype_name__ = 'GeneratorWifiNetworkPickerDialog'

    wifi_network_picker_list_store: Gtk.ListStore = Gtk.Template.Child()
    wifi_network_picker_filter_model: Gtk.TreeModelFilter = Gtk.Template.Child()
    wifi_network_picker_list_view: Gtk.TreeView = Gtk.Template.Child()
    wifi_network_picker_search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    wifi_network_picker_back_button: Gtk.Button = Gtk.Template.Child()

    wifi_picked = GObject.Signal(
        'wifi-picked',
        flags=GObject.SignalFlags.RUN_FIRST,
        arg_types=(WifiNetworkInfo,),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # The filter and its visible function cannot be declared in GtkBuilder.
        self.wifi_network_picker_filter_model.set_visible_func(self.network_row_visible)
        self.wifi_network_picker_search_entry.connect('notify::text', self.on_search_entry_text_changed)

    def network_row_visible(self, model: Gtk.TreeModel, itr: Gtk.TreeIter, data=None) -> bool:
        """Keep only non-erroneous networks whose SSID matches the search text."""
        if model.get_value(itr, COL_ERRONEOUS):
            return False
        ssid = model.get_value(itr, COL_SSID) or ''
        text = self.wifi_network_picker_search_entry.get_text().lower()
        return text in ssid.lower()

    def on_search_entry_text_changed(self, entry: Gtk.SearchEntry, *args):
        self.wifi_network_picker_filter_model.refilter()

    def populate_wifi_networks(self, wifi_networks: Iterable[WifiNetworkInfo]):
        """Populate the picker list store with the given networks."""
        self.wifi_network_picker_list_store.clear()
        for wifi_info in wifi_networks:
            self.wifi_network_picker_list_store.append(
                (
                    wifi_info.ssid,
                    wifi_info.signal_strength_icon,
                    wifi_info.erroneous,
                    wifi_info.is_active,
                    wifi_info,
                )
            )
        log.info('Populated {} WiFi networks in picker dialog', len(list(wifi_networks)))

    def update_wifi_password(self, uuid: str, password: str):
        """Update the password for a WiFi network identified by UUID."""
        store = self.wifi_network_picker_list_store
        itr = store.get_iter_first()
        while itr is not None:
            item = store.get_value(itr, COL_NETWORK)
            if isinstance(item, WifiNetworkInfo) and item.uuid == uuid:
                item.password = password
                return
            itr = store.iter_next(itr)
        log.warning('WiFi network with UUID {} not found in picker dialog list store', uuid)

    def set_network_error(self, uuid: str):
        """Set the erroneous field for a WiFi network identified by UUID."""
        store = self.wifi_network_picker_list_store
        itr = store.get_iter_first()
        while itr is not None:
            item = store.get_value(itr, COL_NETWORK)
            if isinstance(item, WifiNetworkInfo) and item.uuid == uuid:
                item.erroneous = True
                store.set_value(itr, COL_ERRONEOUS, True)
                self.wifi_network_picker_filter_model.refilter()
                return
            itr = store.iter_next(itr)
        log.warning('WiFi network with UUID {} not found in picker dialog list store', uuid)

    @Gtk.Template.Callback()
    def on_network_activated(self, treeview: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn):
        """Handle activation of a list row (Enter / double-click)."""
        model = treeview.get_model()
        itr = model.get_iter(path)
        item = model.get_value(itr, COL_NETWORK)
        if isinstance(item, WifiNetworkInfo):  # Just a type guard
            self.pick_and_close(item)

    @Gtk.Template.Callback()
    def on_back_clicked(self, button: Gtk.Button):
        """Close the dialog without picking a network."""
        self.close()

    @Gtk.Template.Callback()
    def on_search_stopped(self, search_entry: Gtk.SearchEntry):
        """Clear the search field on Escape."""
        search_entry.set_text('')

    @Gtk.Template.Callback()
    def on_delete_event(self, window: Gtk.Widget, event) -> bool:
        # Hide instead of destroying, so the dialog can be reused.
        self.hide()
        return True

    def close(self):
        """GTK3 GtkDialog would destroy itself on close; just hide for reuse."""
        self.hide()

    def pick_and_close(self, wifi_info: WifiNetworkInfo):
        """Emit the wifi-picked signal and close the dialog."""
        log.info('WiFi network picked from dialog: {}', wifi_info.ssid)
        self.wifi_picked.emit(wifi_info)
        self.hide()
