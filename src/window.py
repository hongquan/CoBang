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

import os
from typing import TYPE_CHECKING, Self, cast

from logbook import Logger
from gi.repository import Adw, Gio, GLib, GObject, Gtk, NM, Xdp  # pyright: ignore[reportMissingModuleSource]
from gi.repository import XdpGtk4  # pyright: ignore[reportMissingModuleSource]

from .consts import (
    JobName,
    ScanSourceName,
    WebcamPageLayoutName,
    ENV_EMULATE_SANDBOX,
)
from .messages import IMAGE_GUIDE, WifiInfoMessage
from .pages.generator import GeneratorPage
from .pages.scanner import ScannerPage


log = Logger(__name__)


# This UI file is to be compiled from *.blp file.
@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/window.ui')
class CoBangWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'CoBangWindow'
    in_mobile_screen = GObject.Property(type=bool, default=False, nick='in-mobile-screen')

    job_viewstack: Adw.ViewStack = Gtk.Template.Child()
    toggle_scanner: Gtk.ToggleButton = Gtk.Template.Child()
    toggle_generator: Gtk.ToggleButton = Gtk.Template.Child()
    
    scanner_page: ScannerPage = Gtk.Template.Child()
    generator_page: GeneratorPage = Gtk.Template.Child()
    
    portal_parent: Xdp.Parent

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.portal_parent = XdpGtk4.parent_new_gtk(self)
        action = Gio.SimpleAction.new('paste-image', None)
        self.add_action(action)
        action.connect('activate', self.on_paste_image)
        
        # Connect signals from scanner page
        self.scanner_page.connect('request-camera-access', self.on_request_camera_access)
        self.scanner_page.connect('request-wifi-display', self.on_request_wifi_display)
        
        # Initialize NM.Client
        self.nm_client: NM.Client | None = None
        NM.Client.new_async(None, self.cb_networkmanager_client_init_done)

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

    # Ref: https://pygobject.gnome.org/guide/gtk_template.html
    @Gtk.Template.Callback()
    def on_job_viewstack_visible_child_changed(self, viewstack: Adw.ViewStack, *args):
        visible_child_name = viewstack.get_visible_child_name()
        if visible_child_name != JobName.SCANNER:
            self.scanner_page.stop_webcam()
            return
        if self.scanner_page.scan_source_viewstack.get_visible_child_name() == ScanSourceName.WEBCAM:
             if not self.scanner_page.gst_pipeline:
                 self.scanner_page.request_camera_access()
             elif not self.scanner_page.btn_pause.get_active():
                 self.scanner_page.play_webcam()

    @Gtk.Template.Callback()
    def in_scanner_mode(self, wd: Self, child_name: str) -> bool:
        # Note: self is of `Child` type, not `CoBangWindow`. It may change in the future version of PyGObject.
        return child_name == JobName.SCANNER

    @Gtk.Template.Callback()
    def switch_to_scanner(self, button: Gtk.ToggleButton):
        name = JobName.SCANNER if button.get_active() else JobName.GENERATOR
        self.job_viewstack.set_visible_child_name(name)

    @Gtk.Template.Callback()
    def on_shown(self, *args):
        scan_source = self.scanner_page.scan_source_viewstack.get_visible_child_name()
        log.info('Scan source: {}', scan_source)
        if scan_source == ScanSourceName.WEBCAM:
            self.scanner_page.request_camera_access()

    def cb_camera_access_request(self, portal: Xdp.Portal, result: Gio.AsyncResult):
        # When testing with Ghostty terminal, the app lost focus and the portal request is denied.
        try:
            success = portal.access_camera_finish(result)
        except GLib.Error as e:
            log.error('Failed to access camera: {}', e)
            return
        log.info('Allowed to access camera: {}', success)
        if not success:
            self.scanner_page.webcam_multilayout.set_layout_name(WebcamPageLayoutName.UNAVAILABLE)
            return
        # Ref: https://github.com/workbenchdev/demos/blob/main/src/Camera/main.py#L33
        video_fd = portal.open_pipewire_remote_for_camera()
        log.info('Pipewire remote fd: {}', video_fd)
        self.scanner_page.set_camera_pipewire_fd(video_fd)

    def request_camera_access(self):
        has_camera = self.portal.is_camera_present()
        log.info('Is webcam available: {}', has_camera)
        if not has_camera:
            self.scanner_page.webcam_multilayout.set_layout_name(WebcamPageLayoutName.UNAVAILABLE)
            return
        self.scanner_page.webcam_multilayout.set_layout_name(WebcamPageLayoutName.AVAILABLE)
        # Ref: https://lazka.github.io/pgi-docs/#Xdp-1.0/classes/Portal.html#Xdp.Portal.access_camera
        self.portal.access_camera(
            self.portal_parent,
            Xdp.CameraFlags.NONE,
            None,
            self.cb_camera_access_request,
        )

    def on_request_camera_access(self, scanner_page, *args):
        self.request_camera_access()
    
    def on_request_wifi_display(self, scanner_page, wifi: WifiInfoMessage, *args):
        """Handle WiFi display request from scanner page."""
        from .ui import build_wifi_info_display
        box = build_wifi_info_display(wifi, self.nm_client)
        self.scanner_page.set_wifi_display(box)

    def cb_networkmanager_client_init_done(self, client: NM.Client, res: Gio.AsyncResult):
        """Callback for NM.Client initialization."""
        if not client:
            log.error('Failed to initialize NetworkManager client')
            return
        client.new_finish(res)
        self.nm_client = client
        log.debug('NM client: {}', client)

    def on_paste_image(self, *args):
        self.scanner_page.on_paste_image(*args)

    def process_file_from_commandline(self, file: Gio.File, mime_type: str):
        self.job_viewstack.set_visible_child_name(JobName.SCANNER)
        self.scanner_page.scan_source_viewstack.set_visible_child_name(ScanSourceName.IMAGE)
        self.scanner_page.process_passed_image_file(file, mime_type)
