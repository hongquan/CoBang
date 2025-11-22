from __future__ import annotations

from gi.repository import GObject, Gtk  # pyright: ignore[reportMissingModuleSource]


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator-qr-code-page.ui')
class GeneratorQRCodePage(Gtk.Box):
  __gtype_name__ = 'GeneratorQRCodePage'

  qr_picture: Gtk.Picture = Gtk.Template.Child()
  btn_back: Gtk.Button = Gtk.Template.Child()

  @GObject.Signal('back-to-input', flags=GObject.SignalFlags.RUN_LAST)
  def signal_back_to_input(self):
    pass

  @Gtk.Template.Callback()
  def on_btn_back_clicked(self, _btn: Gtk.Button):
    self.emit('back-to-input')
