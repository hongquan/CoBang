# generator_starting.py
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

from gi.repository import GObject, Gtk  # pyright: ignore[reportMissingModuleSource]
from logbook import Logger


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator-starting-page.ui')
class GeneratorStartingPage(Gtk.Box):
    """A starting page for QR code generator."""

    __gtype_name__ = 'GeneratorStartingPage'

    text_entry: Gtk.Entry = Gtk.Template.Child()
    btn_generate: Gtk.Button = Gtk.Template.Child()

    @GObject.Signal('generate-qr', flags=GObject.SignalFlags.RUN_LAST, arg_types=(str,))
    def signal_generate_qr(self, text: str):  # Emitted when user clicks Generate
        pass

    def __init__(self, **kwargs):
        """Initialize the page and connect entry events."""
        super().__init__(**kwargs)
        self.text_entry.connect('activate', self.on_entry_activated)

    @Gtk.Template.Callback()
    def on_btn_generate_clicked(self, _btn: Gtk.Button):
        text = self.get_entry_text().strip()
        if text:
            self.emit('generate-qr', text)

    def get_entry_text(self) -> str:
        """Get the text from the entry widget."""
        return self.text_entry.get_text()

    def clear_entry(self):
        """Clear the entry widget."""
        self.text_entry.set_text('')

    def on_entry_activated(self, entry: Gtk.Entry):
        """Handle Enter key in the entry field."""
        self.on_btn_generate_clicked(None)
