# scanner.py
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

import io
import os
import threading
from locale import gettext as _
from typing import Any, cast
from urllib.parse import SplitResult, urlsplit

import gi


gi.require_version('Gtk', '3.0')
gi.require_version('Handy', '1')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')

import zbar  # zuban: ignore[import-not-found]
from gi.repository import (
    Gdk,
    GdkPixbuf,
    Gio,
    GLib,
    GObject,
    Gst,
    GstApp,
    Gtk,
    Handy,
)
from logbook import Logger
from PIL import Image

from ..consts import (
    GST_APP_SINK_NAME,
    GST_FLIP_FILTER_NAME,
    GST_SINK_NAME,
    GST_SOURCE_NAME,
    DeviceSourceType,
    ScannerState,
    ScanSourceName,
    WebcamPageLayoutName,
)
from ..custom_types import WebcamDeviceInfo
from ..messages import WifiInfoMessage, parse_wifi_message
from ..prep import (
    get_device_path,
    guess_mimetype,
    invert_and_make_grayscale,
    is_image_almost_black_white,
    make_grayscale,
)
from ..ui import build_url_display, build_wifi_info_display


log = Logger(__name__)


def build_display_sink_desc() -> str:
    # On Wayland, GTK3 provides a proper GL context to gtkglsink, so glsinkbin
    # works for zero-copy GPU rendering. On X11, the wrapped GL context lacks the
    # gst_gl_context_fill_info() implementation, causing glsinkbin to stall after the
    # first frame. Probe the display server to choose the right path.
    display_server = os.getenv('XDG_SESSION_TYPE', '').lower()
    if display_server == 'wayland':
        return f'glsinkbin sink="gtkglsink name={GST_SINK_NAME}" name=sink_bin'
    # gtksink draws via Cairo into a plain GtkWidget: no GL context involved,
    # which avoids the GL stalls seen on X11.
    return f'videoconvert ! gtksink name={GST_SINK_NAME}'


# Maximum dimension of the preview GtkImage for the image source.
PASTED_IMAGE_MAX_SIZE = 720


