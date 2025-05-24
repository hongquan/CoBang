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
import os
from locale import gettext as _
from urllib.parse import urlsplit, SplitResult
from typing import TYPE_CHECKING, Self, Any, cast

import zbar
from logbook import Logger
from PIL import Image
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Gst, GstApp, NM, Xdp  # pyright: ignore[reportMissingModuleSource]
from gi.repository import XdpGtk4  # pyright: ignore[reportMissingModuleSource]

from .consts import JobName, ScanSourceName, WebcamPageLayoutName, ScannerState, DeviceSourceType, ENV_EMULATE_SANDBOX, GST_SOURCE_NAME, GST_FLIP_FILTER_NAME, GST_SINK_NAME, GST_APP_SINK_NAME
from .custom_types import WebcamDeviceInfo
from .messages import WifiInfoMessage, IMAGE_GUIDE, parse_wifi_message
from .ui import build_wifi_info_display, build_url_display
from .prep import guess_mimetype, get_device_path


log = Logger(__name__)


# This UI file is to be compiled from *.blp file.
@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/window.ui')
class CoBangWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'CoBangWindow'
    scanner_state = GObject.Property(type=int, default=0, nick='scanner-state')

    job_viewstack: Adw.ViewStack = Gtk.Template.Child()
    stackpage_scanner: Adw.ViewStackPage = Gtk.Template.Child()
    scan_source_viewstack: Adw.ViewStack = Gtk.Template.Child()
    toggle_scanner: Gtk.ToggleButton = Gtk.Template.Child()
    toggle_generator: Gtk.ToggleButton = Gtk.Template.Child()
    webcam_multilayout: Adw.MultiLayoutView = Gtk.Template.Child()
    webcam_display: Gtk.Picture = Gtk.Template.Child()
    box_playpause: Gtk.Box = Gtk.Template.Child()
    btn_pause: Gtk.ToggleButton = Gtk.Template.Child()
    mirror_switch: Gtk.Switch = Gtk.Template.Child()
    frame_image: Gtk.AspectFrame = Gtk.Template.Child()
    image_guide: Gtk.Label = Gtk.Template.Child()
    pasted_image: Gtk.Picture = Gtk.Template.Child()
    image_drop_target: Gtk.DropTargetAsync = Gtk.Template.Child()
    btn_filechooser: Gtk.Button = Gtk.Template.Child()
    file_filter: Gtk.FileFilter = Gtk.Template.Child()
    label_chosen_file: Gtk.Label = Gtk.Template.Child()
    scanner_page_multilayout: Adw.MultiLayoutView = Gtk.Template.Child()
    scanner_bottom_sheet: Adw.BottomSheet = Gtk.Template.Child()
    result_display_frame: Gtk.Frame = Gtk.Template.Child()
    result_bin: Adw.Bin = Gtk.Template.Child()
    raw_result_display: Gtk.TextView = Gtk.Template.Child()
    raw_result_expander: Gtk.Expander = Gtk.Template.Child()
    portal_parent: Xdp.Parent
    gst_pipeline: Gst.Pipeline | None = None
    dev_monitor: Gst.DeviceMonitor | None = None
    webcam_store: Gio.ListStore = Gtk.Template.Child()
    webcam_dropdown: Gtk.DropDown = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.webcam_multilayout.set_layout_name(WebcamPageLayoutName.REQUESTING)
        self.image_guide.set_label(IMAGE_GUIDE)
        self.portal_parent = XdpGtk4.parent_new_gtk(self)
        action = Gio.SimpleAction.new('paste-image', None)
        self.add_action(action)
        action.connect('activate', self.on_paste_image)
        if self.is_outside_sandbox:
            self.dev_monitor = Gst.DeviceMonitor.new()
            self.dev_monitor.add_filter('Video/Source', Gst.Caps.from_string('video/x-raw'))
            log.debug('Device monitor: {}', self.dev_monitor)

    @property
    def portal(self) -> Xdp.Portal:
        if TYPE_CHECKING:
            from .app import CoBangApplication
        app = self.get_application()
        assert app is not None
        return cast('CoBangApplication', app).portal

    @property
    def is_outside_sandbox(self) -> bool:
        return not self.portal.running_under_sandbox() and not os.getenv(ENV_EMULATE_SANDBOX)

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
    def is_idle(self, wd: Self, value: int) -> bool:
        return value == ScannerState.IDLE

    @Gtk.Template.Callback()
    def is_scanning(self, wd: Self, value: int) -> bool:
        return value == ScannerState.SCANNING

    @Gtk.Template.Callback()
    def is_no_result(self, wd: Self, value: int) -> bool:
        return value == ScannerState.NO_RESULT

    @Gtk.Template.Callback()
    def has_scanning_result(self, wd: Self, value: int) -> bool:
        return value > ScannerState.NO_RESULT

    @Gtk.Template.Callback()
    def scanning_result_title(self, wd: Self, value: int) -> str:
        if value == ScannerState.WIFI_FOUND:
            return _('Found a wifi configuration')
        if value == ScannerState.URL_FOUND:
            return _('Found a URL. Click to open:')
        if value == ScannerState.TEXT_FOUND:
            return _('Found unrecognized text.')
        return _('Unknown')

    @Gtk.Template.Callback()
    def passed_image_name(self, wd: Self, file: Gio.File | None) -> str:
        return file.get_basename() if file else ''

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
            if not self.gst_pipeline:
                self.request_camera_access()
                return
            if not self.btn_pause.get_active():
                self.play_webcam()
            return
        self.stop_webcam()

    @Gtk.Template.Callback()
    def on_btn_pause_toggled(self, button: Gtk.ToggleButton):
        to_pause = button.get_active()
        self.scanner_state = ScannerState.IDLE if to_pause else ScannerState.SCANNING
        if not self.gst_pipeline:
            return
        if to_pause:
            app_sink = self.gst_pipeline.get_by_name(GST_APP_SINK_NAME)
            app_sink.set_emit_signals(False)
            source = self.gst_pipeline.get_by_name(GST_SOURCE_NAME)
            source.set_state(Gst.State.PAUSED)
            return
        # There is issue with the pipewiresrc when changing from PAUSED to PLAYING.
        # So we stop the video and play again.
        if not self.is_outside_sandbox:
            self.stop_webcam()
        self.play_webcam()
        app_sink = self.gst_pipeline.get_by_name(GST_APP_SINK_NAME)
        app_sink.set_emit_signals(True)

    @Gtk.Template.Callback()
    def on_btn_show_result_clicked(self, button: Gtk.Button):
        self.scanner_bottom_sheet.set_open(True)

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

    @Gtk.Template.Callback()
    def on_webcam_device_selected(self, dropdown: Gtk.DropDown, *args):
        log.debug('on_webcam_device_selected args: {}', args)
        item = dropdown.get_selected_item()
        assert isinstance(item, WebcamDeviceInfo)
        log.info('Selected device: {}', item)
        if self.scan_source_viewstack.get_visible_child_name() != ScanSourceName.WEBCAM:
            return
        # Destroy the old pipeline if any.
        if self.gst_pipeline:
            self.gst_pipeline.set_state(Gst.State.NULL)
            self.gst_pipeline = None
        # Build a new pipeline.
        pipeline = self.build_gstreamer_pipeline_direct_access(item.source_type, item.path)
        if not pipeline:
            return
        self.attach_gstreamer_sink_to_window(pipeline)
        if not self.btn_pause.get_active():
            self.play_webcam()
            self.scanner_state = ScannerState.SCANNING
        self.enable_webcam_consumption(pipeline)

    @Gtk.Template.Callback()
    def on_shown(self, *args):
        scan_source = self.scan_source_viewstack.get_visible_child_name()
        log.info('Scan source: {}', scan_source)
        if scan_source != ScanSourceName.WEBCAM:
            return
        if not self.is_outside_sandbox:
            # In sandbox, we need to request camera access.
            self.request_camera_access()
        # Outside sandbox, we can access the webcam directly.
        else:
            self.discover_webcam()

    @Gtk.Template.Callback()
    def on_image_drop_target_accept(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop):
        fmt = drop.get_formats()
        log.info('Drop formats: {}', fmt.to_string())
        return fmt.contain_gtype(Gio.File)

    @Gtk.Template.Callback()
    def on_image_dropped(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop, x: float, y: float):
        drop.read_value_async(Gio.File, GObject.PRIORITY_DEFAULT_IDLE, None, self.cb_file_read_from_drag_n_drop)
        return True

    def cb_camera_access_request(self, portal: Xdp.Portal, result: Gio.AsyncResult):
        # When testing with Ghostty terminal, the app lost focus and the portal request is denied.
        try:
            success = portal.access_camera_finish(result)
        except GLib.Error as e:
            log.error('Failed to access camera: {}', e)
            return
        log.info('Allowed to access camera: {}', success)
        if not success:
            self.webcam_multilayout.set_layout_name(WebcamPageLayoutName.UNAVAILABLE)
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
            self.scanner_state = ScannerState.SCANNING
        self.enable_webcam_consumption(pipeline)

    def request_camera_access(self):
        has_camera = self.portal.is_camera_present()
        log.info('Is webcam available: {}', has_camera)
        if not has_camera:
            self.webcam_multilayout.set_layout_name(WebcamPageLayoutName.UNAVAILABLE)
            return
        self.webcam_multilayout.set_layout_name(WebcamPageLayoutName.AVAILABLE)
        # Ref: https://lazka.github.io/pgi-docs/#Xdp-1.0/classes/Portal.html#Xdp.Portal.access_camera
        self.portal.access_camera(
            self.portal_parent,
            Xdp.CameraFlags.NONE,
            None,
            self.cb_camera_access_request,
        )

    def discover_webcam(self):
        devices = self.dev_monitor.get_devices() or []
        for d in devices:
            log.debug('Found device {}', d.get_path_string())
            device_path, src_type = get_device_path(d)
            device_name = d.get_display_name()
            if not device_name or src_type not in DeviceSourceType:
                log.info('Unsupported device: {} {}', src_type, d.get_path_string())
                continue
            self.webcam_store.append(WebcamDeviceInfo(source_type=src_type, path=device_path, name=device_name))
            log.debug('Added device {}', device_path)
        # If found any device, set the first one as selected.
        if next(iter(self.webcam_store), None):
            self.webcam_multilayout.set_layout_name(WebcamPageLayoutName.AVAILABLE)
            self.webcam_dropdown.set_selected(0)
        # Continue to monitor for new devices.
        bus = self.dev_monitor.get_bus()
        bus.add_watch(GLib.PRIORITY_DEFAULT, self.on_device_monitor_message, None)
        log.debug('Start device monitoring')
        self.dev_monitor.start()

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

    # Ref:
    # - For pipewiresrc: https://github.com/PipeWire/pipewire/blob/1.2.4/src/gst/gstpipewiresrc.c
    # - gstpipewiredeviceprovider: https://github.com/PipeWire/pipewire/blob/1.2.4/src/gst/gstpipewiredeviceprovider.c
    def build_gstreamer_pipeline_direct_access(self, src_type: DeviceSourceType, video_path: str) -> Gst.Pipeline | None:
        """Build GStreamer Pipeline to access webcam directly (via V4L2), when running outside sandbox."""
        flip_method = 'horizontal-flip' if self.mirror_switch.get_active() else 'none'
        source_desc_parts = [
            src_type,
            f'name={GST_SOURCE_NAME}',
            f'device={video_path}' if src_type == DeviceSourceType.V4L2 else f'target-object={video_path}',
        ]
        source_desc = ' '.join(source_desc_parts)
        cmd = (f'{source_desc} ! videoflip name={GST_FLIP_FILTER_NAME} method={flip_method} ! videoconvert ! tee name=t ! '
               'queue ! videoscale ! '
               f'glsinkbin sink="gtk4paintablesink name={GST_SINK_NAME}" name=sink_bin '
               't. ! queue leaky=2 max-size-buffers=2 ! videoconvert ! video/x-raw,format=GRAY8 ! '
               f'appsink name={GST_APP_SINK_NAME} max_buffers=2 drop=1')
        log.info('To build pipeline: {}', cmd)
        try:
            pipeline = cast(Gst.Pipeline, Gst.parse_launch(cmd))
        except GLib.Error as e:
            log.error('Failed to build pipeline: {}', e)
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
            self.scanner_state = ScannerState.SCANNING

    def stop_webcam(self):
        log.info('Stopping webcam')
        self.scanner_state = ScannerState.IDLE
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

    def on_device_monitor_message(self, bus: Gst.Bus, message: Gst.Message, user_data: Any) -> bool:
        # A private GstV4l2Device or GstPipeWireDevice type
        if message.type == Gst.MessageType.DEVICE_ADDED:
            added_dev = message.parse_device_added()
            log.debug('Detected device: {}', added_dev)
            cam_path, src_type = get_device_path(added_dev)
            cam_name = added_dev.get_display_name()
            if not cam_path or src_type not in DeviceSourceType:
                log.info('Unsupported device: {} {}', src_type, added_dev.get_path_string())
                return True
            # Check if this cam already in the list, add to list if not.
            found = any(True for d in self.webcam_store if d.path == cam_path)
            if not found:
                self.webcam_store.append(WebcamDeviceInfo(source_type=src_type, path=cam_path, name=cam_name))
                log.debug('{} was not in the store. Added.', cam_path)
            return True
        elif message.type == Gst.MessageType.DEVICE_REMOVED:
            removed_dev = message.parse_device_removed()
            log.debug('Removed: {}', removed_dev)
            cam_path, src_type = get_device_path(removed_dev)
            if not cam_path or src_type not in DeviceSourceType:
                log.info('Unsupported device: {} {}', src_type, removed_dev.get_path_string())
                return True
            ppl_source = self.gst_pipeline.get_by_name(GST_SOURCE_NAME)
            if cam_path == ppl_source.get_property('device') or cam_path == ppl_source.get_property('target-object'):
                self.gst_pipeline.set_state(Gst.State.NULL)
            # Find the entry of just-removed in the list and remove it.
            try:
                pos = next(i for i, d in enumerate(self.webcam_store) if d.path == cam_path)
                log.debug('To remove {} from list', cam_path)
                self.webcam_store.remove(pos)
            except StopIteration:
                pass
        return True

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

    def cb_file_read_from_drag_n_drop(self, drop: Gdk.Drop, result: Gio.AsyncResult):
        try:
            file = drop.read_value_finish(result)
        except GLib.Error as e:
            log.info('Failed to read file from drop: {}', e)
            return
        finally:
            drop.finish(Gdk.DragAction.COPY)
        if not file:
            log.info('No file chosen.')
            return
        mime_type = guess_mimetype(file)
        log.info('MIME type: {}', mime_type)
        if not mime_type or not mime_type.startswith('image/'):
            log.info('Not an image. Ignore.')
            return
        self.process_passed_image_file(file, mime_type)

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
        self.process_passed_image_file(file, mime_type)

    def process_file_from_commandline(self, file: Gio.File, mime_type: str):
        self.job_viewstack.set_visible_child_name(JobName.SCANNER)
        self.scan_source_viewstack.set_visible_child_name(ScanSourceName.IMAGE)
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
        # ZBar needs grayscale image, the Gdk.Paintable is RGBA,
        # we need to convert it to grayscale, replacing transparency with white.
        # Because the source image can have alpha channel, we need to convert it to LA.
        grayscale = rgb_img.convert('LA')
        # Create an all-white image as background.
        canvas = Image.new('LA', (w, h), (255, 255))
        canvas.paste(grayscale, mask=grayscale)
        zimg = zbar.Image(w, h, 'Y800', canvas.convert('L').tobytes())
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
                self.scanner_bottom_sheet.set_open(True)
                return
        except ValueError:
            pass
        if wifi := parse_wifi_message(raw_data):
            log.info('Parsed wifi message: {}', wifi)
            self.display_wifi(wifi)
            self.scanner_bottom_sheet.set_open(True)
            return
        # Non-welknown QR code. Just display the raw data.
        log.info('Unknown QR code. Display raw data.')
        self.scanner_state = ScannerState.TEXT_FOUND
        self.raw_result_expander.set_expanded(True)
        self.scanner_bottom_sheet.set_open(True)

    def display_wifi(self, wifi: WifiInfoMessage):
        log.debug('Displaying wifi info: {}', wifi)
        box = build_wifi_info_display(wifi, self.nm_client)
        self.result_bin.set_child(box)
        self.scanner_state = ScannerState.WIFI_FOUND

    def display_url(self, url: SplitResult):
        log.debug('Displaying URL: {}', url)
        box = build_url_display(url)
        self.result_bin.set_child(box)
        self.scanner_state = ScannerState.URL_FOUND

    def reset_result(self):
        log.info('Reset result display')
        self.scanner_state = ScannerState.IDLE
        buffer = self.raw_result_display.get_buffer()
        buffer.set_text('')
        self.result_bin.set_child(None)
        self.pasted_image.set_visible(False)
        self.pasted_image.set_file(None)
