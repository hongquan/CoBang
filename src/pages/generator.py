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
    __gtype_name__ = 'GeneratorPage'

    generator_state = GObject.Property(type=int, default=GeneratorState.INPUTING_REGULAR_TEXT, nick='generator-state')
    starting_page: GeneratorStartingPage = Gtk.Template.Child()
    qr_code_page: GeneratorQRCodePage = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.starting_page.connect('generate-qr', self.on_generate_qr)
        self.qr_code_page.connect('back-to-input', self.on_back_to_input)

    @Gtk.Template.Callback()
    def is_inputing_regular_text(self, _wd: GeneratorPage, value: int) -> bool:
        return value == GeneratorState.INPUTING_REGULAR_TEXT

    @Gtk.Template.Callback()
    def is_qr_code_generated(self, _wd: GeneratorPage, value: int) -> bool:
        return value == GeneratorState.QR_CODE_GENERATED

    def on_generate_qr(self, _src: GeneratorStartingPage, text: str):
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

    def on_back_to_input(self, _src: GeneratorQRCodePage):
        self.generator_state = GeneratorState.INPUTING_REGULAR_TEXT