@Gtk.Template.from_resource('/vn/quokka/CyperusCoi/gtk/scanner-page.ui')
class ScannerPage(Gtk.Bin):
    __gtype_name__ = 'ScannerPage'

    scanner_state = GObject.Property(type=int, default=0, nick='scanner-state')
    in_mobile_screen = GObject.Property(type=bool, default=False, nick='in-mobile-screen')
    is_outside_sandbox = GObject.Property(type=bool, default=False, nick='is-outside-sandbox')
    # Whether the webcam display box currently holds a video widget.
    has_webcam_frame = GObject.Property(type=bool, default=False, nick='has-webcam-frame')

    webcam_store: Gtk.ListStore = Gtk.Template.Child()
    file_filter: Gtk.FileFilter = Gtk.Template.Child()

    scanner_flap: Handy.Flap = Gtk.Template.Child()
    toolbarview_scanner: Gtk.Box = Gtk.Template.Child()
    scan_source_viewstack: Gtk.Stack = Gtk.Template.Child()
    webcam_multilayout: Gtk.Stack = Gtk.Template.Child()
    image_webcam_searching: Gtk.Image = Gtk.Template.Child()
    webcam_unavailable_page: Handy.StatusPage = Gtk.Template.Child()
    image_webcam_placeholder: Gtk.Image = Gtk.Template.Child()
    webcam_overlay: Gtk.Overlay = Gtk.Template.Child()
    webcam_display: Gtk.Box = Gtk.Template.Child()
    box_playpause: Gtk.Box = Gtk.Template.Child()
    btn_play: Gtk.ToggleButton = Gtk.Template.Child()
    btn_pause: Gtk.ToggleButton = Gtk.Template.Child()
    box_webcam_settings: Gtk.Box = Gtk.Template.Child()
    label_sandboxed_webcam: Gtk.Label = Gtk.Template.Child()
    box_webcam_selector: Gtk.Box = Gtk.Template.Child()
    label_webcam_selector: Gtk.Label = Gtk.Template.Child()
    webcam_dropdown: Gtk.ComboBox = Gtk.Template.Child()
    box_mirror: Gtk.Box = Gtk.Template.Child()
    mirror_switch: Gtk.Switch = Gtk.Template.Child()
    frame_image: Gtk.Frame = Gtk.Template.Child()

    pasted_image: Gtk.Image = Gtk.Template.Child()
    box_image_hint: Gtk.Box = Gtk.Template.Child()
    image_wireframe: Gtk.Image = Gtk.Template.Child()
    image_filechooser: Gtk.Image = Gtk.Template.Child()
    btn_filechooser: Gtk.Button = Gtk.Template.Child()
    label_chosen_file: Gtk.Label = Gtk.Template.Child()
    btn_show_result: Gtk.Button = Gtk.Template.Child()
    result_display_frame: Gtk.Frame = Gtk.Template.Child()
    label_idle: Gtk.Label = Gtk.Template.Child()
    box_scanning: Gtk.Box = Gtk.Template.Child()
    label_no_result: Gtk.Label = Gtk.Template.Child()
    label_result_title: Gtk.Label = Gtk.Template.Child()
    result_bin: Gtk.Box = Gtk.Template.Child()
    image_scanning: Gtk.Image = Gtk.Template.Child()
    raw_result_display: Gtk.TextView = Gtk.Template.Child()
    raw_result_expander: Gtk.Expander = Gtk.Template.Child()

    gst_pipeline: Gst.Pipeline | None = None
    dev_monitor: Gst.DeviceMonitor | None = None
    # Because the `on_new_webcam_sample` callback is run in a GStreamer
    # thread, which may be started when the Python interpreter has been destroyed,
    # we use this event to short-circuit those threads when the app is about to quit.
    shuttingdown: threading.Event

    # The Gio.File of the last image passed via file chooser, clipboard or DnD.
    pasted_file: Gio.File | None = None
    # Reference to keep the native file chooser alive while it is open.
    _file_chooser: Gtk.FileChooserNative | None = None
    # Guards for mirrored toggle buttons and state switches.
    _syncing_playpause: bool = False

    signal_request_camera_access = GObject.Signal(
        'request-camera-access',
        flags=GObject.SignalFlags.RUN_LAST,
    )
    poll_wifi_connection_status = GObject.Signal(
        'poll-wifi-connection-status',
        flags=GObject.SignalFlags.RUN_LAST,
        arg_types=(object,),
    )
    request_connect_wifi = GObject.Signal(
        'request-connect-wifi',
        flags=GObject.SignalFlags.RUN_LAST,
        arg_types=(object,),
    )

    # GtkListStore columns for the webcam device chooser.
    WEBCAM_COL_NAME = 0
    WEBCAM_COL_DEVICE = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.shuttingdown = threading.Event()

        self.webcam_multilayout.set_visible_child_name(WebcamPageLayoutName.REQUESTING)

        # Bindings which were done in the Blueprint UI file.
        self.bind_property(
            'has-webcam-frame',
            self.image_webcam_placeholder,
            'visible',
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN,
        )
        self.bind_property(
            'has-webcam-frame',
            self.webcam_overlay,
            'visible',
            GObject.BindingFlags.SYNC_CREATE,
        )
        self.bind_property(
            'has-webcam-frame',
            self.box_mirror,
            'visible',
            GObject.BindingFlags.SYNC_CREATE,
        )
        self.bind_property(
            'is-outside-sandbox',
            self.label_sandboxed_webcam,
            'visible',
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN,
        )
        self.bind_property(
            'is-outside-sandbox',
            self.box_webcam_selector,
            'visible',
            GObject.BindingFlags.SYNC_CREATE,
        )
        self.pasted_image.bind_property(
            'visible',
            self.box_image_hint,
            'visible',
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN,
        )

        self.connect('notify::in-mobile-screen', self.on_in_mobile_screen_changed)
        self.connect('notify::scanner-state', self.on_scanner_state_changed)

        # Drag & drop on the image frame (the DropTargetAsync builder object
        # has no GTK3 counterpart).
        self.frame_image.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [Gtk.TargetEntry.new('text/uri-list', 0, 0)],
            Gdk.DragAction.COPY,
        )
        self.frame_image.connect('drag-data-received', self.on_drag_data_received)

        # GTK3 builder has no `accessibility` construct: set the Atk names manually.
        for widget, name in (
            (self.image_webcam_searching, 'Find'),
            (self.image_webcam_placeholder, 'Webcam'),
            (self.image_wireframe, 'Add here'),
            (self.image_filechooser, 'Open'),
            (self.image_scanning, 'Scanning'),
        ):
            widget.get_accessible().set_name(name)

        self.on_in_mobile_screen_changed()
        self.on_scanner_state_changed()

        # Initialize zbar scanner
        self.zbar_scanner = zbar.ImageScanner()

    @property
    def is_at_scanning(self) -> bool:
        """Check if the scanner is currently scanning."""
        return self.scanner_state == ScannerState.SCANNING

    def switch_to_webcam_source(self):
        """Switch to webcam source view"""
        self.scan_source_viewstack.set_visible_child_name(ScanSourceName.WEBCAM)

    def switch_to_image_source(self):
        """Switch to image source view"""
        self.scan_source_viewstack.set_visible_child_name(ScanSourceName.IMAGE)

    def open_file_chooser_dialog(self, parent_window: Gtk.Window):
        """Open file chooser dialog to select an image file"""
        dlg = Gtk.FileChooserNative.new(
            _('Choose an image'),
            parent_window,
            Gtk.FileChooserAction.OPEN,
            _('_Open'),
            _('_Cancel'),
        )
        dlg.set_filter(self.file_filter)
        dlg.set_modal(True)
        dlg.connect('response', self.on_file_chooser_response)
        # Native dialogs need a Python reference to survive until the response.
        self._file_chooser = dlg
        dlg.show()

    def on_file_chooser_response(self, dialog: Gtk.FileChooserNative, response: int):
        self._file_chooser = None
        if response != Gtk.ResponseType.ACCEPT:
            return
        file = dialog.get_file()
        if not file:
            log.info('No file chosen.')
            return
        mime_type = guess_mimetype(file)
        log.info('MIME type: {}', mime_type)
        if not mime_type or not mime_type.startswith('image/'):
            log.info('Not an image. Ignore.')
            return
        self.process_passed_image_file(file, mime_type)

    def process_commandline_file(self, file: Gio.File, mime_type: str):
        """Process a file passed from command line arguments"""
        self.switch_to_image_source()
        self.process_passed_image_file(file, mime_type)

    def setup_camera_for_sandbox(self, video_fd: int):
        """Setup camera pipeline for sandboxed environments (e.g., Flatpak)"""
        pipeline = self.build_gstreamer_pipeline_in_sandbox(video_fd)
        if not pipeline:
            return
        self.attach_gstreamer_sink_to_window(pipeline)
        if not self.btn_pause.get_active():
            self.play_webcam()
            self.scanner_state = ScannerState.SCANNING
        self.enable_webcam_consumption(pipeline)

    def set_webcam_availability(self, available: bool):
        """Set webcam availability status"""
        layout = WebcamPageLayoutName.AVAILABLE if available else WebcamPageLayoutName.UNAVAILABLE
        self.webcam_multilayout.set_visible_child_name(layout)

    @Gtk.Template.Callback()
    def on_scan_source_viewstack_visible_child_changed(self, viewstack: Gtk.Stack, *args):
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

    def on_in_mobile_screen_changed(self, *args):
        """Reconfigure the result Flap and dependent boxes for the new layout.

        Replaces the Adw.MultiLayoutView layout switching: on desktop the flap
        is a permanently visible side panel, on mobile it behaves like a
        bottom sheet.
        """
        flap = self.scanner_flap
        if self.in_mobile_screen:
            flap.set_orientation(Gtk.Orientation.VERTICAL)
            flap.set_flap_position(Gtk.PackType.END)
            flap.set_fold_policy(Handy.FlapFoldPolicy.ALWAYS)
            flap.set_modal(True)
            flap.set_swipe_to_open(True)
            flap.set_swipe_to_close(True)
            flap.set_reveal_flap(True)
            self.toolbarview_scanner.set_hexpand(False)
            self.box_webcam_settings.set_orientation(Gtk.Orientation.VERTICAL)
            self.box_webcam_selector.set_halign(Gtk.Align.FILL)
            self.box_webcam_selector.set_hexpand(False)
            self.label_webcam_selector.set_hexpand(True)
            self.box_mirror.set_halign(Gtk.Align.FILL)
            self.box_mirror.set_valign(Gtk.Align.CENTER)
        else:
            flap.set_orientation(Gtk.Orientation.HORIZONTAL)
            flap.set_flap_position(Gtk.PackType.END)
            flap.set_fold_policy(Handy.FlapFoldPolicy.NEVER)
            flap.set_modal(False)
            flap.set_swipe_to_open(False)
            flap.set_swipe_to_close(False)
            flap.set_reveal_flap(True)
            self.toolbarview_scanner.set_hexpand(True)
            self.box_webcam_settings.set_orientation(Gtk.Orientation.HORIZONTAL)
            self.box_webcam_selector.set_halign(Gtk.Align.START)
            self.box_webcam_selector.set_hexpand(True)
            self.label_webcam_selector.set_hexpand(False)
            self.box_mirror.set_halign(Gtk.Align.END)
            self.box_mirror.set_valign(Gtk.Align.CENTER)
        self.update_show_result_button()

    def on_scanner_state_changed(self, *args):
        """Update the result panel widgets for the new scanner state.

        Replaces the $is_idle / $is_scanning / $is_no_result /
        $has_scanning_result / $scanning_result_title builder closures.
        """
        state = self.scanner_state
        self.label_idle.set_visible(state == ScannerState.IDLE)
        self.box_scanning.set_visible(state == ScannerState.SCANNING)
        self.label_no_result.set_visible(state == ScannerState.NO_RESULT)
        has_result = state > ScannerState.NO_RESULT
        self.label_result_title.set_visible(has_result)
        self.result_bin.set_visible(has_result)
        if has_result:
            self.label_result_title.set_text(self.scanning_result_title_text(state))
        self.update_show_result_button()

    def scanning_result_title_text(self, state: int) -> str:
        if state == ScannerState.WIFI_FOUND:
            return _('Found a wifi configuration')
        if state == ScannerState.URL_FOUND:
            return _('Found a URL. Click to open:')
        if state == ScannerState.TEXT_FOUND:
            return _('Found unrecognized text.')
        return _('Unknown')

    def update_show_result_button(self):
        """The 'Show result' button only makes sense in mobile (bottom sheet) mode."""
        has_result = self.scanner_state > ScannerState.NO_RESULT
        self.btn_show_result.set_visible(self.in_mobile_screen and has_result)

    @Gtk.Template.Callback()
    def on_mirror_switch_toggled(self, switch: Gtk.Switch, state: bool) -> bool:
        if not self.gst_pipeline:
            # Revert the state
            return True
        GLib.idle_add(self.flip_video, self.gst_pipeline, state)
        return False

    def activate_pause_button(self):
        """Activate the Pause button."""
        self.btn_pause.set_active(True)

    @Gtk.Template.Callback()
    def on_btn_play_toggled(self, button: Gtk.ToggleButton):
        if self._syncing_playpause:
            return
        self._syncing_playpause = True
        self.btn_pause.set_active(not button.get_active())
        self._syncing_playpause = False
        self.apply_play_pause(playing=button.get_active())

    @Gtk.Template.Callback()
    def on_btn_pause_toggled(self, button: Gtk.ToggleButton):
        if self._syncing_playpause:
            return
        playing = not button.get_active()
        self._syncing_playpause = True
        self.btn_play.set_active(playing)
        self._syncing_playpause = False
        self.apply_play_pause(playing=playing)

    def apply_play_pause(self, playing: bool):
        self.scanner_state = ScannerState.SCANNING if playing else ScannerState.IDLE
        if not self.gst_pipeline:
            return
        if not playing:
            if app_sink := cast(GstApp.AppSink | None, self.gst_pipeline.get_by_name(GST_APP_SINK_NAME)):
                app_sink.set_emit_signals(False)
            if source := self.gst_pipeline.get_by_name(GST_SOURCE_NAME):
                source.set_state(Gst.State.PAUSED)
            return
        # There is an issue with pipewiresrc when changing from PAUSED to PLAYING: an error is thrown:
        # "gst_caps_intersect_full: assertion 'GST_IS_CAPS (caps2)' failed".
        # So we stop the video and play again.
        source = self.gst_pipeline.get_by_name(GST_SOURCE_NAME)
        if source and source.__class__.__name__ == 'GstPipeWireSrc':
            self.stop_webcam()
        self.play_webcam()
        if app_sink := cast(GstApp.AppSink | None, self.gst_pipeline.get_by_name(GST_APP_SINK_NAME)):
            app_sink.set_emit_signals(True)

    @Gtk.Template.Callback()
    def on_btn_show_result_clicked(self, button: Gtk.Button):
        self.scanner_flap.set_reveal_flap(True)

    @Gtk.Template.Callback()
    def on_btn_copy_clicked(self, button: Gtk.Button):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        buffer = self.raw_result_display.get_buffer()
        buffer.select_range(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.copy_clipboard(clipboard)
        button.set_tooltip_text(_('Copied!'))
        GLib.timeout_add_seconds(3, lambda: button.set_tooltip_text(None))

    @Gtk.Template.Callback()
    def on_btn_filechooser_clicked(self, button: Gtk.Button):
        # We need a window for the dialog.
        if not isinstance(win := self.get_root(), Gtk.Window):
            log.warning('Root is not a window')
            return

        self.open_file_chooser_dialog(win)

    @Gtk.Template.Callback()
    def on_webcam_device_selected(self, combo: Gtk.ComboBox):
        model = combo.get_model()
        active = combo.get_active()
        if not model or active < 0:
            return
        device_info = model.get_value(model.get_iter((active,)), self.WEBCAM_COL_DEVICE)
        if not isinstance(device_info, WebcamDeviceInfo):
            return
        log.info('Selected device: {}', device_info)
        if self.scan_source_viewstack.get_visible_child_name() != ScanSourceName.WEBCAM:
            return
        # Destroy the old pipeline if any.
        if self.gst_pipeline:
            self.gst_pipeline.set_state(Gst.State.NULL)
            self.detach_gstreamer_sink()
            self.gst_pipeline = None
        # Build a new pipeline.
        pipeline = self.build_gstreamer_pipeline(device_info.source_type, device_info.path)
        if not pipeline:
            return
        self.attach_gstreamer_sink_to_window(pipeline)
        # Let GTK prepare the UI fully for painting video. Without this, the video from pipewiresrc may not be displayed.
        if device_info.source_type == DeviceSourceType.PIPEWIRE:
            GLib.idle_add(self.play_webcam_and_enable_consumption, pipeline)
        else:
            self.play_webcam_and_enable_consumption(pipeline)

    def on_drag_data_received(
        self,
        widget: Gtk.Widget,
        drag_context: Gdk.DragContext,
        x: int,
        y: int,
        data: Gtk.SelectionData,
        info: int,
        time: int,
    ):
        uris = data.get_uris()
        if not uris:
            Gtk.drag_finish(drag_context, False, False, time)
            return
        file = Gio.File.new_for_uri(uris[0])
        Gtk.drag_finish(drag_context, True, False, time)
        mime_type = guess_mimetype(file)
        log.info('MIME type: {}', mime_type)
        if not mime_type or not mime_type.startswith('image/'):
            log.info('Not an image. Ignore.')
            return
        self.process_passed_image_file(file, mime_type)

    def request_camera_access(self):
        """Request camera access - emits signal for sandboxed, discovers devices otherwise."""
        log.info('Is outside sandbox: {}', self.get_property('is-outside-sandbox'))
        if self.is_outside_sandbox:
            self.discover_webcam()
        else:
            self.signal_request_camera_access.emit()

    def discover_webcam(self):
        """Discover webcam devices using GStreamer device monitor."""
        # Initialize device monitor if not already done
        if not self.dev_monitor:
            self.dev_monitor = Gst.DeviceMonitor.new()
            self.dev_monitor.add_filter('Video/Source', Gst.Caps.from_string('video/x-raw'))
            log.debug('Device monitor: {}', self.dev_monitor)

        devices = self.dev_monitor.get_devices() or []
        for d in devices:
            log.debug('Found device {}', d.get_path_string())
            device_path, src_type = get_device_path(d)
            device_name = d.get_display_name()
            if not device_name or not device_path:
                log.info('Unsupported device: {}', d.get_path_string())
                continue
            self.webcam_store.append(
                (device_name, WebcamDeviceInfo(source_type=src_type, path=device_path, name=device_name))
            )
            log.debug(
                'Added {} ({}) to webcam_store. Total items: {}',
                src_type,
                device_path,
                self.webcam_store.iter_n_children(None),
            )
        # If found any device, set the first one as selected.
        if self.webcam_store.get_iter_first():
            self.webcam_multilayout.set_visible_child_name(WebcamPageLayoutName.AVAILABLE)
            self.webcam_dropdown.set_active(0)
        # Continue to monitor for new devices.
        bus = self.dev_monitor.get_bus()
        bus.add_watch(GLib.PRIORITY_DEFAULT, self.on_device_monitor_message, None)
        log.debug('Start device monitoring...')
        self.dev_monitor.start()

    def build_gstreamer_pipeline_in_sandbox(self, video_fd: int) -> Gst.Pipeline | None:
        flip_method = 'horizontal-flip' if self.mirror_switch.get_active() else 'none'
        # leaky=2 on the display queue prevents a stalled GL sink from back-pressuring the tee
        # and blocking the scan branch.
        # In `appsink`, the `leaky-type` property is introduced in GStreamer 1.28 but
        # somehow is not unrecognized in Ubuntu 26.04,
        # so we still need to use the old `drop`.
        cmd = (
            f'pipewiresrc name={GST_SOURCE_NAME} fd={video_fd} ! '
            f'videoflip name={GST_FLIP_FILTER_NAME} method={flip_method} ! videoconvert ! tee name=t ! '
            f'queue leaky=2 ! videoscale ! {build_display_sink_desc()} '
            't. ! queue leaky=2 max-size-buffers=2 ! videoconvert ! video/x-raw,format=GRAY8 ! '
            f'appsink name={GST_APP_SINK_NAME} max_buffers=2 drop=1 leaky-type=2'
        )
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

    def build_gstreamer_pipeline(self, src_type: DeviceSourceType, video_path: str) -> Gst.Pipeline | None:
        """Build GStreamer Pipeline to access webcam directly (via V4L2), when running outside sandbox."""
        flip_method = 'horizontal-flip' if self.mirror_switch.get_active() else 'none'
        source_desc_parts = (
            src_type,
            f'name={GST_SOURCE_NAME} ',
            f'device={video_path}' if src_type == DeviceSourceType.V4L2 else f'target-object={video_path}',
        )
        source_desc = ' '.join(source_desc_parts)
        # leaky=2 on the display queue prevents a stalled GL sink from back-pressuring the tee
        # and blocking the scan branch.
        # In `appsink`, the `leaky-type` property is introduced in GStreamer 1.28 but
        # somehow is not unrecognized in Ubuntu 26.04,
        # so we still need to use the old `drop`.
        cmd = (
            f'{source_desc} ! videoflip name={GST_FLIP_FILTER_NAME} method={flip_method} ! videoconvert ! tee name=t ! '
            f'queue leaky=2 ! videoscale ! {build_display_sink_desc()} '
            't. ! queue leaky=2 max-size-buffers=2 ! videoconvert ! video/x-raw,format=GRAY8 ! '
            f'appsink name={GST_APP_SINK_NAME} max_buffers=2 drop=1 leaky-type=2'
        )
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
        sink = pipeline.get_by_name(GST_SINK_NAME)
        if not sink:
            # When glsinkbin wraps gtkglsink, the inner element's name is not
            # discoverable via get_by_name() — retrieve it via the bin's "sink" property.
            if sink_bin := pipeline.get_by_name('sink_bin'):
                sink = sink_bin.get_property('sink')
        if not sink:
            log.error('Failed to get the gtksink/gtkglsink element')
            return
        log.info('Sink element: {}', sink)
        # gtksink / gtkglsink expose the rendering GtkWidget instead of a paintable.
        widget = sink.get_property('widget')
        if not widget:
            log.error('The sink element has no widget to display')
            return
        self.clear_webcam_display()
        self.webcam_display.pack_start(widget, True, True, 0)
        widget.show_all()
        self.has_webcam_frame = True
        self.gst_pipeline = pipeline

    def detach_gstreamer_sink(self):
        self.clear_webcam_display()
        self.has_webcam_frame = False

    def clear_webcam_display(self):
        for child in self.webcam_display.get_children():
            self.webcam_display.remove(child)
            child.destroy()

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
        if app_sink := cast(GstApp.AppSink | None, pipeline.get_by_name(GST_APP_SINK_NAME)):
            log.debug('Appsink: {}', app_sink)
            app_sink.set_emit_signals(True)
            app_sink.connect('new-sample', self.on_new_webcam_sample)
        else:
            log.warning('Appsink not found in pipeline')

    def disable_webcam_consumption(self, pipeline: Gst.Pipeline):
        if app_sink := cast(GstApp.AppSink | None, pipeline.get_by_name(GST_APP_SINK_NAME)):
            log.debug('Appsink: {}', app_sink)
            app_sink.set_emit_signals(False)
            app_sink.disconnect_by_func(self.on_new_webcam_sample)
        else:
            log.warning('Appsink not found in pipeline')

    def teardown_webcam(self):
        """Synchronously stop the webcam and disconnect its sample callback.

        Safe to call on shutdown: after this returns, no `on_new_webcam_sample`
        callback can be running or be invoked again.
        """
        if not self.gst_pipeline:
            return
        self.disable_webcam_consumption(self.gst_pipeline)
        # Setting NULL blocks until the streaming threads have been joined,
        # guaranteeing no in-flight appsink callback remains.
        self.gst_pipeline.set_state(Gst.State.NULL)
        self.detach_gstreamer_sink()
        self.gst_pipeline = None

    def play_webcam_and_enable_consumption(self, gst_pipeline: Gst.Pipeline):
        if not self.btn_pause.get_active():
            self.play_webcam()
            self.scanner_state = ScannerState.SCANNING
        self.enable_webcam_consumption(gst_pipeline)

    def update_webcam_activity(self, is_visible: bool):
        if not is_visible:
            self.stop_webcam()
            return

        if self.scan_source_viewstack.get_visible_child_name() != ScanSourceName.WEBCAM:
            return

        if not self.gst_pipeline:
            self.request_camera_access()
        elif not self.btn_pause.get_active():
            self.play_webcam()

    def flip_video(self, pipeline: Gst.Pipeline, mirror: bool):
        if source := pipeline.get_by_name(GST_SOURCE_NAME):
            source.set_state(Gst.State.NULL)
        pipeline.set_state(Gst.State.NULL)
        if flip_filter := pipeline.get_by_name(GST_FLIP_FILTER_NAME):
            # Ref: https://gstreamer.freedesktop.org/documentation/videofilter/videoflip.html?gi-language=c#named-constants
            new_method = 'horizontal-flip' if mirror else 'none'
            flip_filter.set_property('method', new_method)
        if self.btn_pause.get_active():
            pipeline.set_state(Gst.State.PAUSED)
        else:
            pipeline.set_state(Gst.State.PLAYING)

    def on_new_webcam_sample(self, appsink: GstApp.AppSink) -> Gst.FlowReturn:
        if self.shuttingdown.is_set():
            return Gst.FlowReturn.FLUSHING
        if appsink.is_eos():
            return Gst.FlowReturn.OK
        if not (sample := cast(Gst.Sample | None, appsink.try_pull_sample(1))):
            return Gst.FlowReturn.OK
        if not (buffer := sample.get_buffer()):
            return Gst.FlowReturn.OK
        if not (caps := sample.get_caps()):
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
        # The `buffer.map` API has been changed between python3-gst v1.26 and v1.28.
        # Some runtimes (e.g. GNOME 51) ship GStreamer 1.28 C libraries but older
        # Python overrides, so we detect the return shape at runtime instead of
        # relying solely on Gst.VERSION_MINOR.
        mapped = buffer.map(Gst.MapFlags.READ)
        if isinstance(mapped, tuple):
            success, mapinfo = cast(tuple[bool, Gst.MapInfo], mapped)
            if not success:
                log.error('Failed to get mapinfo from Gst AppSink.')
                return Gst.FlowReturn.ERROR
        else:
            mapinfo = cast(Gst.MapInfo, mapped)
        # The documentation https://lazka.github.io/pgi-docs/#Gst-1.0/classes/MapInfo.html says that
        # the .data is a bytes, but in Ubuntu, it is a memoryview.
        image_data = mapinfo.data.tobytes() if isinstance(mapinfo.data, memoryview) else mapinfo.data
        if not image_data:
            log.debug('Empty data from MapInfo')
            return Gst.FlowReturn.OK
        GLib.idle_add(self.decode_from_video_sample, image_data, width, height)
        buffer.unmap(mapinfo)
        return Gst.FlowReturn.OK

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
            found = self.find_store_position(cam_path) is not None
            if not found:
                self.webcam_store.append(
                    (cam_name, WebcamDeviceInfo(source_type=src_type, path=cam_path, name=cam_name))
                )
                log.debug('{} was not in the store. Added.', cam_path)
            return True
        elif message.type == Gst.MessageType.DEVICE_REMOVED:
            removed_dev = message.parse_device_removed()
            log.debug('Removed: {}', removed_dev)
            cam_path, src_type = get_device_path(removed_dev)
            if not cam_path or src_type not in DeviceSourceType:
                log.info('Unsupported device: {} {}', src_type, removed_dev.get_path_string())
                return True
            if self.gst_pipeline and (ppl_source := self.gst_pipeline.get_by_name(GST_SOURCE_NAME)):
                if cam_path == ppl_source.get_property('device') or cam_path == ppl_source.get_property(
                    'target-object'
                ):
                    self.gst_pipeline.set_state(Gst.State.NULL)
            # Find the entry of just-removed in the list and remove it.
            pos = self.find_store_position(cam_path)
            if pos is not None:
                log.debug('To remove {} from list', cam_path)
                self.webcam_store.remove(self.webcam_store.iter_nth_child(None, pos))
        return True

    def find_store_position(self, cam_path: str) -> int | None:
        """Return the row index of the given webcam device path, or None."""
        model = self.webcam_store
        itr = model.get_iter_first()
        pos = 0
        while itr is not None:
            device_info = model.get_value(itr, self.WEBCAM_COL_DEVICE)
            if isinstance(device_info, WebcamDeviceInfo) and device_info.path == cam_path:
                return pos
            itr = model.iter_next(itr)
            pos += 1
        return None

    def receive_pasted_image(self, *args):
        # Prefer the asynchronous request_* clipboard API (GTK3 clipboard
        # "wait_*" probes are synchronous and can stall the UI).
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        log.debug('Clipboard: {}', clipboard)
        clipboard.request_image(self.cb_image_read_from_clipboard)

    def cb_image_read_from_clipboard(self, clipboard: Gtk.Clipboard, pixbuf: GdkPixbuf.Pixbuf | None):
        if pixbuf is not None:
            log.info('Got image from clipboard: {}x{}', pixbuf.get_width(), pixbuf.get_height())
            self.display_pasted_pixbuf(pixbuf)
            self.decode_from_pixbuf(pixbuf)
            return
        log.debug('No image in clipboard, trying URIs')
        clipboard.request_uris(self.cb_uris_read_from_clipboard)

    def cb_uris_read_from_clipboard(self, clipboard: Gtk.Clipboard, uris: list[str] | None):
        if not uris:
            log.debug('No URI in clipboard')
            return
        file = Gio.File.new_for_uri(uris[0])
        mime_type = guess_mimetype(file)
        log.info('MIME type: {}', mime_type)
        if not mime_type or not mime_type.startswith('image/'):
            log.info('Not an image. Ignore.')
            return
        self.process_passed_image_file(file, mime_type)

    def process_passed_image_file(self, chosen_file: Gio.File, content_type: str):
        self.reset_result()
        pixbuf = self.load_pixbuf_from_file(chosen_file)
        if not pixbuf:
            log.debug('No image data. Ignore.')
            return
        self.pasted_file = chosen_file
        self.display_pasted_pixbuf(pixbuf)
        self.decode_from_pixbuf(pixbuf)

    def display_pasted_pixbuf(self, pixbuf: GdkPixbuf.Pixbuf):
        """Scale (if needed) and show the image in the pasted_image GtkImage."""
        self.pasted_image.set_from_pixbuf(scale_pixbuf_to_fit(pixbuf, PASTED_IMAGE_MAX_SIZE))
        self.pasted_image.set_visible(True)
        basename = self.pasted_file.get_basename() if self.pasted_file else ''
        self.label_chosen_file.set_text(basename or '')
        self.label_chosen_file.set_visible(bool(basename))

    def load_pixbuf_from_file(self, file: Gio.File) -> GdkPixbuf.Pixbuf | None:
        """Load a GdkPixbuf from a local or remote Gio.File."""
        try:
            stream = file.read(None)
        except GLib.Error as e:
            log.error('Failed to read file {}: {}', file.get_uri(), e)
            return None
        try:
            return GdkPixbuf.Pixbuf.new_from_stream(stream, None)
        except GLib.Error as e:
            log.error('Failed to load image {}: {}', file.get_uri(), e)
            return None
        finally:
            try:
                stream.close()
            except GLib.Error:
                pass

    def decode_from_video_sample(self, image_data: bytes, width: int, height: int):
        img = zbar.Image(width, height, 'Y800', image_data)
        n = self.zbar_scanner.scan(img)
        log.info('Scanned {} symbols', n)
        if not n:
            return
        # Found QR code in webcam screenshot
        # Pause video to prevent further processing.
        self.btn_pause.set_active(True)
        GLib.idle_add(self.display_result, img.symbols)

    def decode_from_pixbuf(self, pixbuf: GdkPixbuf.Pixbuf):
        w = pixbuf.get_width()
        h = pixbuf.get_height()
        log.info('Pixbuf size: {}x{}', w, h)
        success, img_bytes = pixbuf.save_to_bufferv('png', [], [])
        if not success or not img_bytes:
            log.debug('No image data in pixbuf. Ignore.')
            return
        img_file = io.BytesIO(img_bytes)
        rgba_img = Image.open(img_file)
        # ZBar needs grayscale image, the GdkPixbuf is RGB/RGBA,
        # we need to convert it to grayscale, replacing transparency with white.
        # Because the source image can have alpha channel, we need to convert it to LA.
        grayscale = make_grayscale(rgba_img, w, h)
        zimg = zbar.Image(w, h, 'Y800', grayscale.tobytes())
        n = self.zbar_scanner.scan(zimg)
        log.debug('Any QR code?: {}', n)
        if not n and is_image_almost_black_white(rgba_img):
            # Invert and try again
            grayscale = invert_and_make_grayscale(rgba_img, w, h)
            zimg = zbar.Image(w, h, 'Y800', grayscale.tobytes())
            n = self.zbar_scanner.scan(zimg)
        if not n:
            log.info('No QR code found in image.')
            self.scanner_state = ScannerState.NO_RESULT
            return
        GLib.idle_add(self.display_result, zimg.symbols)

    def display_result(self, symbols: zbar.SymbolSet):
        # There can be more than one QR code in the image. We just pick the first.
        # No need to handle StopIteration exception, because this function is called
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
                self.scanner_flap.set_reveal_flap(True)
                return
        except ValueError:
            pass
        if wifi := parse_wifi_message(raw_data):
            log.info('Parsed wifi message: {}', wifi)
            self.poll_wifi_connection_status.emit(wifi)
            self.scanner_state = ScannerState.WIFI_FOUND
            self.scanner_flap.set_reveal_flap(True)
            return
        # Non-welknown QR code. Just display the raw data.
        log.info('Unknown QR code. Display raw data.')
        self.scanner_state = ScannerState.TEXT_FOUND
        self.raw_result_expander.set_expanded(True)
        self.scanner_flap.set_reveal_flap(True)

    def set_result_child(self, widget: Gtk.Widget | None):
        """Set (or clear) the child of the result bin (a GtkBox in GTK3)."""
        for child in self.result_bin.get_children():
            self.result_bin.remove(child)
        if widget is not None:
            self.result_bin.add(widget)
            widget.show_all()

    def build_wifi_display(self, wifi: WifiInfoMessage):
        match build_wifi_info_display(wifi):
            case (box, btn_connect):
                btn_connect.connect('clicked', self.on_wifi_connect_button_clicked, wifi)
                self.set_result_child(box)
        return None

    def display_url(self, url: SplitResult):
        log.debug('Displaying URL: {}', url)
        box = build_url_display(url)
        self.set_result_child(box)
        self.scanner_state = ScannerState.URL_FOUND

    def reset_result(self):
        log.info('Reset result display')
        self.scanner_state = ScannerState.IDLE
        buffer = self.raw_result_display.get_buffer()
        buffer.set_text('')
        self.set_result_child(None)
        self.pasted_image.set_visible(False)
        self.pasted_image.clear()
        self.pasted_file = None
        self.label_chosen_file.set_visible(False)

    def on_wifi_connect_button_clicked(self, button: Gtk.Button, wifi_info: WifiInfoMessage):
        log.info('Connect button clicked for wifi: {}', wifi_info)
        self.request_connect_wifi.emit(wifi_info)

    def display_wifi_as_saved(self):
        """Set the current wifi connection status as saved."""
        # GTK3 has no Widget.get_first_child()/get_next_sibling(); walk the
        # result subtree breadth-first to find the connect button.
        widgets = list(self.result_bin.get_children())
        while widgets:
            widget = widgets.pop(0)
            if isinstance(widget, Gtk.Button):
                widget.set_sensitive(False)
                widget.set_label(_('Saved'))
                return
            if hasattr(widget, 'get_children'):
                widgets.extend(widget.get_children())
        log.warning('Not able to find connect button in wifi display box')


def scale_pixbuf_to_fit(pixbuf: GdkPixbuf.Pixbuf, max_size: int) -> GdkPixbuf.Pixbuf:
    """Scale a pixbuf down (keeping the aspect ratio) if it exceeds max_size.

    GTK3 GtkImage does not scale its pixbuf to the widget allocation like
    GTK4 GtkPicture does, so we scale explicitly for display.
    """
    width = pixbuf.get_width()
    height = pixbuf.get_height()
    longest = max(width, height)
    if longest <= max_size:
        return pixbuf
    scale = max_size / longest
    return pixbuf.scale_simple(round(width * scale), round(height * scale), GdkPixbuf.InterpType.BILINEAR)
