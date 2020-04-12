import gi
from logbook import Logger
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, Gdk  # noqa

from .resources import get_ui_filepath


logger = Logger(__name__)


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
        action.connect("activate", self.quit_from_action)
        self.add_action(action)

    def build_main_window(self):
        source = get_ui_filepath('main.glade')
        builder: Gtk.Builder = Gtk.Builder.new_from_file(str(source))
        handlers = self.signal_handlers_for_glade()
        builder.connect_signals(handlers)
        window: Gtk.Window = builder.get_object('main-window')
        builder.get_object('main-grid')
        window.set_application(self)
        self.set_accels_for_action('app.quit', ('<Ctrl>Q',))
        builder.get_object('stack-img-source')
        return window

    def signal_handlers_for_glade(self):
        return {
            'on_area_webcam_realize': self.pass_window_to_gstreamer,
            'on_btn_quit_clicked': self.quit_from_widget
        }

    def pass_window_to_gstreamer(self, area_webcam: Gtk.DrawingArea):
        window: Gdk.Window = area_webcam.get_window()
        is_native = window.ensure_native()
        if not is_native:
            logger.error('DrawingArea {} is not a native window', area_webcam.get_name())
            return
        print(window)

    def do_activate(self):
        if not self.window:
            self.window = self.build_main_window()
        self.window.present()

    def do_command_line(self, command_line):
        self.activate()
        return 0

    def quit_from_widget(self, widget: Gtk.Widget):
        self.quit()

    def quit_from_action(self, action, param):
        self.quit()
