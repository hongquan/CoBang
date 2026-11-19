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

from datetime import datetime
from locale import gettext as _
from typing import TYPE_CHECKING

import gi
import qrcode
from logbook import Logger


if TYPE_CHECKING:
    from ..custom_types import WifiNetworkInfo

from ..consts import ErrorCorrectionLevel, WifiAuthMethod
from .generator_form import GeneratorForm
from .generator_qr_preview_pane import GeneratorQRPreviewPane


gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Handy', '1')

from gi.repository import (
    Gdk,
    GdkPixbuf,
    GLib,
    GObject,
    Gtk,
)


log = Logger(__name__)


def wifi_escape(s: str) -> str:
    return s.replace('\\', r'\\').replace(';', r'\;').replace(',', r'\,').replace('"', r'\"')


@Gtk.Template.from_resource('/vn/quokka/CyperusCoi/gtk/generator-page.ui')
class GeneratorPage(Gtk.Bin):
    """The new QR code generator page."""

    __gtype_name__ = 'GeneratorPage'

    in_mobile_screen = GObject.Property(type=bool, default=False, nick='in-mobile-screen')

    generator_page_box: Gtk.Box = Gtk.Template.Child()
    box_preview: Gtk.Box = Gtk.Template.Child()
    page_separator: Gtk.Separator = Gtk.Template.Child()
    qr_preview_widget: GeneratorQRPreviewPane = Gtk.Template.Child()
    form: GeneratorForm = Gtk.Template.Child()

    request_saved_wifi_networks = GObject.Signal(
        'request-saved-wifi-networks',
        flags=GObject.SignalFlags.RUN_FIRST,
    )

    def __init__(self, **kwargs) -> None:
        """Initialize the generator page."""
        super().__init__(**kwargs)
        self.current_pixbuf: GdkPixbuf.Pixbuf | None = None
        self.current_text: str = ''
        # Reference to keep the native save dialog alive while it is open.
        self._save_dialog: Gtk.FileChooserNative | None = None
        # React to form changes by regenerating the QR code.
        self.form.content_changed.connect(self.on_form_content_changed)
        # The form asks the window to fetch saved WiFi networks when the picker is opened.
        self.form.request_saved_wifi_networks.connect(self.on_form_request_saved_wifi_networks)
        # Preview-pane appearance/quality changes also regenerate the QR code.
        self.qr_preview_widget.qr_property_changed.connect(self.on_form_content_changed)
        # Wire pane button signals to handlers.
        self.qr_preview_widget.download_clicked.connect(self.on_btn_download_clicked)
        self.qr_preview_widget.copy_clicked.connect(self.on_btn_copy_clicked)
        self.qr_preview_widget.new_clicked.connect(self.on_btn_new_clicked)
        # The Adw.MultiLayoutView of the Blueprint UI is replaced by a single
        # GtkBox whose orientation and child order are switched on demand.
        self.connect('notify::in-mobile-screen', self.on_in_mobile_screen_changed)

    def on_in_mobile_screen_changed(self, *args):
        """Switch between the desktop (preview | form) and mobile (form / preview) layouts."""
        box = self.generator_page_box
        if self.in_mobile_screen:
            box.set_orientation(Gtk.Orientation.VERTICAL)
            self.page_separator.set_orientation(Gtk.Orientation.HORIZONTAL)
            box.reorder_child(self.form, 0)
            box.reorder_child(self.page_separator, 1)
            box.reorder_child(self.box_preview, 2)
            self.form.set_vexpand(True)
            self.box_preview.set_halign(Gtk.Align.CENTER)
        else:
            box.set_orientation(Gtk.Orientation.HORIZONTAL)
            self.page_separator.set_orientation(Gtk.Orientation.VERTICAL)
            box.reorder_child(self.box_preview, 0)
            box.reorder_child(self.page_separator, 1)
            box.reorder_child(self.form, 2)
            self.form.set_vexpand(False)
            self.box_preview.set_halign(Gtk.Align.START)

    def on_form_content_changed(self, *args):
        """Regenerate QR code when any form field changes."""
        self.regenerate_qr_code()

    def on_form_request_saved_wifi_networks(self, _src: GeneratorForm):
        """Forward the form's request for saved WiFi networks up to the window."""
        self.request_saved_wifi_networks.emit()

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
            if self.form.wifi_hidden:
                parts.append('H:true')
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
                box_size=int(self.qr_preview_widget.qr_pixel_size),
                border=int(self.qr_preview_widget.qr_border_size),
            )
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(
                fill_color=self.rgba_to_hex(self.qr_preview_widget.foreground_color),
                back_color=self.rgba_to_hex(self.qr_preview_widget.background_color),
            )
            pixbuf = self.pixbuf_from_qrcode_image(img)
        except (GLib.Error, ValueError) as e:
            log.error('Failed to generate QR code image: {}', e)
            self.clear_preview()
            return

        self.current_pixbuf = pixbuf
        self.qr_preview_widget.set_pixbuf(pixbuf)

    def pixbuf_from_qrcode_image(self, img) -> GdkPixbuf.Pixbuf:
        """Convert the qrcode PIL image to a GdkPixbuf (without a PNG detour)."""
        pil_img = img.get_image() if hasattr(img, 'get_image') else img
        if pil_img.mode == 'RGBA':
            has_alpha = True
        else:
            pil_img = pil_img.convert('RGB')
            has_alpha = False
        width, height = pil_img.size
        channels = 4 if has_alpha else 3
        return GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(pil_img.tobytes()),
            GdkPixbuf.Colorspace.RGB,
            has_alpha,
            8,
            width,
            height,
            width * channels,
        )

    def clear_preview(self):
        """Clear the preview image and current pixbuf."""
        self.current_pixbuf = None
        self.current_text = ''
        self.qr_preview_widget.set_pixbuf(None)

    def error_correction_for_level(self, level: str) -> int:
        """Map the form error-correction value (L/M/Q/H) to a qrcode error constant."""
        try:
            return {
                ErrorCorrectionLevel.LOWEST: qrcode.constants.ERROR_CORRECT_L,
                ErrorCorrectionLevel.LOW: qrcode.constants.ERROR_CORRECT_M,
                ErrorCorrectionLevel.MEDIUM: qrcode.constants.ERROR_CORRECT_Q,
                ErrorCorrectionLevel.HIGH: qrcode.constants.ERROR_CORRECT_H,
            }[ErrorCorrectionLevel(level)]
        except (ValueError, KeyError):
            log.warning('Unknown error_correction value: {}, falling back to LOW', level)
            return qrcode.constants.ERROR_CORRECT_M

    def rgba_to_hex(self, rgba: Gdk.RGBA) -> str:
        """Convert a Gdk.RGBA to a CSS-style hex string."""
        return f'#{int(rgba.red * 255):02x}{int(rgba.green * 255):02x}{int(rgba.blue * 255):02x}'

    def on_btn_download_clicked(self, _src: GeneratorQRPreviewPane, _btn: Gtk.Button):
        """Save the generated QR code to a PNG file."""
        if not isinstance(self.current_pixbuf, GdkPixbuf.Pixbuf):
            log.warning('No QR code to save')
            return

        if not isinstance(root := self.get_root(), Gtk.Window):
            log.warning('Generator page is not inside a window, cannot show save dialog')
            return
        filter_png = Gtk.FileFilter()
        filter_png.set_name(_('PNG Image'))
        filter_png.add_mime_type('image/png')
        dlg = Gtk.FileChooserNative.new(
            _('Save QR Code'),
            root,
            Gtk.FileChooserAction.SAVE,
            _('_Save'),
            _('_Cancel'),
        )
        dlg.set_filter(filter_png)
        dlg.set_modal(True)
        dlg.set_do_overwrite_confirmation(True)
        now = datetime.now()
        dlg.set_current_name(f'qrcode_{now:%Y%m%d_%H%M%S}.png')
        dlg.connect('response', self.on_save_dialog_response)
        self._save_dialog = dlg
        dlg.show()

    def on_save_dialog_response(self, dialog: Gtk.FileChooserNative, response: int):
        if response != Gtk.ResponseType.ACCEPT:
            self._save_dialog = None
            return
        file = dialog.get_file()
        self._save_dialog = None
        if not file:
            log.info('No file chosen.')
            return
        pixbuf = self.current_pixbuf
        if not isinstance(pixbuf, GdkPixbuf.Pixbuf):
            log.warning('No QR code to save')
            return
        if not (path := file.get_path()):
            log.warning('The chosen location is not a local file')
            return
        try:
            pixbuf.savev(path, 'png', [], [])
        except GLib.Error as e:
            log.error('Failed to save QR code: {}', e)
        except OSError as e:
            log.error('Failed to save QR code due to file system error: {}', e)

    def on_btn_copy_clicked(self, _src: GeneratorQRPreviewPane, button: Gtk.Button):
        """Copy the generated QR code image to the clipboard."""
        if not isinstance(self.current_pixbuf, GdkPixbuf.Pixbuf):
            log.warning('No QR code to copy')
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_image(self.current_pixbuf)
        button.set_tooltip_text(_('Copied!'))
        GLib.timeout_add_seconds(3, lambda: button.set_tooltip_text(None))

    def on_btn_new_clicked(self, _src: GeneratorQRPreviewPane):
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
