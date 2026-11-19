# generator_form.py
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
    Gio,
    GObject,
    Gtk,
    Handy,
)
from logbook import Logger

from ..consts import ContentType, WifiAuthMethod
from ..custom_types import GeneratorChoiceItem, WifiNetworkInfo
from .generator_wifi_network_picker import GeneratorWifiNetworkPickerDialog


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/quokka/CyperusCoi/gtk/generator/form.ui')
class GeneratorForm(Gtk.Bin):
    """The form for configuring QR code content."""

    __gtype_name__ = 'GeneratorForm'

    content_changed = GObject.Signal('content-changed', flags=GObject.SignalFlags.RUN_FIRST)
    request_saved_wifi_networks = GObject.Signal(
        'request-saved-wifi-networks',
        flags=GObject.SignalFlags.RUN_FIRST,
    )

    content_type_row: Handy.ComboRow = Gtk.Template.Child()
    wifi_auth_method_row: Handy.ComboRow = Gtk.Template.Child()
    text_row: Handy.ActionRow = Gtk.Template.Child()
    wifi_ssid_row: Handy.ActionRow = Gtk.Template.Child()
    wifi_password_row: Handy.ActionRow = Gtk.Template.Child()
    wifi_hidden_row: Handy.ActionRow = Gtk.Template.Child()
    choose_saved_wifi_network_row: Handy.ActionRow = Gtk.Template.Child()
    group_text: Handy.PreferencesGroup = Gtk.Template.Child()
    group_wifi: Handy.PreferencesGroup = Gtk.Template.Child()
    group_vcard: Handy.PreferencesGroup = Gtk.Template.Child()

    # GObject.Property declared as class attributes to avoid zuban no-redef
    # false positives from decorator-style getter/setter pairs.
    content_type = GObject.Property(type=str, default=ContentType.TEXT.value)
    text_content = GObject.Property(type=str, default='')
    wifi_ssid = GObject.Property(type=str, default='')
    wifi_password = GObject.Property(type=str, default='')
    # NetworkManager key_mgmt string, see WifiAuthMethod.
    wifi_auth_method = GObject.Property(type=str, default=WifiAuthMethod.WPA_PSK.value)
    wifi_hidden = GObject.Property(type=bool, default=False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # libhandy 1.x HdyComboRow has no "model"/"expression" builder support:
        # keep the Gio.ListStores in Python and bind them with bind_name_model().
        self.generator_type_store = Gio.ListStore.new(GeneratorChoiceItem)
        self.wifi_auth_method_store = Gio.ListStore.new(GeneratorChoiceItem)
        self.populate_type_store()
        self.populate_security_store()
        self.content_type_row.bind_name_model(self.generator_type_store, self.get_item_label)
        self.wifi_auth_method_row.bind_name_model(self.wifi_auth_method_store, self.get_item_label)

        for prop in (
            'text-content',
            'wifi-ssid',
            'wifi-password',
            'wifi-auth-method',
            'wifi-hidden',
        ):
            self.connect(f'notify::{prop}', self.on_content_property_changed)
        self.connect('notify::content-type', lambda *a: self.update_group_visibility())
        self.content_type_row.connect('notify::selected-index', self.on_content_type_row_selected)
        self.wifi_auth_method_row.connect('notify::selected-index', self.on_wifi_auth_method_row_selected)
        # Sync the ComboRow to the property's default value.
        self.select_wifi_auth_method(WifiAuthMethod(self.wifi_auth_method))

        self.build_suffix_widgets()
        self.update_group_visibility()
        # Lazily-created dialog for picking a saved Wi-Fi network.
        self.wifi_network_picker: GeneratorWifiNetworkPickerDialog | None = None

    @staticmethod
    def get_item_label(item: GObject.GObject) -> str:
        """Name function for HdyComboRow.bind_name_model()."""
        return item.label if isinstance(item, GeneratorChoiceItem) else ''

    @staticmethod
    def add_row_suffix(row: Handy.ActionRow, widget: Gtk.Widget):
        """Attach a suffix widget to an HdyActionRow.

        libhandy 1.8 has no HdyActionRow.add_suffix() (that is libadwaita's
        AdwActionRow API), but the row's internal "suffixes" GtkBox can be
        addressed via its GtkBuildable name. Falls back to add_prefix().
        """
        content = row.get_child()
        suffix_box = None
        if isinstance(content, Gtk.Box):
            for child in content.get_children():
                if Gtk.Buildable.get_name(child) == 'suffixes':
                    suffix_box = child
                    break
        if suffix_box is not None:
            suffix_box.add(widget)
        else:
            log.warning('HdyActionRow suffix box not found; falling back to prefix')
            row.add_prefix(widget)

    def build_suffix_widgets(self):
        """Build and attach the row suffix widgets (libhandy 1.x has no EntryRow etc.)."""
        binding_flags = GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE

        self.text_entry = Gtk.Entry()
        self.text_entry.set_hexpand(True)
        self.text_entry.set_width_chars(24)
        self.add_row_suffix(self.text_row, self.text_entry)
        self.text_entry.bind_property('text', self, 'text-content', binding_flags)

        self.wifi_ssid_entry = Gtk.Entry()
        self.wifi_ssid_entry.set_hexpand(True)
        self.wifi_ssid_entry.set_width_chars(24)
        self.add_row_suffix(self.wifi_ssid_row, self.wifi_ssid_entry)
        self.wifi_ssid_entry.bind_property('text', self, 'wifi-ssid', binding_flags)

        self.wifi_password_entry = Gtk.Entry()
        self.wifi_password_entry.set_hexpand(True)
        self.wifi_password_entry.set_width_chars(24)
        self.wifi_password_entry.set_visibility(False)
        self.wifi_password_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.wifi_password_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, 'dialog-password-symbolic')
        self.wifi_password_entry.connect('icon-press', self.on_password_icon_pressed)
        self.add_row_suffix(self.wifi_password_row, self.wifi_password_entry)
        self.wifi_password_entry.bind_property('text', self, 'wifi-password', binding_flags)

        self.wifi_hidden_switch = Gtk.Switch()
        self.add_row_suffix(self.wifi_hidden_row, self.wifi_hidden_switch)
        self.wifi_hidden_row.set_activatable_widget(self.wifi_hidden_switch)
        self.wifi_hidden_switch.bind_property('active', self, 'wifi-hidden', binding_flags)

    @staticmethod
    def on_password_icon_pressed(entry: Gtk.Entry, icon_pos: Gtk.EntryIconPosition, event):
        """Toggle the password visibility on clicking the secondary icon."""
        entry.set_visibility(not entry.get_visibility())

    def update_group_visibility(self):
        """Show only the group matching the current content type.

        Replaces the $is_text_type / $is_wifi_type / $is_vcard_type closures.
        """
        content_type = self.content_type
        self.group_text.set_visible(content_type == ContentType.TEXT.value)
        self.group_wifi.set_visible(content_type == ContentType.WIFI.value)
        self.group_vcard.set_visible(content_type == ContentType.VCARD.value)

    def on_content_type_row_selected(self, content_type_row: Handy.ComboRow, *args):
        """Reflect the ComboRow selection into content_type and emit content-changed."""
        item = self.get_selected_type_item()
        if item is None:
            return
        self.set_property('content-type', item.value)
        self.on_content_property_changed()

    def on_wifi_auth_method_row_selected(self, wifi_auth_method_row: Handy.ComboRow, *args):
        """Reflect the security ComboRow selection into wifi_auth_method and emit content-changed."""
        item = self.get_selected_security_item()
        if item is None:
            return
        self.set_property('wifi-auth-method', item.value)
        self.on_content_property_changed()

    @Gtk.Template.Callback()
    def on_choose_saved_wifi_network_clicked(self, *args):
        """Open the WiFi network picker dialog and ask the window for networks."""
        if self.wifi_network_picker is None:
            self.wifi_network_picker = GeneratorWifiNetworkPickerDialog()
            self.wifi_network_picker.wifi_picked.connect(self.on_wifi_network_picked)
        self.request_saved_wifi_networks.emit()
        if (window := self.get_root()) and isinstance(window, Gtk.Window):
            self.wifi_network_picker.set_transient_for(window)
        self.wifi_network_picker.show()

    def on_wifi_network_picked(
        self,
        _picker: GeneratorWifiNetworkPickerDialog,
        wifi_info: WifiNetworkInfo,
    ):
        """Fill the form with the chosen saved WiFi network."""
        self.switch_to_wifi_network(wifi_info)

    def populate_type_store(self):
        """Populate the QR code content type choices."""
        self.generator_type_store.remove_all()
        for content_type in ContentType:
            self.generator_type_store.append(GeneratorChoiceItem(label=content_type.label(), value=content_type.value))

    def populate_security_store(self):
        """Populate the WiFi security choices from WifiAuthMethod."""
        self.wifi_auth_method_store.remove_all()
        for auth_method in WifiAuthMethod:
            self.wifi_auth_method_store.append(GeneratorChoiceItem(label=auth_method.label(), value=auth_method.value))

    def on_content_property_changed(self, *args):
        """Emit a single signal when any QR-relevant property changes."""
        self.content_changed.emit()

    def get_selected_type_item(self) -> GeneratorChoiceItem | None:
        """Return the selected content type item."""
        index = self.content_type_row.get_selected_index()
        if index < 0:
            return None
        item = self.generator_type_store.get_item(index)
        return item if isinstance(item, GeneratorChoiceItem) else None

    def get_selected_security_item(self) -> GeneratorChoiceItem | None:
        """Return the selected WiFi security item."""
        index = self.wifi_auth_method_row.get_selected_index()
        if index < 0:
            return None
        item = self.wifi_auth_method_store.get_item(index)
        return item if isinstance(item, GeneratorChoiceItem) else None

    def reset(self):
        """Reset the form to its initial state."""
        self.select_content_type(ContentType.TEXT)
        self.text_content = ''
        self.wifi_ssid = ''
        self.wifi_password = ''
        self.wifi_hidden = False
        self.select_wifi_auth_method(WifiAuthMethod.WPA_PSK)

    def select_content_type(self, content_type: ContentType):
        """Select the ComboRow row matching the given content type."""
        for index, item in enumerate(self.generator_type_store):
            if item.value == content_type.value:
                self.content_type_row.set_selected_index(index)
                return
        log.warning('No ComboRow item matches content_type={}', content_type.value)

    def select_wifi_auth_method(self, auth_method: WifiAuthMethod):
        """Select the security ComboRow row matching the given auth method."""
        for index, item in enumerate(self.wifi_auth_method_store):
            if item.value == auth_method.value:
                self.wifi_auth_method_row.set_selected_index(index)
                return
        log.warning('No ComboRow item matches wifi_auth_method={}', auth_method.value)

    def populate_wifi_networks(self, wifi_networks: Iterable[WifiNetworkInfo]):
        """Populate the saved WiFi network list shown in the picker dialog."""
        if self.wifi_network_picker is not None:
            self.wifi_network_picker.populate_wifi_networks(wifi_networks)
        else:
            log.info('Received {} saved WiFi networks (no picker open)', len(list(wifi_networks)))

    def update_wifi_password(self, uuid: str, password: str):
        """Update the password for a saved WiFi network in the picker dialog."""
        if self.wifi_network_picker is not None:
            self.wifi_network_picker.update_wifi_password(uuid, password)
        else:
            log.info('Updated password for WiFi network UUID: {} (no picker open)', uuid)

    def set_wifi_network_error(self, uuid: str):
        """Mark a saved WiFi network as erroneous in the picker dialog."""
        if self.wifi_network_picker is not None:
            self.wifi_network_picker.set_network_error(uuid)
        else:
            log.warning('WiFi network with UUID {} is erroneous (no picker open)', uuid)

    def switch_to_wifi_network(self, wifi_info: WifiNetworkInfo):
        """Configure the form to generate a QR code for a saved WiFi network."""
        self.select_content_type(ContentType.WIFI)
        self.wifi_ssid = wifi_info.ssid
        self.wifi_password = wifi_info.password or ''
        self.wifi_hidden = wifi_info.hidden
        try:
            auth_method = WifiAuthMethod(wifi_info.key_mgmt)
        except ValueError:
            auth_method = WifiAuthMethod.WPA_PSK
        self.select_wifi_auth_method(auth_method)
