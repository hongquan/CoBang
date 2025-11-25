# generator.py
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

import io

import gi


gi.require_version('GLib', '2.0')

import qrcode
from gi.repository import (  # pyright: ignore[reportMissingModuleSource]
    Adw,  # pyright: ignore[reportMissingModuleSource]
    Gdk,  # pyright: ignore[reportMissingModuleSource]
    GLib,  # pyright: ignore[reportMissingModuleSource]
    GObject,  # pyright: ignore[reportMissingModuleSource]
    Gtk,  # pyright: ignore[reportMissingModuleSource]
)
from logbook import Logger

from ..consts import GeneratorSubPage
from ..custom_types import WifiNetworkInfo
from .generator_qr_code import GeneratorQRCodePage
from .generator_starting import GeneratorStartingPage
from .generator_wifi import GeneratorWiFiPage


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator-page.ui')
class GeneratorPage(Adw.Bin):
    """The main generator page."""

    __gtype_name__ = 'GeneratorPage'

    active_sub_page = GObject.Property(type=str, default=GeneratorSubPage.STARTING)
    view_stack: Adw.ViewStack = Gtk.Template.Child()
    starting_page: GeneratorStartingPage = Gtk.Template.Child()
    qr_code_page: GeneratorQRCodePage = Gtk.Template.Child()
    wifi_page: GeneratorWiFiPage = Gtk.Template.Child()

    __gsignals__ = {
        'request-saved-wifi-networks': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, **kwargs):
        """Initialize the page."""
        super().__init__(**kwargs)
        self.starting_page.connect('generate-qr', self.on_qr_code_generation_requested)
        self.starting_page.connect('switch-to-wifi', self.on_switch_to_wifi)
        self.qr_code_page.connect('back-to-start', self.on_back_to_start)
        self.wifi_page.connect('request-saved-wifi-networks', self.on_request_saved_wifi_networks)
        self.wifi_page.connect('generate-qr-for-wifi', self.on_generate_qr_for_wifi_network)
        self.wifi_page.connect('back-to-start', self.on_back_to_start)

    def on_qr_code_generation_requested(self, _src: GeneratorStartingPage, text: str):
        """Handle the QR code generation request."""
        qr = qrcode.QRCode(border=2)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        png_data = buf.getvalue()
        # Use direct GDK Texture rather than PixbufLoader to avoid external loader
        try:
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(png_data))
            self.qr_code_page.set_original_text(text)
            self.qr_code_page.qr_picture.set_paintable(texture)
            self.active_sub_page = GeneratorSubPage.QR_CODE_RESULT
        except GLib.Error as e:
            log.error('Failed to generate QR code image: {}', e)

    def on_back_to_start(self, _src: GeneratorQRCodePage):
        """Handle returning to the starting page."""
        self.starting_page.clear_entry()
        self.qr_code_page.clear_original_text()
        self.active_sub_page = GeneratorSubPage.STARTING

    def on_switch_to_wifi(self, _src: GeneratorStartingPage):
        """Handle switching to the WiFi page."""
        self.active_sub_page = GeneratorSubPage.WIFI

    def on_request_saved_wifi_networks(self, _src: GeneratorWiFiPage):
        """Forward the request to the window."""
        self.emit('request-saved-wifi-networks')

    def populate_wifi_networks(self, wifi_networks: list[WifiNetworkInfo]):
        """Populate WiFi networks in the WiFi page."""
        self.wifi_page.populate_wifi_networks(wifi_networks)

    def on_generate_qr_for_wifi_network(self, _src: GeneratorWiFiPage, wifi_info: WifiNetworkInfo):
        """Generate QR code for a saved WiFi network."""
        ssid = wifi_escape(wifi_info.ssid)
        auth = map_key_mgmt_to_auth(wifi_info.key_mgmt)
        parts = [f'S:{ssid}', f'T:{auth}']
        if auth != 'nopass' and wifi_info.password:
            parts.append(f'P:{wifi_escape(wifi_info.password)}')
        text = 'WIFI:' + ';'.join(parts) + ';'
        self.on_qr_code_generation_requested(self.starting_page, text)

    @Gtk.Template.Callback()
    def on_view_stack_visible_child_name_changed(self, view_stack: Adw.ViewStack, *args):
        """Handle change of visible child name on the generator view stack."""
        name = view_stack.get_visible_child_name()
        log.debug('GeneratorPage visible child changed to: {}', name)
        if name == GeneratorSubPage.WIFI:
            # Ask for a refresh of saved WiFi networks every time user switches here.
            self.emit('request-saved-wifi-networks')

def wifi_escape(s: str) -> str:
    return s.replace('\\', r'\\').replace(';', r'\;').replace(',', r'\,').replace('"', r'\"')

def map_key_mgmt_to_auth(key_mgmt: str) -> str:
    if key_mgmt in ('none', ''):
        return 'nopass'
    if key_mgmt in ('wpa-psk', 'sae'):
        return 'WPA'
    if key_mgmt == 'wpa-eap':
        return 'WPA2-EAP'
    return 'WPA'
