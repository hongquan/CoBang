from typing import Optional

import gi
import zbar
from logbook import Logger

gi.require_version('GObject', "2.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
gi.require_version("GstApp", "1.0")
gi.require_version("Cheese", "3.0")

from gi.repository import GObject, Gtk, Gio, Gst, GstBase, GstApp, Cheese

from .resources import get_ui_filepath


logger = Logger(__name__)
Gst.init(None)

# Require: gstreamer1.0-plugins-bad, gir1.2-gst-plugins-bad-1.0
# Ref:
# https://github.com/sreerenjb/gst-wayland
# https://github.com/GStreamer/gst-plugins-bad/blob/master/tests/examples/waylandsink/main.c
# https://gist.github.com/jonasl/92c1ef32cfd87047e15f5ae24c6b510e
# Some Gstreamer CLI examples
# gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! waylandsink
# gst-launch-1.0 playbin3 uri=v4l2:///dev/video0 video-sink=waylandsink
# Better integration:
#   gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! gtksink
#   gst-launch-1.0 v4l2src ! videoconvert ! glsinkbin sink=gtkglsink


class CoBangApplication(Gtk.Application):
    SINK_NAME = 'sink'
    APPSINK_NAME = 'app_sink'
    WEBCAM_STACK_CHILD_NAME = 'src_webcam'
    GST_SOURCE_NAME = 'webcam_source'
    SIGNAL_QRCODE_DETECTED = 'qrcode-detected'
    window: Optional[Gtk.Window] = None
    main_grid: Optional[Gtk.Grid] = None
    area_webcam: Optional[Gtk.Widget] = None
    stack_img_source: Optional[Gtk.Stack] = None
    btn_play: Optional[Gtk.RadioToolButton] = None
    gst_pipeline: Optional[Gst.Pipeline] = None
    zbar_scanner: Optional[zbar.ImageScanner] = None
    raw_result_buffer: Optional[Gtk.TextBuffer] = None
    wecam_combobox: Optional[Gtk.ComboBox] = None
    webcam_store: Optional[Gtk.ListStore] = None

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, application_id="vn.hoabinh.quan.cobang", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE, **kwargs
        )

    def do_startup(self):
        Gtk.Application.do_startup(self)
        GObject.signal_new(self.SIGNAL_QRCODE_DETECTED, Gtk.Window, GObject.SignalFlags.RUN_LAST,
                           GObject.TYPE_BOOLEAN, (GObject.TYPE_PYOBJECT,))
        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.quit_from_action)
        self.add_action(action)
        Cheese.CameraDeviceMonitor.new_async(None, self.camera_monitor_started)
        self.build_gstreamer_pipeline()

    def build_gstreamer_pipeline(self):
        # https://gstreamer.freedesktop.org/documentation/application-development/advanced/pipeline-manipulation.html?gi-language=c#grabbing-data-with-appsink
        # Try GL backend first
        command = (f'v4l2src name={self.GST_SOURCE_NAME} ! tee name=t ! '
                   'queue ! glsinkbin sink=gtkglsink name=sink_bin '
                   't. ! queue leaky=2 max-size-buffers=2 ! videoconvert ! video/x-raw,format=GRAY8 ! '
                   f'appsink name={self.APPSINK_NAME} max_buffers=2 drop=1 emit-signals=1')
        logger.debug('To build pipeline: {}', command)
        pipeline = Gst.parse_launch(command)
        if pipeline:
            glbin = pipeline.get_by_name('sink_bin')
            itr = iter(glbin.iterate_sinks())
            glsink = next(itr)
            logger.debug('GtkGLSink: {}', glsink)
            glsink.set_property('name', self.SINK_NAME)
        else:
            # Fallback to non-GL
            command = (f'v4l2src name={self.GST_SOURCE_NAME} ! videoconvert ! tee name=t ! '
                       'queue ! gtksink name={self.SINK_NAME} '
                       't. ! queue leaky=1 max-size-buffers=2 ! video/x-raw,format=GRAY8 ! '
                       f'appsink name={self.APPSINK_NAME} emit-signals=1')
            logger.debug('To build pipeline: {}', command)
            pipeline = Gst.parse_launch(command)
        if not pipeline:
            # TODO: Print error in status bar
            logger.error('Failed to create Gst Pipeline')
            return
        logger.debug('Created {}', pipeline)
        appsink: GstApp.AppSink = pipeline.get_by_name(self.APPSINK_NAME)
        logger.debug('Appsink: {}', appsink)
        appsink.connect('new-sample', self.on_new_webcam_sample)
        self.gst_pipeline = pipeline
        return pipeline

    def build_main_window(self):
        source = get_ui_filepath('main.glade')
        builder: Gtk.Builder = Gtk.Builder.new_from_file(str(source))
        handlers = self.signal_handlers_for_glade()
        window: Gtk.Window = builder.get_object('main-window')
        builder.get_object("main-grid")
        window.set_application(self)
        self.set_accels_for_action("app.quit", ("<Ctrl>Q",))
        self.stack_img_source = builder.get_object("stack-img-source")
        self.btn_play = builder.get_object('btn-play')
        self.replace_webcam_placeholder_with_gstreamer_sink()
        self.raw_result_buffer = builder.get_object('raw-result-buffer')
        self.webcam_store = builder.get_object('webcam-list')
        self.wecam_combobox = builder.get_object('webcam-combobox')
        builder.connect_signals(handlers)
        return window

    def signal_handlers_for_glade(self):
        return {
            "on_btn_quit_clicked": self.quit_from_widget,
            'on_btn_play_toggled': self.play_webcam_video,
            'on_webcam_combobox_changed': self.on_webcam_combobox_changed,
            'on_stack_img_source_visible_child_notify': self.on_stack_img_source_visible_child_notify,
        }

    def do_activate(self):
        if not self.window:
            self.window = self.build_main_window()
            self.zbar_scanner = zbar.ImageScanner()
        self.window.present()
        logger.debug("Window {} is shown", self.window)

    def do_command_line(self, command_line):
        self.activate()
        return 0

    def camera_monitor_started(self, monitor: Cheese.CameraDeviceMonitor, result: Gio.AsyncResult):
        monitor = Cheese.CameraDeviceMonitor.new_finish(result)
        monitor.connect("added", self.on_camera_added)
        monitor.connect("removed", self.on_camera_removed)
        monitor.coldplug()

    def replace_webcam_placeholder_with_gstreamer_sink(self):
        '''
        In glade file, we put a placeholder to reserve a place for putting webcam screen.
        Now it is time to replace that widget with which coming with gtksink.
        '''
        sink = self.gst_pipeline.get_by_name(self.SINK_NAME)
        area = sink.get_property('widget')
        old_area = self.stack_img_source.get_child_by_name(self.WEBCAM_STACK_CHILD_NAME)
        widget_name = old_area.get_name()
        logger.debug('To replace {} with {}', old_area, area)
        # Extract properties of old widget
        property_names = ('icon-name', 'needs-attention', 'position', 'title')
        stack = self.stack_img_source
        properties = {k: stack.child_get_property(old_area, k) for k in property_names}
        # Remove old widget
        self.stack_img_source.remove(old_area)
        self.stack_img_source.add_named(area, self.WEBCAM_STACK_CHILD_NAME)
        for n in property_names:
            stack.child_set_property(area, n, properties[n])
        area.set_name(widget_name)
        area.show()
        self.stack_img_source.set_visible_child(area)

    def on_camera_added(self, monitor: Cheese.CameraDeviceMonitor, device: Cheese.CameraDevice):
        logger.info("Added {}", device)
        # GstV4l2Src type, but don't know where to import
        src: GstBase.PushSrc = device.get_src()
        cam_path: str = src.get_property('device')
        cam_name: str = device.get_name()
        self.webcam_store.append((cam_path, cam_name))
        self.wecam_combobox.set_active_id(cam_path)
        ppl_source = self.gst_pipeline.get_by_name(self.GST_SOURCE_NAME)
        logger.debug('Source: {}', ppl_source)
        ppl_source.set_property('device', cam_path)
        logger.debug('Play {}', self.gst_pipeline)
        self.gst_pipeline.set_state(Gst.State.PLAYING)
        self.btn_play.set_active(True)

    def on_camera_removed(self, monitor: Cheese.CameraDeviceMonitor, device: Cheese.CameraDevice):
        logger.info("Removed {}", device)
        src: GstBase.PushSrc = device.get_src()
        cam_path: str = src.get_property('device')
        ppl_source = self.gst_pipeline.get_by_name(self.GST_SOURCE_NAME)
        if cam_path == ppl_source.get_property('device'):
            self.gst_pipeline.set_state(Gst.State.NULL)

    def on_webcam_combobox_changed(self, combo: Gtk.ComboBox):
        liter = combo.get_active_iter()
        if not liter:
            return
        model = combo.get_model()
        path, name = model[liter]
        logger.debug('{} {}', path, name)
        ppl_source = self.gst_pipeline.get_by_name(self.GST_SOURCE_NAME)
        self.gst_pipeline.set_state(Gst.State.NULL)
        ppl_source.set_property('device', path)
        self.gst_pipeline.set_state(Gst.State.PLAYING)

    def on_stack_img_source_visible_child_notify(self, stack: Gtk.Stack, param: GObject.ParamSpec):
        child = stack.get_visible_child()
        child_name = child.get_name()
        logger.debug('Child: {} ({})', child, child_name)
        toolbar = self.btn_play.get_parent()
        if not child_name.endswith('webcam'):
            logger.info('To disable webcam')
            self.gst_pipeline.set_state(Gst.State.NULL)
            toolbar.hide()
        elif self.gst_pipeline:
            logger.info('To enable webcam')
            ppl_source = self.gst_pipeline.get_by_name(self.GST_SOURCE_NAME)
            if ppl_source.get_property('device'):
                self.gst_pipeline.set_state(Gst.State.PLAYING)
            toolbar.show()

    def on_new_webcam_sample(self, appsink: GstApp.AppSink) -> Gst.FlowReturn:
        if appsink.is_eos():
            return Gst.FlowReturn.OK
        sample: Gst.Sample = appsink.try_pull_sample(0.5)
        buffer: Gst.Buffer = sample.get_buffer()
        caps: Gst.Caps = sample.get_caps()
        # This Pythonic usage is thank to python3-gst
        struct: Gst.Structure = caps[0]
        width = struct['width']
        height = struct['height']
        success, mapinfo = buffer.map(Gst.MapFlags.READ)   # type: bool, Gst.MapInfo
        if not success:
            logger.error('Failed to get mapinfo.')
            return Gst.FlowReturn.ERROR
        img = zbar.Image(width, height, 'Y800', mapinfo.data)
        n = self.zbar_scanner.scan(img)
        logger.debug('Any QR code?: {}', n)
        if not n:
            return Gst.FlowReturn.OK
        # Found QR code in webcam screenshot
        logger.debug('Emulate pressing Pause button')
        self.btn_play.set_active(False)
        try:
            sym = next(iter(img.symbols))
        except StopIteration:
            logger.error('Something wrong. Failed to extract symbol from zbar image!')
            return Gst.FlowReturn.ERROR
        logger.info('QR type: {}', sym.type)
        logger.info('Decoded string: {}', sym.data)
        self.raw_result_buffer.set_text(sym.data)
        return Gst.FlowReturn.OK

    def play_webcam_video(self, widget: Optional[Gtk.Widget] = None):
        to_pause = isinstance(widget, Gtk.RadioToolButton) and not widget.get_active()
        app_sink = self.gst_pipeline.get_by_name(self.APPSINK_NAME)
        source = self.gst_pipeline.get_by_name(self.GST_SOURCE_NAME)
        if to_pause:
            # Tell appsink to stop emitting signals
            logger.debug('Stop appsink from emitting signals')
            app_sink.set_emit_signals(False)
            r = source.set_state(Gst.State.READY)
            r = source.set_state(Gst.State.PAUSED)
            logger.debug('Change {} state to paused: {}', source.get_name(), r)
        else:
            r = source.set_state(Gst.State.PLAYING)
            logger.debug('Change {} state to playing: {}', source.get_name(), r)
            self.raw_result_buffer.set_text('')
            app_sink.set_emit_signals(True)

    def quit_from_widget(self, widget: Gtk.Widget):
        self.quit()

    def quit_from_action(self, action, param):
        self.quit()
