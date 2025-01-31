# window.py
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

import io
from gettext import gettext as _
from urllib.parse import urlsplit, SplitResult
from typing import TYPE_CHECKING, Self, Any, cast

import zbar
from logbook import Logger
from PIL import Image
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Gst, GstApp, NM, Xdp  # pyright: ignore[reportMissingModuleSource]
from gi.repository import XdpGtk4  # pyright: ignore[reportMissingModuleSource]

from .consts import JobName, ScanSourceName, GST_SOURCE_NAME, GST_FLIP_FILTER_NAME, GST_SINK_NAME, GST_APP_SINK_NAME
from .messages import WifiInfoMessage, IMAGE_GUIDE, parse_wifi_message
from .ui import build_wifi_info_display, build_url_display
from .prep import guess_mimetype


log = Logger(__name__)


# This UI file is to be compiled from *.blp file.
@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/window.ui')
class CoBangWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'CoBangWindow'

    job_viewstack: Adw.ViewStack = Gtk.Template.Child()
    stackpage_scanner: Adw.ViewStackPage = Gtk.Template.Child()
    scan_source_viewstack: Adw.ViewStack = Gtk.Template.Child()
    toggle_scanner: Gtk.ToggleButton = Gtk.Template.Child()
    toggle_generator: Gtk.ToggleButton = Gtk.Template.Child()
    webcam_display: Gtk.Picture = Gtk.Template.Child()
    box_playpause: Gtk.Box = Gtk.Template.Child()
    btn_pause: Gtk.ToggleButton = Gtk.Template.Child()
    mirror_switch: Gtk.Switch = Gtk.Template.Child()
    frame_image: Gtk.AspectFrame = Gtk.Template.Child()
    image_guide: Gtk.Label = Gtk.Template.Child()
    pasted_image: Gtk.Picture = Gtk.Template.Child()
    btn_filechooser: Gtk.Button = Gtk.Template.Child()
    file_filter: Gtk.FileFilter = Gtk.Template.Child()
    label_chosen_file: Gtk.Label = Gtk.Template.Child()
    result_display_frame: Gtk.Frame = Gtk.Template.Child()
    raw_result_display: Gtk.TextView = Gtk.Template.Child()
    raw_result_expander: Gtk.Expander = Gtk.Template.Child()
    portal_parent: Xdp.Parent
    gst_pipeline: Gst.Pipeline | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.image_guide.set_label(IMAGE_GUIDE)
        self.portal_parent = XdpGtk4.parent_new_gtk(self)
        action = Gio.SimpleAction.new('paste-image', None)
        self.add_action(action)
        action.connect('activate', self.on_paste_image)

    @property
    def portal(self) -> Xdp.Portal:
        if TYPE_CHECKING:
            from .app import CoBangApplication
        app = self.get_application()
        assert app is not None
        return cast('CoBangApplication', app).portal

    @property
    def zbar_scanner(self) -> zbar.ImageScanner:
        if TYPE_CHECKING:
            from .app import CoBangApplication
        app = self.get_application()
        assert app is not None
        return cast('CoBangApplication', app).zbar_scanner

    @property
    def nm_client(self) -> NM.Client | None:
        if TYPE_CHECKING:
            from .app import CoBangApplication
        app = self.get_application()
        assert app is not None
        return cast('CoBangApplication', app).nm_client

    # Ref: https://pygobject.gnome.org/guide/gtk_template.html
    @Gtk.Template.Callback()
    def on_job_viewstack_visible_child_changed(self, viewstack: Adw.ViewStack, *args):
        visible_child_name = viewstack.get_visible_child_name()
        if visible_child_name != JobName.SCANNER:
            self.stop_webcam()
            return
        if not self.gst_pipeline:
            self.request_camera_access()
            return
        if not self.btn_pause.get_active() and self.scan_source_viewstack.get_visible_child_name() == ScanSourceName.WEBCAM:
            self.play_webcam()

    @Gtk.Template.Callback()
    def in_scanner_mode(self, wd: Self, child_name: str) -> bool:
        # TODO: The self is of `Child` type, not `CoBangWindow`. It may change in the future version of PyGObject.
        return child_name == JobName.SCANNER

    @Gtk.Template.Callback()
    def is_empty(self, wd: Self, value: Any) -> bool:
        return not bool(value)

    @Gtk.Template.Callback()
    def has_some(self, wd: Self, value: Any) -> bool:
        return bool(value)

    @Gtk.Template.Callback()
    def switch_to_scanner(self, button: Gtk.ToggleButton):
        name = JobName.SCANNER if button.get_active() else JobName.GENERATOR
        self.job_viewstack.set_visible_child_name(name)

    @Gtk.Template.Callback()
    def on_mirror_switch_toggled(self, switch: Gtk.Switch, active: bool):
        if not self.gst_pipeline:
            return
        if source := self.gst_pipeline.get_by_name(GST_SOURCE_NAME):
            source.set_state(Gst.State.NULL)
        self.gst_pipeline.set_state(Gst.State.NULL)
        if flip_filter := self.gst_pipeline.get_by_name(GST_FLIP_FILTER_NAME):
            flip_filter.set_property('method', 'none' if active else 'horizontal-flip')
        self.gst_pipeline.set_state(Gst.State.PLAYING)

    @Gtk.Template.Callback()
    def on_scan_source_viewstack_visible_child_changed(self, viewstack: Adw.ViewStack, *args):
        self.reset_result()
        visible_child_name = viewstack.get_visible_child_name()
        if visible_child_name == ScanSourceName.WEBCAM:
            self.play_webcam()
            return
        self.stop_webcam()

    @Gtk.Template.Callback()
    def on_btn_pause_toggled(self, button: Gtk.ToggleButton):
        if not self.gst_pipeline:
            return
        to_pause = button.get_active()
        if to_pause:
            app_sink = self.gst_pipeline.get_by_name(GST_APP_SINK_NAME)
            app_sink.set_emit_signals(False)
            source = self.gst_pipeline.get_by_name(GST_SOURCE_NAME)
            source.set_state(Gst.State.PAUSED)
            return
        # There is issue with the pipewiresrc when changing from PAUSED to PLAYING.
        # So we stop the video and play again.
        self.stop_webcam()
        self.play_webcam()
        app_sink = self.gst_pipeline.get_by_name(GST_APP_SINK_NAME)
        app_sink.set_emit_signals(True)

    @Gtk.Template.Callback()
    def on_btn_copy_clicked(self, button: Gtk.Button):
        display = Gdk.Display.get_default()
        clipboard = display.get_clipboard()
        buffer = self.raw_result_display.get_buffer()
        buffer.select_range(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.copy_clipboard(clipboard)
        button.set_tooltip_text(_('Copied!'))
        GLib.timeout_add_seconds(3, lambda: button.set_has_tooltip(False))

    @Gtk.Template.Callback()
    def on_btn_filechooser_clicked(self, button: Gtk.Button):
        dlg = Gtk.FileDialog(default_filter=self.file_filter, modal=True)
        dlg.open(self, None, self.cb_file_dialog)

    def on_camera_access_request(self, portal: Xdp.Portal, result: Gio.AsyncResult):
        # When testing with Ghostty terminal, the app lost focus and the portal request is denied.
        try:
            success = portal.access_camera_finish(result)
        except GLib.Error as e:
            log.error('Failed to access camera: {}', e)
            return
        log.info('Allowed to access camera: {}', success)
        if not success:
            return
        # Ref: https://github.com/workbenchdev/demos/blob/main/src/Camera/main.py#L33
        video_fd = portal.open_pipewire_remote_for_camera()
        log.info('Pipewire remote fd: {}', video_fd)
        pipeline = self.build_gstreamer_pipeline(video_fd)
        if not pipeline:
            return
        self.attach_gstreamer_sink_to_window(pipeline)
        if not self.btn_pause.get_active():
            self.play_webcam()
        self.enable_webcam_consumption(pipeline)

    @Gtk.Template.Callback()
    def on_shown(self, *args):
        GLib.timeout_add_seconds(1, self.request_camera_access)

    def request_camera_access(self):
        has_camera = self.portal.is_camera_present()
        log.info('Is webcam available: {}', has_camera)
        # TODO: Show banner to tell user that camera is not available.
        # Ref: https://lazka.github.io/pgi-docs/#Xdp-1.0/classes/Portal.html#Xdp.Portal.access_camera
        self.portal.access_camera(
            self.portal_parent,
            Xdp.CameraFlags.NONE,
            None,
            self.on_camera_access_request,
        )

    def build_gstreamer_pipeline(self, webcam_fd: int) -> Gst.Pipeline | None:
        # Note: Setting custom name for gtk4paintablesink does not work.
        flip_method = 'horizontal-flip' if self.mirror_switch.get_active() else 'none'
        cmd = (f'pipewiresrc name={GST_SOURCE_NAME} fd={webcam_fd} ! videoflip name={GST_FLIP_FILTER_NAME} method={flip_method} ! videoconvert ! tee name=t ! '
               'queue ! videoscale ! '
               f'glsinkbin sink="gtk4paintablesink name={GST_SINK_NAME}" name=sink_bin '
               't. ! queue leaky=2 max-size-buffers=2 ! videoconvert ! video/x-raw,format=GRAY8 ! '
               f'appsink name={GST_APP_SINK_NAME} max_buffers=2 drop=1')
        log.info('To build pipeline: {}', cmd)
        try:
            pipeline = cast(Gst.Pipeline, Gst.parse_launch(cmd))
        except GLib.Error as e:
            log.error('Failed to build pipeline: {}', e)
            # TODO: Print error message to user.
            self.gst_pipeline = None
            return None
        log.debug('Pipeline built: {}', pipeline)
        return pipeline

    def attach_gstreamer_sink_to_window(self, pipeline: Gst.Pipeline):
        sinkbin = pipeline.get_by_name('sink_bin')
        if not sinkbin:
            log.error('Failed to get glsinkbin element')
            return
        gtk4_sink = sinkbin.get_property('sink')
        log.info('Gtk4 sink: {}', gtk4_sink)
        paintable = gtk4_sink.get_property('paintable')
        self.webcam_display.set_paintable(paintable)
        self.gst_pipeline = pipeline

    def play_webcam(self):
        log.info('Playing webcam')
        if self.gst_pipeline:
            self.gst_pipeline.set_state(Gst.State.PLAYING)

    def stop_webcam(self):
        log.info('Stopping webcam')
        if self.gst_pipeline:
            self.gst_pipeline.set_state(Gst.State.NULL)

    def enable_webcam_consumption(self, pipeline: Gst.Pipeline):
        if app_sink := pipeline.get_by_name(GST_APP_SINK_NAME):
            log.debug('Appsink: {}', app_sink)
            app_sink.set_emit_signals(True)
            app_sink.connect('new-sample', self.on_new_webcam_sample)
        else:
            log.warning('Appsink not found in pipeline')

    def disable_webcam_consumption(self, pipeline: Gst.Pipeline):
        if app_sink := pipeline.get_by_name(GST_APP_SINK_NAME):
            log.debug('Appsink: {}', app_sink)
            app_sink.set_emit_signals(False)
            app_sink.disconnect_by_func(self.on_new_webcam_sample)
        else:
            log.warning('Appsink not found in pipeline')

    def on_new_webcam_sample(self, appsink: GstApp.AppSink) -> Gst.FlowReturn:
        if appsink.is_eos():
            return Gst.FlowReturn.OK
        sample = cast(Gst.Sample | None, appsink.try_pull_sample(0.5))
        if not sample:
            return Gst.FlowReturn.OK
        buffer = sample.get_buffer()
        if not buffer:
            return Gst.FlowReturn.OK
        caps = sample.get_caps()
        if not caps:
            return Gst.FlowReturn.OK
        struct = caps.get_structure(0)
        exist, width = struct.get_int('width')
        if not exist:
            log.error('Failed to get width from caps')
            return Gst.FlowReturn.ERROR
        exist, height = struct.get_int('height')
        if not exist:
            log.error('Failed to get height from caps')
            return Gst.FlowReturn.ERROR
        success, mapinfo = buffer.map(Gst.MapFlags.READ)
        if not success:
            log.error('Failed to get mapinfo from Gst AppSink.')
            return Gst.FlowReturn.ERROR
        # The documentation https://lazka.github.io/pgi-docs/#Gst-1.0/classes/MapInfo.html says that
        # the .data is a bytes, but in Ubuntu, it is a memoryview.
        image_data = mapinfo.data.tobytes() if isinstance(mapinfo.data, memoryview) else mapinfo.data
        img = zbar.Image(width, height, 'Y800', image_data)
        n = self.zbar_scanner.scan(img)
        log.info('Scanned {} symbols', n)
        if not n:
            return Gst.FlowReturn.OK
        # Found QR code in webcam screenshot
        # Pause video to prevent further processing.
        self.btn_pause.set_active(True)
        GLib.idle_add(self.display_result, img.symbols)
        return Gst.FlowReturn.OK

    def on_paste_image(self, *args):
        log.info('Args: {}', args)
        display = Gdk.Display.get_default()
        log.debug('Display: {}', display)
        clipboard = display.get_clipboard()
        log.debug('Clipboard: {}', clipboard)
        fmt = clipboard.get_formats()
        log.debug('Clipboard formats: {}', fmt.get_gtypes())
        # Try reading texture first.
        clipboard.read_texture_async(None, self.cb_texture_read_from_clipboard)

    def cb_texture_read_from_clipboard(self, clipboard: Gdk.Clipboard, result: Gio.AsyncResult):
        try:
            texture = clipboard.read_texture_finish(result)
            log.info('Texture: {}', texture)
            self.pasted_image.set_paintable(texture)
            self.pasted_image.set_visible(True)
            return
        except GLib.Error:
            log.debug('No texture in clipboard')
        # If there is no texture, try reading file.
        clipboard.read_value_async(Gio.File, GObject.PRIORITY_DEFAULT_IDLE, None, self.cb_file_read_from_clipboard)

    def cb_file_read_from_clipboard(self, clipboard: Gdk.Clipboard, result: Gio.AsyncResult):
        try:
            image = cast(Gio.File, clipboard.read_value_finish(result))
            log.info('File: {}', image)
            mime_type = guess_mimetype(image)
            log.info('MIME type: {}', mime_type)
            if not mime_type or not mime_type.startswith('image/'):
                log.info('Not an image. Ignore.')
                return
            self.process_passed_image_file(image, mime_type)
        except GLib.Error:
            log.debug('No file in clipboard')

    def cb_file_dialog(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult):
        try:
            file = dialog.open_finish(result)
        except GLib.Error as e:
            log.info('Failed to open file: {}', e)
            return
        if not file:
            log.info('No file chosen.')
            return
        mime_type = guess_mimetype(file)
        log.info('MIME type: {}', mime_type)
        if not mime_type or not mime_type.startswith('image/'):
            log.info('Not an image. Ignore.')
            return
        basename = file.get_basename()
        self.label_chosen_file.set_text(basename or '')
        self.process_passed_image_file(file, mime_type)

    def process_passed_image_file(self, chosen_file: Gio.File, content_type: str):
        self.reset_result()
        # The file can be remote, so we should read asynchronously
        self.pasted_image.set_file(chosen_file)
        GLib.main_context_default().iteration(False)
        self.pasted_image.set_visible(True)
        paintable = cast(Gdk.Texture | None, self.pasted_image.get_paintable())
        log.info('Paintable: {}', paintable)
        if not paintable:
            log.debug('No paintable. Ignore.')
            return
        w = paintable.get_width()
        h = paintable.get_height()
        log.info('Paintable size: {}x{}', w, h)
        img_bytes = paintable.save_to_png_bytes().get_data()
        if not img_bytes:
            return
        img_file = io.BytesIO(img_bytes)
        rgb_img = Image.open(img_file)
        # ZBar needs grayscale image
        grayscale = rgb_img.convert('L')
        zimg = zbar.Image(w, h, 'Y800', grayscale.tobytes())
        n = self.zbar_scanner.scan(zimg)
        log.debug('Any QR code?: {}', n)
        if not n:
            return
        GLib.idle_add(self.display_result, zimg.symbols)

    def display_result(self, symbols: zbar.SymbolSet):
        # There can be more than one QR code in the image. We just pick the first.
        # No need to to handle StopIteration exception, because this function is called
        # only when QR code is detected from the image.
        sym: zbar.Symbol = next(iter(symbols))
        log.info('QR type: {}', sym.type)
        # We expect ZBar to return bytes, but it returns str.
        raw_data = cast(str, sym.data)
        log.info('Decoded string: {}', raw_data)
        log.debug('Set text for raw_result_buffer')
        buffer = self.raw_result_display.get_buffer()
        buffer.set_text(raw_data)
        try:
            url = urlsplit(raw_data)
            if url.scheme and url.netloc:
                log.info('Parsed URL: {}', url)
                self.display_url(url)
                return
        except ValueError:
            pass
        if wifi := parse_wifi_message(raw_data):
            log.info('Parsed wifi message: {}', wifi)
            self.display_wifi(wifi)
            return
        # Non-welknown QR code. Just display the raw data.
        log.info('Unknown QR code. Display raw data.')
        self.raw_result_expander.set_expanded(True)

    def display_wifi(self, wifi: WifiInfoMessage):
        log.debug('Displaying wifi info: {}', wifi)
        box = build_wifi_info_display(wifi, self.nm_client)
        self.result_display_frame.set_child(box)

    def display_url(self, url: SplitResult):
        log.debug('Displaying URL: {}', url)
        box = build_url_display(url)
        self.result_display_frame.set_child(box)

    def reset_result(self):
        log.info('Reset result display')
        buffer = self.raw_result_display.get_buffer()
        buffer.set_text('')
        self.result_display_frame.set_child(None)
        self.pasted_image.set_visible(False)
        self.pasted_image.set_file(None)
