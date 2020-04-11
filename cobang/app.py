import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio  # noqa

from .resources import get_ui_filepath


class CoBangApplication(Gtk.Application):
    window = None
    main_grid = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id='vn.hoabinh.quan.cobang',
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
                         **kwargs)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.on_quit)
        self.add_action(action)

    def build_main_window(self):
        source = get_ui_filepath('main.glade')
        builder: Gtk.Builder = Gtk.Builder.new_from_file(str(source))
        window: Gtk.Window = builder.get_object('main-window')
        builder.get_object('main-grid')
        window.set_application(self)
        self.set_accels_for_action('app.quit', ('<Ctrl>Q',))
        btn_quit = builder.get_object('btn-quit')
        btn_quit.connect('clicked', self.on_quit, self)
        builder.get_object('stack-img-source')
        return window

    def do_activate(self):
        if not self.window:
            self.window = self.build_main_window()
        self.window.present()

    def do_command_line(self, command_line):
        self.activate()
        return 0

    def on_quit(self, action, param):
        self.quit()
