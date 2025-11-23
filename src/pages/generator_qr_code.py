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

from gi.repository import GObject, Gtk  # pyright: ignore[reportMissingModuleSource]
from logbook import Logger


log = Logger(__name__)


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator-qr-code-page.ui')
class GeneratorQRCodePage(Gtk.Box):
  """A page for displaying generated QR code."""

  __gtype_name__ = 'GeneratorQRCodePage'

  qr_picture: Gtk.Picture = Gtk.Template.Child()
  btn_back: Gtk.Button = Gtk.Template.Child()

  @GObject.Signal('back-to-start', flags=GObject.SignalFlags.RUN_LAST)
  def signal_back_to_start(self):  # Emitted when user clicks New
    pass

  def __init__(self, **kwargs):
    """Initialize the page."""
    super().__init__(**kwargs)

  @Gtk.Template.Callback()
  def on_btn_back_clicked(self, _btn: Gtk.Button):
    self.emit('back-to-start')
