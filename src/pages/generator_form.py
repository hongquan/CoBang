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
from locale import gettext as _
from typing import Self

from gi.repository import (  # pyright: ignore[reportMissingModuleSource]
    Adw,  # pyright: ignore[reportMissingModuleSource]
    Gio,  # pyright: ignore[reportMissingModuleSource]
    GObject,  # pyright: ignore[reportMissingModuleSource]
    Gtk,  # pyright: ignore[reportMissingModuleSource]
)
from logbook import Logger

from .generator_wifi_network_picker import GeneratorWifiNetworkPickerDialog
from ..consts import ContentType, WifiAuthMethod
from ..custom_types import GeneratorChoiceItem, WifiNetworkInfo


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator/form.ui')
class GeneratorForm(Adw.PreferencesPage):
    """The form for configuring QR code content."""

    __gtype_name__ = 'GeneratorForm'

    __gsignals__ = {
        'content-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'request-saved-wifi-networks': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    content_type_row: Adw.ComboRow = Gtk.Template.Child()
    wifi_auth_method_row: Adw.ComboRow = Gtk.Template.Child()
    generator_type_store: Gio.ListStore = Gtk.Template.Child()
    wifi_auth_method_store: Gio.ListStore = Gtk.Template.Child()
    choose_saved_wifi_network_row: Adw.ButtonRow = Gtk.Template.Child()

    # GObject.Property declared as class attributes to avoid zuban no-redef
    # false positives from decorator-style getter/setter pairs.
    content_type = GObject.Property(type=str, default=ContentType.TEXT.value)
    text_content = GObject.Property(type=str, default='')
    wifi_ssid = GObject.Property(type=str, default='')
    wifi_password = GObject.Property(type=str, default='')
    # NetworkManager key_mgmt string, see WifiAuthMethod.
    wifi_auth_method = GObject.Property(type=str, default=WifiAuthMethod.WPA_PSK.value)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        for prop in (
            'text-content',
            'wifi-ssid',
            'wifi-password',
            'wifi-auth-method',
        ):
            self.connect(f'notify::{prop}', self.on_content_property_changed)
        self.populate_type_store()
        self.populate_security_store()
        self.content_type_row.connect('notify::selected', self.on_content_type_row_selected)
        self.wifi_auth_method_row.connect('notify::selected', self.on_wifi_auth_method_row_selected)
        # Sync the ComboRow to the property's default value.
        self.select_wifi_auth_method(WifiAuthMethod(self.wifi_auth_method))
        # Lazily-created dialog for picking a saved Wi-Fi network.
        self.wifi_network_picker: GeneratorWifiNetworkPickerDialog | None = None

    @Gtk.Template.Callback()
    def is_text_type(self, wd: Self, value: str) -> bool:
        """Whether the text/URL row should be visible for the current type."""
        return value == ContentType.TEXT.value

    @Gtk.Template.Callback()
    def is_wifi_type(self, wd: Self, value: str) -> bool:
        """Whether the WiFi rows should be visible for the current type."""
        return value == ContentType.WIFI.value

    def on_content_type_row_selected(self, content_type_row: Adw.ComboRow, *args):
        """Reflect the ComboRow selection into content_type and emit content-changed."""
        if not isinstance(item := content_type_row.get_selected_item(), GeneratorChoiceItem):
            return
        self.set_property('content-type', item.value)
        self.on_content_property_changed()

    def on_wifi_auth_method_row_selected(self, wifi_auth_method_row: Adw.ComboRow, *args):
        """Reflect the security ComboRow selection into wifi_auth_method and emit content-changed."""
        if not isinstance(item := wifi_auth_method_row.get_selected_item(), GeneratorChoiceItem):
            return
        self.set_property('wifi-auth-method', item.value)
        self.on_content_property_changed()

    @Gtk.Template.Callback()
    def on_choose_saved_wifi_network_clicked(self, *args):
        """Open the WiFi network picker dialog and ask the window for networks."""
        if self.wifi_network_picker is None:
            self.wifi_network_picker = GeneratorWifiNetworkPickerDialog()
            self.wifi_network_picker.connect('wifi-picked', self.on_wifi_network_picked)
        self.emit('request-saved-wifi-networks')
        self.wifi_network_picker.present(self.get_root())

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
        self.emit('content-changed')

    def get_selected_type_item(self) -> GeneratorChoiceItem | None:
        """Return the selected content type item."""
        if not isinstance(item := self.content_type_row.get_selected_item(), GeneratorChoiceItem):
            return None
        return item

    def get_selected_security_item(self) -> GeneratorChoiceItem | None:
        """Return the selected WiFi security item."""
        if not isinstance(item := self.wifi_auth_method_row.get_selected_item(), GeneratorChoiceItem):
            return None
        return item

    def reset(self):
        """Reset the form to its initial state."""
        self.select_content_type(ContentType.TEXT)
        self.text_content = ''
        self.wifi_ssid = ''
        self.wifi_password = ''
        self.select_wifi_auth_method(WifiAuthMethod.WPA_PSK)

    def select_content_type(self, content_type: ContentType):
        """Select the ComboRow row matching the given content type."""
        for index, item in enumerate(self.generator_type_store):
            if item.value == content_type.value:
                self.content_type_row.set_selected(index)
                return
        log.warning('No ComboRow item matches content_type={}', content_type.value)

    def select_wifi_auth_method(self, auth_method: WifiAuthMethod):
        """Select the security ComboRow row matching the given auth method."""
        for index, item in enumerate(self.wifi_auth_method_store):
            if item.value == auth_method.value:
                self.wifi_auth_method_row.set_selected(index)
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
        try:
            auth_method = WifiAuthMethod(wifi_info.key_mgmt)
        except ValueError:
            auth_method = WifiAuthMethod.WPA_PSK
        self.select_wifi_auth_method(auth_method)
