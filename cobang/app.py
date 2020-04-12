import gi
from logbook import Logger
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
gi.require_version('Cheese', '3.0')
from gi.repository import Gtk, Gio, Gdk, Gst, GstBase, Cheese  # noqa

from .resources import get_ui_filepath
from .wayland import get_wayland_window_handle


logger = Logger(__name__)
Gst.init(None)

# Require: gstreamer1.0-plugins-bad, gir1.2-gst-plugins-bad-1.0
# https://github.com/sreerenjb/gst-wayland
# https://cgit.freedesktop.org/gstreamer/gst-plugins-bad/tree/tests/examples/waylandsink/main.c
# Some Gstreamer CLI examples
# gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! waylandsink
# gst-launch-1.0 playbin3 uri=v4l2:///dev/video0 video-sink=waylandsink


class CoBangApplication(Gtk.Application):
    window = None
    main_grid = None
    gst_pipeline = None
    camera_devices = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id='vn.hoabinh.quan.cobang',
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
                         **kwargs)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.quit_from_action)
        self.add_action(action)
        self.gst_pipeline = Gst.parse_launch('playbin3 uri=v4l2:///dev/video0 video-sink=waylandsink')
        bus = self.gst_pipeline.get_bus()
        bus.add_signal_watch()
        Cheese.CameraDeviceMonitor.new_async(None, self.camera_monitor_started)
        self.camera_devices = {}

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
        # TODO: Handle Wayland: https://cgit.freedesktop.org/gstreamer/gst-plugins-bad/tree/tests/examples/waylandsink/main.c
        # https://gist.github.com/jonasl/92c1ef32cfd87047e15f5ae24c6b510e
        if window.__class__.__name__ != 'GdkWaylandWindow':
            # X11
            print('Implement later')
        # Wayland
        whandle = get_wayland_window_handle(area_webcam)
        print(whandle)

    def do_activate(self):
        if not self.window:
            self.window = self.build_main_window()
        self.window.present()

    def do_command_line(self, command_line):
        self.activate()
        return 0

    def camera_monitor_started(self, monitor: Cheese.CameraDeviceMonitor, result: Gio.AsyncResult):
        monitor = Cheese.CameraDeviceMonitor.new_finish(result)
        monitor.connect('added', self.on_camera_added)
        monitor.connect('removed', self.on_camera_removed)
        monitor.coldplug()

    def on_camera_added(self, monitor: Cheese.CameraDeviceMonitor, device: Cheese.CameraDevice):
        logger.info('Added {}', device)
        # GstV4l2Src type, but don't know where to import
        src: GstBase.PushSrc = device.get_src()
        loc: str = src.get_property('device')
        self.camera_devices[loc] = device

    def on_camera_removed(self, monitor: Cheese.CameraDeviceMonitor, device: Cheese.CameraDevice):
        logger.info('Removed {}', device)
        src: GstBase.PushSrc = device.get_src()
        loc: str = src.get_property('device')
        self.camera_devices.pop(loc)

    def quit_from_widget(self, widget: Gtk.Widget):
        self.quit()

    def quit_from_action(self, action, param):
        self.quit()
