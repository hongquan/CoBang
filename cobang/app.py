# Copyright © 2020, Nguyễn Hồng Quân <ng.hong.quan@gmail.com>

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#       http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import io
from urllib.parse import urlsplit
from urllib.parse import SplitResult as UrlSplitResult
from typing import Optional, Tuple, Dict

import gi
import zbar
import logbook
from logbook import Logger
from PIL import Image

gi.require_version('GObject', '2.0')
gi.require_version('GLib', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Gio', '2.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Rsvg', '2.0')
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('NM', '1.0')

from gi.repository import GObject, GLib, Gtk, Gdk, Gio, GdkPixbuf, Rsvg, Gst, GstApp, NM

from .consts import APP_ID, SHORT_NAME
from . import __version__
from . import ui
from .common import _
from .resources import get_ui_filepath, guess_content_type, cache_http_file
from .prep import get_device_path, choose_first_image, export_svg, scale_pixbuf
from .messages import WifiInfoMessage, parse_wifi_message


logger = Logger(__name__)
Gst.init(None)

# Some Gstreamer CLI examples
# gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! waylandsink
# gst-launch-1.0 playbin3 uri=v4l2:///dev/video0 video-sink=waylandsink
# Better integration:
#   gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! gtksink
#   gst-launch-1.0 v4l2src ! videoconvert ! glsinkbin sink=gtkglsink


class CoBangApplication(Gtk.Application):
    SINK_NAME = 'sink'
    APPSINK_NAME = 'app_sink'
    STACK_CHILD_NAME_WEBCAM = 'src_webcam'
    STACK_CHILD_NAME_IMAGE = 'src_image'
    GST_SOURCE_NAME = 'webcam_source'
    SIGNAL_QRCODE_DETECTED = 'qrcode-detected'
    window: Optional[Gtk.Window] = None
    main_grid: Optional[Gtk.Grid] = None
    area_webcam: Optional[Gtk.Widget] = None
    cont_webcam: Optional[Gtk.Overlay] = None
    stack_img_source: Optional[Gtk.Stack] = None
    btn_play: Optional[Gtk.RadioToolButton] = None
    # We connect Play button with "toggled" signal, but when we want to imitate mouse click on the button,
    # calling "set_active" on it doesn't work! We have to call on the Pause button instead
    btn_pause: Optional[Gtk.RadioToolButton] = None
    btn_img_chooser: Optional[Gtk.FileChooserButton] = None
    gst_pipeline: Optional[Gst.Pipeline] = None
    zbar_scanner: Optional[zbar.ImageScanner] = None
    raw_result_buffer: Optional[Gtk.TextBuffer] = None
    webcam_combobox: Optional[Gtk.ComboBox] = None
    webcam_store: Optional[Gtk.ListStore] = None
    frame_image: Optional[Gtk.AspectFrame] = None
    # Box holds the emplement to display when no image is chosen
    box_image_empty: Optional[Gtk.Box] = None
    devmonitor: Optional[Gst.DeviceMonitor] = None
    clipboard: Optional[Gtk.Clipboard] = None
    result_display: Optional[Gtk.Frame] = None
    progress_bar: Optional[Gtk.ProgressBar] = None
    infobar: Optional[Gtk.InfoBar] = None
    raw_result_expander: Optional[Gtk.Expander] = None
    nm_client: Optional[NM.Client] = None
    g_event_sources: Dict[str, int] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE, **kwargs
        )
        self.add_main_option(
            'verbose', ord('v'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
            "More detailed log", None
        )

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.setup_actions()
        self.build_gstreamer_pipeline()
        devmonitor = Gst.DeviceMonitor.new()
        devmonitor.add_filter('Video/Source', Gst.Caps.from_string('video/x-raw'))
        logger.debug('Monitor: {}', devmonitor)
        self.devmonitor = devmonitor
        NM.Client.new_async(None, self.cb_networkmanager_client_init_done)

    def setup_actions(self):
        action_quit = Gio.SimpleAction.new('quit', None)
        action_quit.connect('activate', self.quit_from_action)
        self.add_action(action_quit)
        action_about = Gio.SimpleAction.new('about', None)
        action_about.connect('activate', self.show_about_dialog)
        self.add_action(action_about)

    def build_gstreamer_pipeline(self):
        # https://gstreamer.freedesktop.org/documentation/application-development/advanced/pipeline-manipulation.html?gi-language=c#grabbing-data-with-appsink
        # Try GL backend first
        command = (f'v4l2src name={self.GST_SOURCE_NAME} ! tee name=t ! '
                   f'queue ! glsinkbin sink="gtkglsink name={self.SINK_NAME}" name=sink_bin '
                   't. ! queue leaky=2 max-size-buffers=2 ! videoconvert ! video/x-raw,format=GRAY8 ! '
                   f'appsink name={self.APPSINK_NAME} max_buffers=2 drop=1')
        logger.debug('To build pipeline: {}', command)
        try:
            pipeline = Gst.parse_launch(command)
        except GLib.Error as e:
            logger.debug('Error: {}', e)
            pipeline = None
        if not pipeline:
            logger.info('OpenGL is not available, fallback to normal GtkSink')
            # Fallback to non-GL
            command = (f'v4l2src name={self.GST_SOURCE_NAME} ! videoconvert ! tee name=t ! '
                       f'queue ! gtksink name={self.SINK_NAME} '
                       't. ! queue leaky=1 max-size-buffers=2 ! video/x-raw,format=GRAY8 ! '
                       f'appsink name={self.APPSINK_NAME}')
            logger.debug('To build pipeline: {}', command)
            try:
                pipeline = Gst.parse_launch(command)
            except GLib.Error as e:
                # TODO: Print error in status bar
                logger.error('Failed to create Gst Pipeline. Error: {}', e)
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
        builder.get_object('main-grid')
        window.set_application(self)
        self.set_accels_for_action('app.quit', ("<Ctrl>Q",))
        self.stack_img_source = builder.get_object('stack-img-source')
        self.btn_play = builder.get_object('btn-play')
        self.btn_pause = builder.get_object('btn-pause')
        self.btn_img_chooser = builder.get_object('btn-img-chooser')
        self.cont_webcam = builder.get_object('cont-webcam')
        if self.gst_pipeline:
            self.replace_webcam_placeholder_with_gstreamer_sink()
        self.raw_result_buffer = builder.get_object('raw-result-buffer')
        self.raw_result_expander = builder.get_object('raw-result-expander')
        self.webcam_store = builder.get_object('webcam-list')
        self.webcam_combobox = builder.get_object('webcam-combobox')
        self.frame_image = builder.get_object('frame-image')
        self.box_image_empty = builder.get_object('box-image-empty')
        main_menubutton: Gtk.MenuButton = builder.get_object('main-menubutton')
        main_menubutton.set_menu_model(ui.build_app_menu_model())
        self.frame_image.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.frame_image.drag_dest_add_uri_targets()
        self.clipboard = Gtk.Clipboard.get_for_display(Gdk.Display.get_default(),
                                                       Gdk.SELECTION_CLIPBOARD)
        self.result_display = builder.get_object('result-display-frame')
        self.progress_bar = builder.get_object('progress-bar')
        self.infobar = builder.get_object('info-bar')
        box_playpause = builder.get_object('evbox-playpause')
        self.cont_webcam.add_overlay(box_playpause)
        logger.debug('Connect signal handlers')
        builder.connect_signals(handlers)
        self.frame_image.connect('drag-data-received', self.on_frame_image_drag_data_received)
        return window

    def signal_handlers_for_glade(self):
        return {
            'on_btn_play_toggled': self.play_webcam_video,
            'on_webcam_combobox_changed': self.on_webcam_combobox_changed,
            'on_stack_img_source_visible_child_notify': self.on_stack_img_source_visible_child_notify,
            'on_btn_img_chooser_update_preview': self.on_btn_img_chooser_update_preview,
            'on_btn_img_chooser_file_set': self.on_btn_img_chooser_file_set,
            'on_eventbox_key_press_event': self.on_eventbox_key_press_event,
            'on_evbox_playpause_enter_notify_event': self.on_evbox_playpause_enter_notify_event,
            'on_evbox_playpause_leave_notify_event': self.on_evbox_playpause_leave_notify_event,
            'on_info_bar_response': self.on_info_bar_response,
        }

    def discover_webcam(self):
        bus: Gst.Bus = self.devmonitor.get_bus()
        logger.debug('Bus: {}', bus)
        bus.add_watch(GLib.PRIORITY_DEFAULT, self.on_device_monitor_message, None)
        devices = self.devmonitor.get_devices()
        for d in devices:  # type: Gst.Device
            # Device is of private type GstV4l2Device or GstPipeWireDevice
            logger.debug('Found device {}', d.get_path_string())
            cam_name = d.get_display_name()
            cam_path = get_device_path(d)
            self.webcam_store.append((cam_path, cam_name))
        logger.debug('Start device monitoring')
        self.devmonitor.start()

    def do_activate(self):
        if not self.window:
            self.window = self.build_main_window()
            self.zbar_scanner = zbar.ImageScanner()
            self.discover_webcam()
        self.window.present()
        logger.debug("Window {} is shown", self.window)
        # If no webcam is selected, select the first one
        if not self.webcam_combobox.get_active_iter():
            self.webcam_combobox.set_active(0)

    def do_command_line(self, command_line: Gio.ApplicationCommandLine):
        options = command_line.get_options_dict().end().unpack()
        if options.get('verbose'):
            logger.level = logbook.DEBUG
            displayed_apps = os.getenv('G_MESSAGES_DEBUG', '').split()
            displayed_apps.append(SHORT_NAME)
            GLib.setenv('G_MESSAGES_DEBUG', ' '.join(displayed_apps), True)
        self.activate()
        return 0

    def replace_webcam_placeholder_with_gstreamer_sink(self):
        '''
        In glade file, we put a placeholder to reserve a place for putting webcam screen.
        Now it is time to replace that widget with which coming with gtksink.
        '''
        sink = self.gst_pipeline.get_by_name(self.SINK_NAME)
        area = sink.get_property('widget')
        old_area = self.cont_webcam.get_child()
        logger.debug('To replace {} with {}', old_area, area)
        self.cont_webcam.remove(old_area)
        self.cont_webcam.add(area)
        area.show()

    def grab_focus_on_event_box(self):
        event_box: Gtk.EventBox = self.frame_image.get_child()
        event_box.grab_focus()

    def insert_image_to_placeholder(self, pixbuf: GdkPixbuf.Pixbuf):
        stack = self.stack_img_source
        pane: Gtk.AspectFrame = stack.get_visible_child()
        logger.debug('Visible pane: {}', pane.get_name())
        if not isinstance(pane, Gtk.AspectFrame):
            logger.error('Stack seems to be in wrong state')
            return
        try:
            event_box: Gtk.EventBox = pane.get_child()
            child = event_box.get_child()
            logger.debug('Child: {}', child)
        except IndexError:
            logger.error('{} doesnot have child or grandchild!', pane)
            return
        if isinstance(child, Gtk.Image):
            child.set_from_pixbuf(pixbuf)
            return
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        # Detach the box
        logger.debug('Detach {} from {}', child, event_box)
        event_box.remove(child)
        logger.debug('Attach {}', image)
        event_box.add(image)
        image.show()

    def reset_image_placeholder(self):
        stack = self.stack_img_source
        logger.debug('Children: {}', stack.get_children())
        pane: Gtk.AspectFrame = stack.get_child_by_name(self.STACK_CHILD_NAME_IMAGE)
        try:
            event_box: Gtk.EventBox = pane.get_child()
            old_widget = event_box.get_child()
        except IndexError:
            logger.error('Stack seems to be in wrong state')
            return
        if old_widget == self.box_image_empty:
            return
        event_box.remove(old_widget)
        event_box.add(self.box_image_empty)

    def display_url(self, url: UrlSplitResult):
        logger.debug('Found URL: {}', url)
        box = ui.build_url_display(url)
        self.result_display.add(box)
        self.result_display.show_all()

    def display_wifi(self, wifi: WifiInfoMessage):
        box = ui.build_wifi_info_display(wifi, self.nm_client)
        self.result_display.add(box)
        self.result_display.show_all()

    def reset_result(self):
        self.raw_result_buffer.set_text('')
        self.raw_result_expander.set_expanded(False)
        child = self.result_display.get_child()
        if child:
            self.result_display.remove(child)

    def display_result(self, symbols: zbar.SymbolSet):
        # There can be more than one QR code in the image. We just pick the first.
        # No need to to handle StopIteration exception, because this function is called
        # only when QR code is detected from the image.
        sym: zbar.Symbol = next(iter(symbols))
        logger.info('QR type: {}', sym.type)
        raw_data: str = sym.data
        logger.info('Decoded string: {}', raw_data)
        logger.debug('Set text for raw_result_buffer')
        self.raw_result_buffer.set_text(raw_data)
        # Is it a URL?
        try:
            url = urlsplit(raw_data)
        except ValueError:
            url = None
        if url and url.scheme and url.netloc:
            self.display_url(url)
            return
        try:
            wifi = parse_wifi_message(raw_data)
            logger.debug('To display {}', wifi)
            self.display_wifi(wifi)
            return
        except ValueError:
            logger.debug('Not a wellknown message')
            pass
        # Unknown message, just show raw content
        self.raw_result_expander.set_expanded(True)

    def on_device_monitor_message(self, bus: Gst.Bus, message: Gst.Message, user_data):
        logger.debug('Message: {}', message)
        # A private GstV4l2Device or GstPipeWireDevice type
        if message.type == Gst.MessageType.DEVICE_ADDED:
            added_dev: Optional[Gst.Device] = message.parse_device_added()
            if not added_dev:
                return True
            logger.debug('Added: {}', added_dev)
            cam_path = get_device_path(added_dev)
            cam_name = added_dev.get_display_name()
            # Check if this cam already in the list, add to list if not.
            for row in self.webcam_store:
                if row[0] == cam_path:
                    break
            else:
                self.webcam_store.append((cam_path, cam_name))
            return True
        elif message.type == Gst.MessageType.DEVICE_REMOVED:
            removed_dev: Optional[Gst.Device] = message.parse_device_removed()
            if not removed_dev:
                return True
            logger.debug('Removed: {}', removed_dev)
            cam_path = get_device_path(removed_dev)
            ppl_source = self.gst_pipeline.get_by_name(self.GST_SOURCE_NAME)
            if cam_path == ppl_source.get_property('device'):
                self.gst_pipeline.set_state(Gst.State.NULL)
            # Find the entry of just-removed in the list and remove it.
            itr: Optional[Gtk.TreeIter] = None
            for row in self.webcam_store:
                logger.debug('Row: {}', row)
                if row[0] == cam_path:
                    itr = row.iter
                    break
            if itr:
                logger.debug('To remove {} from list', cam_path)
                self.webcam_store.remove(itr)
        return True

    def on_webcam_combobox_changed(self, combo: Gtk.ComboBox):
        if not self.gst_pipeline:
            return
        liter = combo.get_active_iter()
        if not liter:
            return
        model = combo.get_model()
        path, name = model[liter]
        logger.debug('Picked {} {}', path, name)
        ppl_source = self.gst_pipeline.get_by_name(self.GST_SOURCE_NAME)
        self.gst_pipeline.set_state(Gst.State.NULL)
        ppl_source.set_property('device', path)
        self.gst_pipeline.set_state(Gst.State.PLAYING)
        app_sink = self.gst_pipeline.get_by_name(self.APPSINK_NAME)
        app_sink.set_emit_signals(True)

    def on_stack_img_source_visible_child_notify(self, stack: Gtk.Stack, param: GObject.ParamSpec):
        self.reset_result()
        self.btn_img_chooser.unselect_all()
        child = stack.get_visible_child()
        child_name = child.get_name()
        logger.debug('Visible child: {} ({})', child, child_name)
        toolbar = self.btn_play.get_parent()
        if not child_name.endswith('webcam'):
            logger.info('To disable webcam')
            if self.gst_pipeline:
                self.gst_pipeline.set_state(Gst.State.NULL)
            toolbar.hide()
            self.webcam_combobox.hide()
            self.btn_img_chooser.show()
            self.grab_focus_on_event_box()
        elif self.gst_pipeline:
            logger.info('To enable webcam')
            ppl_source = self.gst_pipeline.get_by_name(self.GST_SOURCE_NAME)
            if ppl_source.get_property('device'):
                self.btn_pause.set_active(False)
                self.gst_pipeline.set_state(Gst.State.PLAYING)
            self.btn_img_chooser.hide()
            self.webcam_combobox.show()
            self.reset_image_placeholder()
            toolbar.show()

    def on_btn_img_chooser_update_preview(self, chooser: Gtk.FileChooserButton):
        file_uri: Optional[str] = chooser.get_preview_uri()
        logger.debug('Chose file: {}', file_uri)
        if not file_uri:
            chooser.set_preview_widget_active(False)
            return
        gfile = Gio.file_new_for_uri(file_uri)
        ftype: Gio.FileType = gfile.query_file_type(Gio.FileQueryInfoFlags.NONE, None)
        if ftype != Gio.FileType.REGULAR:
            chooser.set_preview_widget_active(False)
            return
        stream: Gio.FileInputStream = gfile.read(None)
        pix = GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, 200, 400, True, None)
        preview = chooser.get_preview_widget()
        logger.debug('Preview: {}', preview)
        preview.set_from_pixbuf(pix)
        chooser.set_preview_widget_active(True)
        return

    def process_passed_image_file(self, chosen_file: Gio.File, content_type: Optional[str] = None):
        self.reset_result()
        # The file can be remote, so we should read asynchronously
        chosen_file.read_async(GLib.PRIORITY_DEFAULT, None, self.cb_file_read, content_type)
        # If this file is remote, reading it will take time, so we display progress bar.
        if not chosen_file.is_native():
            self.progress_bar.set_visible(True)
            sid = GLib.timeout_add(100, ui.update_progress, self.progress_bar)
            # Properly handle GLib event source
            if self.g_event_sources.get('update_progress'):
                GLib.Source.remove(self.g_event_sources['update_progress'])
            self.g_event_sources['update_progress'] = sid

    def cb_networkmanager_client_init_done(self, client: NM.Client, res: Gio.AsyncResult):
        if not client:
            logger.error('Failed to initialize NetworkManager client')
            return
        client.new_finish(res)
        self.nm_client = client
        logger.debug('NM client: {}', client)

    def cb_file_read(self, remote_file: Gio.File, res: Gio.AsyncResult, content_type: Optional[str] = None):
        w, h = self.get_preview_size()
        gi_stream: Gio.FileInputStream = remote_file.read_finish(res)
        scaled_pix = GdkPixbuf.Pixbuf.new_from_stream_at_scale(gi_stream, w, h, True, None)
        # Prevent freezing GUI
        Gtk.main_iteration()
        self.insert_image_to_placeholder(scaled_pix)
        # Prevent freezing GUI
        Gtk.main_iteration()
        gi_stream.seek(0, GLib.SeekType.SET, None)
        logger.debug('Content type: {}', content_type)
        if content_type == 'image/svg+xml':
            svg: Rsvg.Handle = Rsvg.Handle.new_from_stream_sync(gi_stream, remote_file,
                                                                Rsvg.HandleFlags.FLAGS_NONE, None)
            stream: io.BytesIO = export_svg(svg)
        else:
            stream = io.BytesIO()
            CHUNNK_SIZE = 8192
            # There is no method like read_all_bytes(), so have to do verbose way below
            while True:
                buf: GLib.Bytes = gi_stream.read_bytes(CHUNNK_SIZE, None)
                amount = buf.get_size()
                logger.debug('Read {} bytes', amount)
                stream.write(buf.get_data())
                if amount <= 0:
                    break
        if self.g_event_sources.get('update_progress'):
            GLib.Source.remove(self.g_event_sources['update_progress'])
            del self.g_event_sources['update_progress']
        ui.update_progress(self.progress_bar, 1)
        self.process_passed_rgb_image(stream)

    def process_passed_rgb_image(self, stream: io.BytesIO):
        pim = Image.open(stream)
        grayscale = pim.convert('L')
        w, h = grayscale.size
        img = zbar.Image(w, h, 'Y800', grayscale.tobytes())
        n = self.zbar_scanner.scan(img)
        logger.debug('Any QR code?: {}', n)
        if not n:
            return
        self.display_result(img.symbols)

    def on_btn_img_chooser_file_set(self, chooser: Gtk.FileChooserButton):
        uri: str = chooser.get_uri()
        logger.debug('Chose file: {}', uri)
        # There are some limitation of Gio when handling HTTP remote files, so if encountering
        # HTTP URL, we download it to temporary file then handover to Gio
        if uri.startswith(('http://', 'https://')):
            chosen_file = cache_http_file(uri)
        else:
            chosen_file: Gio.File = Gio.file_new_for_uri(uri)
        # Check file content type
        try:
            content_type = guess_content_type(chosen_file)
        except GLib.Error as e:
            logger.error('Failed to open file. Error {}', e)
            self.show_error('Failed to open file.')
            return
        logger.debug('Content type: {}', content_type)
        if not content_type.startswith('image/'):
            self.show_error(_('Unsuported file type %s!') % content_type)
            return
        self.process_passed_image_file(chosen_file, content_type)
        self.grab_focus_on_event_box()

    def on_frame_image_drag_data_received(self, widget: Gtk.AspectFrame, drag_context: Gdk.DragContext,
                                          x: int, y: int, data: Gtk.SelectionData, info: int, time: int):
        uri: str = data.get_data().strip().decode()
        logger.debug('Dropped URI: {}', uri)
        if not uri:
            logger.debug('Something wrong with desktop environment. No URI is given.')
            return
        chosen_file = Gio.file_new_for_uri(uri)
        self.btn_img_chooser.select_uri(uri)
        content_type = guess_content_type(chosen_file)
        logger.debug('Content type: {}', content_type)
        self.process_passed_image_file(chosen_file, content_type)
        self.grab_focus_on_event_box()

    def on_eventbox_key_press_event(self, widget: Gtk.Widget, event: Gdk.Event):
        logger.debug('Got key press: {}, state {}', event, event.state)
        key_name = Gdk.keyval_name(event.keyval)
        if event.state != Gdk.ModifierType.CONTROL_MASK or key_name != 'v':
            return
        # Pressed Ctrl + V
        self.reset_result()
        logger.debug('Clipboard -> {}', self.clipboard.wait_for_targets())
        pixbuf: Optional[GdkPixbuf.Pixbuf] = self.clipboard.wait_for_image()
        logger.debug('Got pasted image: {}', pixbuf)
        if pixbuf:
            w, h = self.get_preview_size()
            scaled_pixbuf = scale_pixbuf(pixbuf, w, h)
            self.insert_image_to_placeholder(scaled_pixbuf)
            success, content = pixbuf.save_to_bufferv('png', [], [])
            if not success:
                return
            stream = io.BytesIO(content)
            self.process_passed_rgb_image(stream)
            return
        uris = self.clipboard.wait_for_uris()
        logger.debug('URIs: {}', uris)
        if not uris:
            return
        # Get first URI which looks like a URL of an image
        gfile = choose_first_image(uris)
        if not gfile:
            return
        self.btn_img_chooser.select_uri(gfile.get_uri())
        content_type = guess_content_type(gfile)
        self.process_passed_image_file(gfile, content_type)

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
        self.btn_pause.set_active(True)
        self.display_result(img.symbols)
        return Gst.FlowReturn.OK

    def on_evbox_playpause_enter_notify_event(self, box: Gtk.EventBox, event: Gdk.EventCrossing):
        child: Gtk.Widget = box.get_child()
        child.set_opacity(1)

    def on_evbox_playpause_leave_notify_event(self, box: Gtk.EventBox, event: Gdk.EventCrossing):
        child: Gtk.Widget = box.get_child()
        child.set_opacity(0.2)

    def on_info_bar_response(self, infobar: Gtk.InfoBar, response_id: int):
        infobar.set_visible(False)

    def play_webcam_video(self, widget: Optional[Gtk.Widget] = None):
        if not self.gst_pipeline:
            return
        to_pause = (isinstance(widget, Gtk.RadioToolButton) and not widget.get_active())
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
            self.reset_result()
            # Delay set_emit_signals call to prevent scanning old frame
            GLib.timeout_add_seconds(1, app_sink.set_emit_signals, True)

    def get_preview_size(self) -> Tuple[int, int]:
        widget = self.stack_img_source.get_visible_child()
        size, b = widget.get_allocated_size()  # type: Gdk.Rectangle, int
        return (size.width, size.height)

    def show_about_dialog(self, action: Gio.SimpleAction, param: Optional[GLib.Variant] = None):
        if self.gst_pipeline:
            self.btn_pause.set_active(True)
        source = get_ui_filepath('about.glade')
        builder: Gtk.Builder = Gtk.Builder.new_from_file(str(source))
        dlg_about: Gtk.AboutDialog = builder.get_object('dlg-about')
        dlg_about.set_version(__version__)
        logger.debug('To present {}', dlg_about)
        dlg_about.present()

    def show_error(self, message: str):
        box: Gtk.Box = self.infobar.get_content_area()
        label: Gtk.Label = box.get_children()[0]
        label.set_label(message)
        self.infobar.set_message_type(Gtk.MessageType.ERROR)
        self.infobar.set_visible(True)

    def quit_from_action(self, action: Gio.SimpleAction, param: Optional[GLib.Variant] = None):
        self.quit()

    def quit(self):
        if self.gst_pipeline:
            self.gst_pipeline.set_state(Gst.State.NULL)
        super().quit()
