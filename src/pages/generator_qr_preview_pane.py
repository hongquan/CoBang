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


gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import (  # pyright: ignore[reportMissingModuleSource]
    Gdk,  # pyright: ignore[reportMissingModuleSource]
    Gio,  # pyright: ignore[reportMissingModuleSource]
    GObject,  # pyright: ignore[reportMissingModuleSource]
    Gtk,  # pyright: ignore[reportMissingModuleSource]
)

from ..consts import ErrorCorrectionLevel
from ..custom_types import GeneratorChoiceItem


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator/qr-preview-pane.ui')
class GeneratorQRPreviewPane(Gtk.Box):
    """A pane displaying the generated QR code preview, action buttons, and
    appearance / quality controls that affect the rendered output."""

    __gtype_name__ = 'GeneratorQRPreviewPane'

    qr_preview: Gtk.Picture = Gtk.Template.Child()
    error_correction_store: Gio.ListStore = Gtk.Template.Child()
    row_error_correction: Gtk.DropDown = Gtk.Template.Child()

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

    __gsignals__ = {
        'download-clicked': (GObject.SignalFlags.RUN_FIRST, None, (Gtk.Button,)),
        'copy-clicked': (GObject.SignalFlags.RUN_FIRST, None, (Gtk.Button,)),
        'new-clicked': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'qr-property-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for prop in (
            'qr-pixel-size',
            'qr-border-size',
            'foreground-color',
            'background-color',
            'error-correction',
        ):
            self.connect(f'notify::{prop}', self.on_qr_property_changed)
        self.populate_error_correction_store()
        self.row_error_correction.connect('notify::selected', self.on_row_error_correction_selected)
        # Sync the DropDown to the property's default value.
        self.select_error_correction_level(ErrorCorrectionLevel(self.error_correction))

    def populate_error_correction_store(self):
        """Populate the error-correction dropdown from ErrorCorrectionLevel."""
        self.error_correction_store.remove_all()
        for level in ErrorCorrectionLevel:
            self.error_correction_store.append(GeneratorChoiceItem(label=level.label(), value=level.value))

    def on_row_error_correction_selected(self, row_error_correction: Gtk.DropDown, *args):
        """Reflect the DropDown selection into error_correction and emit qr-property-changed."""
        item = row_error_correction.get_selected_item()
        if not isinstance(item, GeneratorChoiceItem):
            return
        self.set_property('error-correction', item.value)
        self.on_qr_property_changed()

    def select_error_correction_level(self, level: ErrorCorrectionLevel):
        """Select the DropDown row matching the given error-correction level."""
        for index, item in enumerate(self.error_correction_store):
            if item.value == level.value:
                self.row_error_correction.set_selected(index)
                return
        log.warning('No DropDown item matches error_correction={}', level.value)

    def on_qr_property_changed(self, *args):
        self.emit('qr-property-changed')

    def reset(self):
        """Reset appearance and quality controls to their initial state."""
        self.qr_pixel_size = 8.0
        self.qr_border_size = 3.0
        self.foreground_color = Gdk.RGBA(red=0, green=0, blue=0, alpha=1)
        self.background_color = Gdk.RGBA(red=1, green=1, blue=1, alpha=1)
        self.select_error_correction_level(ErrorCorrectionLevel.LOWEST)

    def set_paintable(self, paintable: Gdk.Paintable | None):
        """Set the paintable displayed in the QR code preview."""
        self.qr_preview.set_paintable(paintable)
        self.qr_empty = paintable is None

    @Gtk.Template.Callback()
    def on_btn_download_clicked(self, btn: Gtk.Button):
        """Emit signal when the download button is clicked."""
        self.emit('download-clicked', btn)

    @Gtk.Template.Callback()
    def on_btn_copy_clicked(self, btn: Gtk.Button):
        """Emit signal when the copy button is clicked."""
        self.emit('copy-clicked', btn)

    @Gtk.Template.Callback()
    def on_btn_new_clicked(self, btn: Gtk.Button):
        """Emit signal when the new button is clicked."""
        self.emit('new-clicked')
