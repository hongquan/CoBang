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

from ..consts import ContentType
from ..custom_types import GeneratorChoiceItem, WifiNetworkInfo


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator/form.ui')
class GeneratorForm(Adw.PreferencesPage):
    """The form for configuring QR code content."""

    __gtype_name__ = 'GeneratorForm'

    __gsignals__ = {
        'content-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    row_type: Adw.ComboRow = Gtk.Template.Child()
    row_security: Adw.ComboRow = Gtk.Template.Child()
    generator_type_store: Gio.ListStore = Gtk.Template.Child()
    wifi_security_store: Gio.ListStore = Gtk.Template.Child()

    # GObject.Property declared as class attributes to avoid zuban no-redef
    # false positives from decorator-style getter/setter pairs.
    content_type = GObject.Property(type=str, default=ContentType.TEXT.value)
    text_content = GObject.Property(type=str, default='')
    wifi_ssid = GObject.Property(type=str, default='')
    wifi_password = GObject.Property(type=str, default='')
    wifi_security = GObject.Property(type=int, default=2)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for prop in (
            'text-content',
            'wifi-ssid',
            'wifi-password',
            'wifi-security',
        ):
            self.connect(f'notify::{prop}', self._on_content_property_changed)
        self._populate_type_store()
        self._populate_security_store()
        self.row_type.connect('notify::selected', self._on_row_type_selected)

    @Gtk.Template.Callback()
    def is_text_type(self, wd: Self, value: str) -> bool:
        """Whether the text/URL row should be visible for the current type."""
        return value == ContentType.TEXT.value

    @Gtk.Template.Callback()
    def is_wifi_type(self, wd: Self, value: str) -> bool:
        """Whether the WiFi rows should be visible for the current type."""
        return value == ContentType.WIFI.value

    def _on_row_type_selected(self, row_type: Adw.ComboRow, *args):
        """Reflect the ComboRow selection into content_type and emit content-changed."""
        if not isinstance(item := row_type.get_selected_item(), GeneratorChoiceItem):
            return
        self.set_property('content-type', item.value)
        self._on_content_property_changed()

    def _populate_type_store(self):
        """Populate the QR code content type choices."""
        self.generator_type_store.remove_all()
        for content_type in ContentType:
            self.generator_type_store.append(GeneratorChoiceItem(label=content_type.label(), value=content_type.value))

    def _populate_security_store(self):
        """Populate the WiFi security choices."""
        self.wifi_security_store.remove_all()
        for label, value in (
            (_('No Security'), 'nopass'),
            (_('WEP'), 'WEP'),
            (_('WPA2 Personal'), 'WPA'),
            (_('WPA2 Enterprise'), 'WPA2-EAP'),
            (_('WPA3'), 'WPA3'),
        ):
            self.wifi_security_store.append(GeneratorChoiceItem(label=label, value=value))

    def _on_content_property_changed(self, *args):
        """Emit a single signal when any QR-relevant property changes."""
        self.emit('content-changed')

    def get_selected_type_item(self) -> GeneratorChoiceItem | None:
        """Return the selected content type item."""
        if not isinstance(item := self.row_type.get_selected_item(), GeneratorChoiceItem):
            return None
        return item

    def get_selected_security_item(self) -> GeneratorChoiceItem | None:
        """Return the selected WiFi security item."""
        if not isinstance(item := self.row_security.get_selected_item(), GeneratorChoiceItem):
            return None
        return item

    def reset(self):
        """Reset the form to its initial state."""
        self._select_content_type(ContentType.TEXT)
        self.text_content = ''
        self.wifi_ssid = ''
        self.wifi_password = ''
        self.wifi_security = 2

    def _select_content_type(self, content_type: ContentType):
        """Select the ComboRow row matching the given content type."""
        for index, item in enumerate(self.generator_type_store):
            if item.value == content_type.value:
                self.row_type.set_selected(index)
                return
        log.warning('No ComboRow item matches content_type={}', content_type.value)

    def populate_wifi_networks(self, wifi_networks: Iterable[WifiNetworkInfo]):
        """Populate the saved WiFi network list (placeholder for future UI)."""
        log.info('Received {} saved WiFi networks', len(list(wifi_networks)))

    def update_wifi_password(self, uuid: str, password: str):
        """Update the password for a saved WiFi network (placeholder)."""
        log.info('Updated password for WiFi network UUID: {}', uuid)

    def set_wifi_network_error(self, uuid: str):
        """Mark a saved WiFi network as erroneous (placeholder)."""
        log.warning('WiFi network with UUID {} is erroneous', uuid)

    def switch_to_wifi_network(self, wifi_info: WifiNetworkInfo):
        """Configure the form to generate a QR code for a saved WiFi network."""
        self._select_content_type(ContentType.WIFI)
        self.wifi_ssid = wifi_info.ssid
        self.wifi_password = wifi_info.password or ''
        match wifi_info.key_mgmt:
            case 'none':
                self.wifi_security = 0
            case 'wep':
                self.wifi_security = 1
            case 'wpa-psk':
                self.wifi_security = 2
            case 'wpa-eap':
                self.wifi_security = 3
            case 'sae':
                self.wifi_security = 4
            case _:
                self.wifi_security = 2
