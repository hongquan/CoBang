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

from gi.repository import (  # pyright: ignore[reportMissingModuleSource]
    NM,
    Adw,
    Gio,
    GLib,
    GObject,
    Gtk,
    Xdp,
    XdpGtk4,
)  # pyright: ignore[reportMissingModuleSource]
from logbook import Logger

from .consts import (
    ENV_EMULATE_SANDBOX,
    JobName,
    ScanSourceName,
)
from .messages import WifiInfoMessage
from .net import add_wifi_connection, is_connected_same_wifi
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

    @GObject.Property(type=bool, default=False, nick='is-outside-sandbox')
    def is_outside_sandbox(self) -> bool:
        # This property may be accessed before application is set.
        if not self.get_application():
            return False
        return not self.portal.running_under_sandbox() and not os.getenv(ENV_EMULATE_SANDBOX)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.portal_parent = XdpGtk4.parent_new_gtk(self)
        action = Gio.SimpleAction.new('paste-image', None)
        self.add_action(action)
        action.connect('activate', self.on_paste_image)

        # Connect signals from scanner page
        self.scanner_page.connect('request-camera-access', self.on_camera_access_requested)
        self.scanner_page.connect('poll-wifi-connection-status', self.on_wifi_connection_status_polled)
        self.scanner_page.connect('request-connect-wifi', self.on_wifi_connecting_requested)

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

    @Gtk.Template.Callback()
    def on_job_viewstack_visible_child_changed(self, viewstack: Adw.ViewStack, *args):
        visible_child_name = viewstack.get_visible_child_name()
        self.scanner_page.update_webcam_activity(visible_child_name == JobName.SCANNER)

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

    def cb_camera_access_request_via_portal(self, portal: Xdp.Portal, result: Gio.AsyncResult):
        # When testing with Ghostty terminal, the app lost focus and the portal request is denied.
        try:
            success = portal.access_camera_finish(result)
        except GLib.Error as e:
            log.error('Failed to access camera: {}', e)
            return
        log.info('Allowed to access camera: {}', success)
        if not success:
            self.scanner_page.set_webcam_availability(False)
            return
        # Ref: https://github.com/workbenchdev/demos/blob/main/src/Camera/main.py#L33
        video_fd = portal.open_pipewire_remote_for_camera()
        log.info('Pipewire remote fd: {}', video_fd)
        self.scanner_page.setup_camera_for_sandbox(video_fd)

    def on_camera_access_requested(self, scanner_page, *args):
        has_camera = self.portal.is_camera_present()
        log.info('Is webcam available: {}', has_camera)
        self.scanner_page.set_webcam_availability(has_camera)
        if not has_camera:
            return
        # Ref: https://lazka.github.io/pgi-docs/#Xdp-1.0/classes/Portal.html#Xdp.Portal.access_camera
        self.portal.access_camera(
            self.portal_parent,
            Xdp.CameraFlags.NONE,
            None,
            self.cb_camera_access_request_via_portal,
        )

    def on_wifi_connection_status_polled(self, scanner_page: ScannerPage, wifi: WifiInfoMessage, *args):
        """Handle WiFi connection status polling from scanner page."""
        connected = False
        if self.nm_client:
            connected = is_connected_same_wifi(wifi.ssid, self.nm_client)
        log.info('WiFi SSID "{}" connected: {}', wifi.ssid, connected)
        wifi.connected = connected
        scanner_page.build_wifi_display(wifi)

    def on_wifi_connecting_requested(self, scanner_page: ScannerPage, wifi_info: WifiInfoMessage, *args):
        """Handle WiFi connection request from scanner page."""

        if not self.nm_client:
            log.error('No NM.Client available to connect to WiFi')
            return
        log.info('Requesting to connect to WiFi: {}', wifi_info)
        add_wifi_connection(wifi_info, self.cb_wifi_connect_done, self.nm_client)

    def cb_networkmanager_client_init_done(self, client: NM.Client, res: Gio.AsyncResult):
        """Callback for NM.Client initialization."""
        if not client:
            log.error('Failed to initialize NetworkManager client')
            return
        client.new_finish(res)
        self.nm_client = client
        log.debug('NM client: {}', client)

    def on_paste_image(self, *args):
        self.scanner_page.on_paste_image()

    def cb_wifi_connect_done(self, client: NM.Client, res: Gio.AsyncResult):
        """Callback for WiFi connection request."""
        created = client.add_connection_finish(res)
        log.debug('NetworkManager created connection: {}', created)
        self.scanner_page.display_wifi_as_connected(True)

    def activate_pause_button(self):
        """Activate the Pause button if ScannerPage is visible and in an appropriate stage."""
        if self.job_viewstack.get_visible_child() == self.scanner_page and self.scanner_page.is_scanning():
            self.scanner_page.activate_pause_button()

    def process_file_from_commandline(self, file: Gio.File, mime_type: str):
        self.scanner_page.process_commandline_file(file, mime_type)
