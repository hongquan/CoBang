# generator_qr_code.py
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

from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # pyright: ignore[reportMissingModuleSource]
from logbook import Logger


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator-qr-code-page.ui')
class GeneratorQRCodePage(Gtk.Box):
    """A page for displaying generated QR code."""

    __gtype_name__ = 'GeneratorQRCodePage'

    qr_picture: Gtk.Picture = Gtk.Template.Child()
    btn_download: Gtk.Button = Gtk.Template.Child()
    btn_copy: Gtk.Button = Gtk.Template.Child()
    btn_new: Gtk.Button = Gtk.Template.Child()
    original_text_view: Gtk.TextView = Gtk.Template.Child()

    @GObject.Signal('back-to-start', flags=GObject.SignalFlags.RUN_LAST)
    def signal_back_to_start(self):  # Emitted when user clicks New
        pass

    def set_original_text(self, text: str):
        """Display the text used to generate the QR code."""
        buffer = self.original_text_view.get_buffer()
        buffer.set_text(text)

    def clear_original_text(self):
        """Clear the displayed original text."""
        self.set_original_text('')

    @Gtk.Template.Callback()
    def on_btn_new_clicked(self, _btn: Gtk.Button):
        self.emit('back-to-start')

    @Gtk.Template.Callback()
    def on_btn_download_clicked(self, _btn: Gtk.Button):
        paintable = self.qr_picture.get_paintable()
        if not isinstance(paintable, Gdk.Texture):
            log.warning('QR code picture is not a texture')
            return

        # Prepare dialog for saving file
        filter_png = Gtk.FileFilter(mime_types=['image/png'], name=_('PNG Image'))

        # Create a file dialog to save the image
        file_dialog = Gtk.FileDialog(title=_('Save QR Code'), modal=True, default_filter=filter_png)

        # Set default filename
        now = datetime.now()
        default_filename = f'qrcode_{now:%Y%m%d_%H%M%S}.png'
        file = Gio.File.new_for_path(default_filename)
        file_dialog.set_initial_file(file)

        # Show the dialog
        file_dialog.save(self.get_root(), None, self.on_save_dialog_response, paintable)

    def on_save_dialog_response(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, paintable: Gdk.Texture):
        file = dialog.save_finish(result)
        if not file:
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

    @Gtk.Template.Callback()
    def on_btn_copy_clicked(self, button: Gtk.Button):
        paintable = self.qr_picture.get_paintable()
        if not isinstance(paintable, Gdk.Texture):
            log.warning('QR code picture is not a texture')
            return

        content_provider = Gdk.ContentProvider.new_for_bytes('image/png', paintable.save_to_png_bytes())
        clipboard = Gdk.Display.get_default().get_clipboard()
        try:
            clipboard.set_content(content_provider)
            button.set_tooltip_text(_('Copied!'))
            GLib.timeout_add_seconds(3, lambda: button.set_tooltip_text(None))
        except GLib.Error as e:
            log.error('Failed to copy QR code to clipboard: {}', e)
