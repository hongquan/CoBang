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

from locale import gettext as _

import gi


gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import (  # pyright: ignore[reportMissingModuleSource]
    Gdk,  # pyright: ignore[reportMissingModuleSource]
    Gio,  # pyright: ignore[reportMissingModuleSource]
    GObject,  # pyright: ignore[reportMissingModuleSource]
    Gtk,  # pyright: ignore[reportMissingModuleSource]
)

from ..custom_types import GeneratorChoiceItem


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator/qr-preview-pane.ui')
class GeneratorQRPreviewPane(Gtk.Box):
    """A pane displaying the generated QR code preview, action buttons, and
    appearance / quality controls that affect the rendered output."""

    __gtype_name__ = 'GeneratorQRPreviewPane'

    qr_preview: Gtk.Picture = Gtk.Template.Child()
    error_correction_store: Gio.ListStore = Gtk.Template.Child()
    row_error_correction: Gtk.DropDown = Gtk.Template.Child()
    btn_foreground: Gtk.ColorDialogButton = Gtk.Template.Child()
    btn_background: Gtk.ColorDialogButton = Gtk.Template.Child()

    qr_pixel_size = GObject.Property(type=int, default=8)
    qr_border_size = GObject.Property(type=int, default=3)
    foreground_color = GObject.Property(
        type=Gdk.RGBA,
        default=Gdk.RGBA(red=0, green=0, blue=0, alpha=1),
    )
    background_color = GObject.Property(
        type=Gdk.RGBA,
        default=Gdk.RGBA(red=1, green=1, blue=1, alpha=1),
    )
    error_correction = GObject.Property(type=int, default=0)

    __gsignals__ = {
        'download-clicked': (GObject.SignalFlags.RUN_FIRST, None, (Gtk.Button,)),
        'copy-clicked': (GObject.SignalFlags.RUN_FIRST, None, (Gtk.Button,)),
        'new-clicked': (GObject.SignalFlags.RUN_FIRST, None, (Gtk.Button,)),
        'content-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
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
            self.connect(f'notify::{prop}', self.on_content_property_changed)
        self.populate_error_correction_store()

    def populate_error_correction_store(self):
        self.error_correction_store.remove_all()
        for label, value in (
            (_('Lowest'), 'L'),
            (_('Low'), 'M'),
            (_('Medium'), 'Q'),
            (_('High'), 'H'),
            (_('Highest'), 'H'),
        ):
            self.error_correction_store.append(GeneratorChoiceItem(label=label, value=value))

    def on_content_property_changed(self, *args):
        self.emit('content-changed')

    def reset(self):
        """Reset appearance and quality controls to their initial state."""
        self.qr_pixel_size = 8
        self.qr_border_size = 3
        self.foreground_color = Gdk.RGBA(red=0, green=0, blue=0, alpha=1)
        self.background_color = Gdk.RGBA(red=1, green=1, blue=1, alpha=1)
        self.error_correction = 0

    def set_paintable(self, paintable: Gdk.Paintable | None):
        """Set the paintable displayed in the QR code preview."""
        self.qr_preview.set_paintable(paintable)

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
        self.emit('new-clicked', btn)
