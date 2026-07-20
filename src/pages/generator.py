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
from datetime import datetime
from locale import gettext as _
from typing import TYPE_CHECKING, Self

import gi
import qrcode
from logbook import Logger


if TYPE_CHECKING:
    from ..custom_types import WifiNetworkInfo

from .generator_form import GeneratorForm
from .generator_qr_preview_pane import GeneratorQRPreviewPane
from ..consts import WifiAuthMethod


gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import (  # pyright: ignore[reportMissingModuleSource]
    Adw,  # pyright: ignore[reportMissingModuleSource]
    Gdk,  # pyright: ignore[reportMissingModuleSource]
    Gio,  # pyright: ignore[reportMissingModuleSource]
    GLib,  # pyright: ignore[reportMissingModuleSource]
    GObject,  # pyright: ignore[reportMissingModuleSource]
    Gtk,  # pyright: ignore[reportMissingModuleSource]
)


log = Logger(__name__)


def wifi_escape(s: str) -> str:
    return s.replace('\\', r'\\').replace(';', r'\;').replace(',', r'\,').replace('"', r'\"')


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator-page.ui')
class GeneratorPage(Adw.Bin):
    """The new QR code generator page."""

    __gtype_name__ = 'GeneratorPage'

    in_mobile_screen = GObject.Property(type=bool, default=False, nick='in-mobile-screen')

    generator_page_multilayout: Adw.MultiLayoutView = Gtk.Template.Child()
    qr_preview_widget: GeneratorQRPreviewPane = Gtk.Template.Child()
    form: GeneratorForm = Gtk.Template.Child()

    __gsignals__ = {
        'request-saved-wifi-networks': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, **kwargs) -> None:
        """Initialize the generator page."""
        super().__init__(**kwargs)
        self.current_paintable: Gdk.Texture | None = None
        self.current_text: str = ''
        # React to form changes by regenerating the QR code.
        self.form.connect('content-changed', self.on_form_content_changed)
        # The form asks the window to fetch saved WiFi networks when the picker is opened.
        self.form.connect('request-saved-wifi-networks', self.on_form_request_saved_wifi_networks)
        # Preview-pane appearance/quality changes also regenerate the QR code.
        self.qr_preview_widget.connect('content-changed', self.on_form_content_changed)
        # Wire pane button signals to handlers.
        self.qr_preview_widget.connect('download-clicked', self.on_btn_download_clicked)
        self.qr_preview_widget.connect('copy-clicked', self.on_btn_copy_clicked)
        self.qr_preview_widget.connect('new-clicked', self.on_btn_new_clicked)

    def on_form_content_changed(self, *args):
        """Regenerate QR code when any form field changes."""
        self.regenerate_qr_code()

    def on_form_request_saved_wifi_networks(self, _src: GeneratorForm):
        """Forward the form's request for saved WiFi networks up to the window."""
        self.emit('request-saved-wifi-networks')

    @Gtk.Template.Callback()
    def generator_page_layout_name(self, wd: Self, is_mobile: bool) -> str:
        return 'mobile' if is_mobile else 'desktop'

    def build_qr_text(self) -> str:
        """Build the raw text that should be encoded into the QR code."""
        content_type_item = self.form.get_selected_type_item()
        if content_type_item is None:
            return ''
        content_type = content_type_item.value
        if content_type == 'text':
            return self.form.text_content
        if content_type == 'wifi':
            security_item = self.form.get_selected_security_item()
            try:
                auth_method = WifiAuthMethod(security_item.value) if security_item else WifiAuthMethod.WPA_PSK
            except ValueError:
                auth_method = WifiAuthMethod.WPA_PSK
            auth = auth_method.qr_auth()
            password = self.form.wifi_password
            ssid = wifi_escape(self.form.wifi_ssid)
            if auth_method == WifiAuthMethod.NONE:
                password = ''
            parts = [f'S:{ssid}', f'T:{auth}']
            if password:
                parts.append(f'P:{wifi_escape(password)}')
            return 'WIFI:' + ';'.join(parts) + ';;'
        return ''

    def regenerate_qr_code(self):
        """Generate a QR code from the current form content and display it."""
        text = self.build_qr_text()
        if not text:
            self.clear_preview()
            return

        self.current_text = text
        error_correction = self.error_correction_for_level(self.qr_preview_widget.error_correction)
        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=error_correction,
                box_size=self.qr_preview_widget.qr_pixel_size,
                border=self.qr_preview_widget.qr_border_size,
            )
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(
                fill_color=self.rgba_to_hex(self.qr_preview_widget.foreground_color),
                back_color=self.rgba_to_hex(self.qr_preview_widget.background_color),
            )
            buf = io.BytesIO()
            img.save(buf)
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf.getvalue()))
        except GLib.Error as e:
            log.error('Failed to generate QR code image: {}', e)
            self.clear_preview()
            return

        self.current_paintable = texture
        self.qr_preview_widget.set_paintable(texture)

    def clear_preview(self):
        """Clear the preview picture and current paintable."""
        self.current_paintable = None
        self.current_text = ''
        self.qr_preview_widget.set_paintable(None)

    def error_correction_for_level(self, level: int) -> int:
        """Map the form error-correction index to qrcode error constants."""
        match level:
            case 0:
                return qrcode.constants.ERROR_CORRECT_L
            case 1:
                return qrcode.constants.ERROR_CORRECT_M
            case 2:
                return qrcode.constants.ERROR_CORRECT_Q
            case 3:
                return qrcode.constants.ERROR_CORRECT_H
            case 4:
                return qrcode.constants.ERROR_CORRECT_H
            case _:
                return qrcode.constants.ERROR_CORRECT_M

    def rgba_to_hex(self, rgba: Gdk.RGBA) -> str:
        """Convert a Gdk.RGBA to a CSS-style hex string."""
        return f'#{int(rgba.red * 255):02x}{int(rgba.green * 255):02x}{int(rgba.blue * 255):02x}'

    def on_btn_download_clicked(self, _src: GeneratorQRPreviewPane, _btn: Gtk.Button):
        """Save the generated QR code to a PNG file."""
        if not isinstance(self.current_paintable, Gdk.Texture):
            log.warning('No QR code to save')
            return

        filter_png = Gtk.FileFilter(mime_types=['image/png'], name=_('PNG Image'))
        file_dialog = Gtk.FileDialog(title=_('Save QR Code'), modal=True, default_filter=filter_png)
        now = datetime.now()
        default_filename = f'qrcode_{now:%Y%m%d_%H%M%S}.png'
        file = Gio.File.new_for_path(default_filename)
        file_dialog.set_initial_file(file)

        if not isinstance(root := self.get_root(), Gtk.Window):
            log.warning('Generator page is not inside a window, cannot show save dialog')
            return
        file_dialog.save(root, None, self.on_save_dialog_response, self.current_paintable)

    def on_save_dialog_response(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, paintable: Gdk.Texture):
        if not (file := dialog.save_finish(result)):
            return
        try:
            bytes_data = paintable.save_to_png_bytes()
            file.replace_contents_bytes_async(
                bytes_data,
                etag=None,
                make_backup=False,
                flags=Gio.FileCreateFlags.NONE,
                cancellable=None,
                callback=self.on_file_write_finished,
            )
        except GLib.Error as e:
            log.error('Failed to save QR code: {}', e)
        except OSError as e:
            log.error('Failed to save QR code due to file system error: {}', e)

    def on_file_write_finished(self, file: Gio.File, result: Gio.AsyncResult):
        try:
            file.replace_contents_finish(result)
        except GLib.Error as e:
            log.error('Failed to write QR code to file: {}', e)

    def on_btn_copy_clicked(self, _src: GeneratorQRPreviewPane, button: Gtk.Button):
        """Copy the generated QR code image to the clipboard."""
        if not isinstance(self.current_paintable, Gdk.Texture):
            log.warning('No QR code to copy')
            return

        content_provider = Gdk.ContentProvider.new_for_bytes('image/png', self.current_paintable.save_to_png_bytes())
        if not isinstance(display := Gdk.Display.get_default(), Gdk.Display):
            log.warning('No default display available')
            return
        clipboard = display.get_clipboard()
        try:
            clipboard.set_content(content_provider)
            button.set_tooltip_text(_('Copied!'))
            GLib.timeout_add_seconds(3, lambda: button.set_tooltip_text(None))
        except GLib.Error as e:
            log.error('Failed to copy QR code to clipboard: {}', e)

    def on_btn_new_clicked(self, _src: GeneratorQRPreviewPane, _btn: Gtk.Button):
        """Reset the form and preview to start a new QR code."""
        self.clear_preview()
        self.form.reset()
        self.qr_preview_widget.reset()

    def populate_wifi_networks(self, wifi_networks: list[WifiNetworkInfo]):
        """Populate saved WiFi networks in the form."""
        self.form.populate_wifi_networks(wifi_networks)

    def update_wifi_password(self, uuid: str, password: str):
        """Update password for a saved WiFi network by UUID."""
        self.form.update_wifi_password(uuid, password)

    def set_wifi_network_error(self, uuid: str):
        """Mark a saved WiFi network as erroneous by UUID."""
        self.form.set_wifi_network_error(uuid)

    def generate_qr_for_wifi_network(self, wifi_info: WifiNetworkInfo):
        """Set the form to generate a QR code for a saved WiFi network."""
        self.form.switch_to_wifi_network(wifi_info)
