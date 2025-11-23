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
    Gdk,  # pyright: ignore[reportMissingModuleSource]
    GLib,  # pyright: ignore[reportMissingModuleSource]
    GObject,  # pyright: ignore[reportMissingModuleSource]
    Gtk,  # pyright: ignore[reportMissingModuleSource]
)
from logbook import Logger

from ..consts import GeneratorState
from .generator_qr_code import GeneratorQRCodePage
from .generator_starting import GeneratorStartingPage


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator-page.ui')
class GeneratorPage(Gtk.Box):
    """The main generator page."""

    __gtype_name__ = 'GeneratorPage'

    generator_state = GObject.Property(type=int, default=GeneratorState.INPUTING_REGULAR_TEXT, nick='generator-state')
    starting_page: GeneratorStartingPage = Gtk.Template.Child()
    qr_code_page: GeneratorQRCodePage = Gtk.Template.Child()

    def __init__(self, **kwargs):
        """Initialize the page."""
        super().__init__(**kwargs)
        self.starting_page.connect('generate-qr', self.on_qr_code_generation_requested)
        self.qr_code_page.connect('back-to-start', self.on_back_to_start)

    @Gtk.Template.Callback()
    def is_inputing_regular_text(self, _wd: GeneratorPage, value: int) -> bool:
        """Check if the generator is in input mode."""
        return value == GeneratorState.INPUTING_REGULAR_TEXT

    @Gtk.Template.Callback()
    def is_qr_code_generated(self, _wd: GeneratorPage, value: int) -> bool:
        """Check if the QR code has been generated."""
        return value == GeneratorState.QR_CODE_GENERATED

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
            self.qr_code_page.qr_picture.set_paintable(texture)
            self.generator_state = GeneratorState.QR_CODE_GENERATED
        except GLib.Error as e:
            log.error('Failed to generate QR code image: {}', e)

    def on_back_to_start(self, _src: GeneratorQRCodePage):
        """Handle returning to the starting page."""
        self.starting_page.clear_entry()
        self.generator_state = GeneratorState.INPUTING_REGULAR_TEXT
