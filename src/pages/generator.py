from gi.repository import Gtk  # pyright: ignore[reportMissingModuleSource]


@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/generator-page.ui')
class GeneratorPage(Gtk.Box):
    """A page for generating QR code."""
    __gtype_name__ = 'GeneratorPage'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
