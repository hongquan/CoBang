# generator_qr_preview_pane.py
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

import gi
from logbook import Logger


gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import (
    Gdk,
    GdkPixbuf,
    GObject,
    Gtk,
)

from ..consts import ErrorCorrectionLevel


log = Logger(__name__)


# Maximum dimension of the displayed preview image.
QR_PREVIEW_MAX_SIZE = 192


@Gtk.Template.from_resource('/vn/quokka/CyperusCoi/gtk/generator/qr-preview-pane.ui')
class GeneratorQRPreviewPane(Gtk.Box):
    """A pane displaying the generated QR code preview, action buttons, and
    appearance / quality controls that affect the rendered output."""

    __gtype_name__ = 'GeneratorQRPreviewPane'

    qr_preview: Gtk.Image = Gtk.Template.Child()
    qr_placeholder: Gtk.Box = Gtk.Template.Child()
    qr_pixel_size_row: Gtk.SpinButton = Gtk.Template.Child()
    qr_border_size_row: Gtk.SpinButton = Gtk.Template.Child()
    btn_foreground: Gtk.ColorButton = Gtk.Template.Child()
    btn_background: Gtk.ColorButton = Gtk.Template.Child()
    row_error_correction: Gtk.ComboBoxText = Gtk.Template.Child()

    qr_pixel_size = GObject.Property(type=float, default=8.0)
    qr_border_size = GObject.Property(type=float, default=3.0)
    qr_empty = GObject.Property(type=bool, default=True)
    foreground_color = GObject.Property(
        type=Gdk.RGBA,
        default=Gdk.RGBA(red=0, green=0, blue=0, alpha=1),
    )
    background_color = GObject.Property(
        type=Gdk.RGBA,
        default=Gdk.RGBA(red=1, green=1, blue=1, alpha=1),
    )
    error_correction = GObject.Property(type=str, default=ErrorCorrectionLevel.LOWEST.value)

    download_clicked = GObject.Signal(
        'download-clicked',
        flags=GObject.SignalFlags.RUN_FIRST,
        arg_types=(Gtk.Button,),
    )
    copy_clicked = GObject.Signal(
        'copy-clicked',
        flags=GObject.SignalFlags.RUN_FIRST,
        arg_types=(Gtk.Button,),
    )
    new_clicked = GObject.Signal('new-clicked', flags=GObject.SignalFlags.RUN_FIRST)
    qr_property_changed = GObject.Signal(
        'qr-property-changed',
        flags=GObject.SignalFlags.RUN_FIRST,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        binding_flags = GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE
        # Bindings which were done in the Blueprint UI file.
        self.qr_pixel_size_row.bind_property('value', self, 'qr-pixel-size', binding_flags)
        self.qr_border_size_row.bind_property('value', self, 'qr-border-size', binding_flags)
        self.btn_foreground.bind_property('rgba', self, 'foreground-color', binding_flags)
        self.btn_background.bind_property('rgba', self, 'background-color', binding_flags)
        self.bind_property('qr-empty', self.qr_placeholder, 'visible', GObject.BindingFlags.SYNC_CREATE)

        for prop in (
            'qr-pixel-size',
            'qr-border-size',
            'foreground-color',
            'background-color',
            'error-correction',
        ):
            self.connect(f'notify::{prop}', self.on_qr_property_changed)
        self.populate_error_correction_store()
        self.row_error_correction.connect('changed', self.on_row_error_correction_selected)
        # Sync the ComboBox to the property's default value.
        self.select_error_correction_level(ErrorCorrectionLevel(self.error_correction))

    def populate_error_correction_store(self):
        """Populate the error-correction combobox from ErrorCorrectionLevel."""
        self.row_error_correction.remove_all()
        self.error_correction_levels = list(ErrorCorrectionLevel)
        for level in self.error_correction_levels:
            self.row_error_correction.append_text(level.label())

    def on_row_error_correction_selected(self, row_error_correction: Gtk.ComboBoxText, *args):
        """Reflect the combobox selection into error_correction and emit qr-property-changed."""
        index = row_error_correction.get_active()
        if not 0 <= index < len(self.error_correction_levels):
            return
        self.set_property('error-correction', self.error_correction_levels[index].value)
        self.on_qr_property_changed()

    def select_error_correction_level(self, level: ErrorCorrectionLevel):
        """Select the combobox row matching the given error-correction level."""
        for index, item in enumerate(self.error_correction_levels):
            if item.value == level.value:
                self.row_error_correction.set_active(index)
                return
        log.warning('No ComboBox item matches error_correction={}', level.value)

    def on_qr_property_changed(self, *args):
        self.qr_property_changed.emit()

    def reset(self):
        """Reset appearance and quality controls to their initial state."""
        self.qr_pixel_size = 8.0
        self.qr_border_size = 3.0
        self.foreground_color = Gdk.RGBA(red=0, green=0, blue=0, alpha=1)
        self.background_color = Gdk.RGBA(red=1, green=1, blue=1, alpha=1)
        self.select_error_correction_level(ErrorCorrectionLevel.LOWEST)

    def set_pixbuf(self, pixbuf: GdkPixbuf.Pixbuf | None):
        """Set the pixbuf displayed in the QR code preview.

        GTK3 GtkImage does not scale its pixbuf to the widget allocation like
        GTK4 GtkPicture (with content-fit) does, so we scale it explicitly.
        """
        if pixbuf is None:
            self.qr_preview.clear()
            self.qr_empty = True
            return
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        longest = max(width, height)
        if longest > QR_PREVIEW_MAX_SIZE:
            scale = QR_PREVIEW_MAX_SIZE / longest
            pixbuf = pixbuf.scale_simple(round(width * scale), round(height * scale), GdkPixbuf.InterpType.BILINEAR)
        self.qr_preview.set_from_pixbuf(pixbuf)
        self.qr_empty = False

    @Gtk.Template.Callback()
    def on_btn_download_clicked(self, btn: Gtk.Button):
        """Emit signal when the download button is clicked."""
        self.download_clicked.emit(btn)

    @Gtk.Template.Callback()
    def on_btn_copy_clicked(self, btn: Gtk.Button):
        """Emit signal when the copy button is clicked."""
        self.copy_clicked.emit(btn)

    @Gtk.Template.Callback()
    def on_btn_new_clicked(self, btn: Gtk.Button):
        """Emit signal when the new button is clicked."""
        self.new_clicked.emit()
