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

from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

import gi


gi.require_version('Gtk', '3.0')
gi.require_version('Handy', '1')
gi.require_version('NM', '1.0')
gi.require_version('Xdp', '1.0')
gi.require_version('XdpGtk3', '1.0')

from gi.repository import (
    NM,
    Gdk,
    Gio,
    GLib,
    GObject,
    Gtk,
    Handy,
    Xdp,
    XdpGtk3,
)
from logbook import Logger

from .consts import (
    ENV_EMULATE_SANDBOX,
    JobName,
    ScanSourceName,
)
from .messages import WifiInfoMessage
from .net import (
    DummyAgent,
    WiFiSaver,
    WifiSecretsRetriever,
    get_saved_wifi_networks,
    is_connected_same_wifi,
)
from .pages.generator import GeneratorPage
from .pages.scanner import ScannerPage
from .ui import icon_name_for_wifi_strength


log = Logger(__name__)


# Equivalent of the former Adw.Breakpoint condition 'max-width: 550sp'.
MOBILE_BREAKPOINT_PX = 550


@Gtk.Template.from_resource('/vn/quokka/CyperusCoi/gtk/window.ui')
class CoBangWindow(Handy.ApplicationWindow):
    __gtype_name__ = 'CoBangWindow'
    in_mobile_screen = GObject.Property(type=bool, default=False, nick='in-mobile-screen')
    # PyGobject seems not to support re-computing GObject.Property yet. So we will make it writable
    # and manually set new value later.
    is_outside_sandbox = GObject.Property(type=bool, default=False, nick='is-outside-sandbox')

    job_viewstack: Gtk.Stack = Gtk.Template.Child()
    job_switcher: Handy.ViewSwitcher = Gtk.Template.Child()
    job_toggler_box: Gtk.Box = Gtk.Template.Child()
    toggle_scanner: Gtk.ToggleButton = Gtk.Template.Child()
    toggle_generator: Gtk.ToggleButton = Gtk.Template.Child()

    scanner_page: ScannerPage = Gtk.Template.Child()
    generator_page: GeneratorPage = Gtk.Template.Child()

    portal_parent: Xdp.Parent
    nm_client: NM.Client | None = None

    # Guards against re-entrant `toggled` handlers while we synchronize the
    # pair of job toggle buttons (GTK3 has no radio-group for ToggleButton).
    _syncing_toggles: bool = False

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.portal_parent = XdpGtk3.parent_new_gtk(self)
        action = Gio.SimpleAction.new('paste-image', None)
        self.add_action(action)
        action.connect('activate', self.on_paste_image)

        # Connect signals from scanner page
        self.scanner_page.signal_request_camera_access.connect(self.on_camera_access_requested)
        self.scanner_page.poll_wifi_connection_status.connect(self.on_wifi_connection_status_polled)
        self.scanner_page.request_connect_wifi.connect(self.on_wifi_connecting_requested)

        # Connect signals from generator page
        self.generator_page.request_saved_wifi_networks.connect(self.on_request_saved_wifi_networks)

        # Keep a reference to the dummy agent on the window so it stays alive
        # and remains registered with NetworkManager.
        self.nm_dummy_agent = DummyAgent()

        # Initialize NM.Client
        NM.Client.new_async(None, self.cb_networkmanager_client_init_done)

        # Bindings which were done in the Blueprint UI file.
        self.bind_property(
            'in-mobile-screen',
            self.job_switcher,
            'visible',
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN,
        )
        self.bind_property(
            'in-mobile-screen',
            self.job_toggler_box,
            'visible',
            GObject.BindingFlags.SYNC_CREATE,
        )
        self.bind_property(
            'in-mobile-screen',
            self.scanner_page,
            'in-mobile-screen',
            GObject.BindingFlags.SYNC_CREATE,
        )
        self.bind_property(
            'in-mobile-screen',
            self.generator_page,
            'in-mobile-screen',
            GObject.BindingFlags.SYNC_CREATE,
        )
        self.bind_property(
            'is-outside-sandbox',
            self.scanner_page,
            'is-outside-sandbox',
            GObject.BindingFlags.SYNC_CREATE,
        )
        # Replacement for the Adw.Breakpoint: derive the mobile state from the
        # window width.
        self.connect('size-allocate', self.on_size_allocate)
        self._sync_toggles(JobName.SCANNER)

    def on_size_allocate(self, widget: Gtk.Widget, allocation: Gdk.Rectangle, *args) -> None:
        mobile = allocation.width < MOBILE_BREAKPOINT_PX
        if mobile != self.in_mobile_screen:
            log.debug('Window width {}, in_mobile_screen = {}', allocation.width, mobile)
            self.in_mobile_screen = mobile

    @property
    def portal(self) -> Xdp.Portal:
        app = self.get_application()
        assert app is not None
        if TYPE_CHECKING:
            from .app import CoBangApplication

            app = cast(CoBangApplication, app)
        return app.portal

    @Gtk.Template.Callback()
    def on_job_viewstack_visible_child_changed(self, viewstack: Gtk.Stack, *args):
        visible_child_name = viewstack.get_visible_child_name()
        if visible_child_name:
            self._sync_toggles(visible_child_name)
        self.scanner_page.update_webcam_activity(visible_child_name == JobName.SCANNER)

    def _sync_toggles(self, active_name: str):
        """Mirror the job viewstack state onto the toggle buttons.

        GTK3 ToggleButton has no `group` property, so we emulate the GTK4
        radio-group behavior manually.
        """
        self._syncing_toggles = True
        self.toggle_scanner.set_active(active_name == JobName.SCANNER)
        self.toggle_generator.set_active(active_name == JobName.GENERATOR)
        self._syncing_toggles = False

    @Gtk.Template.Callback()
    def on_toggle_scanner_toggled(self, button: Gtk.ToggleButton):
        if self._syncing_toggles:
            return
        if not button.get_active():
            # Radio-button semantics: an active button can only be deactivated
            # by activating its sibling.
            self._syncing_toggles = True
            button.set_active(True)
            self._syncing_toggles = False
            return
        self.job_viewstack.set_visible_child_name(JobName.SCANNER)

    @Gtk.Template.Callback()
    def on_toggle_generator_toggled(self, button: Gtk.ToggleButton):
        if self._syncing_toggles:
            return
        if not button.get_active():
            self._syncing_toggles = True
            button.set_active(True)
            self._syncing_toggles = False
            return
        self.job_viewstack.set_visible_child_name(JobName.GENERATOR)

    @Gtk.Template.Callback()
    def on_shown(self, *args):
        if self.get_application():
            outside_sandbox = not self.portal.running_under_sandbox() and not os.getenv(ENV_EMULATE_SANDBOX)
            log.debug('Calculated is_outside_sandbox: {}', outside_sandbox)
            self.is_outside_sandbox = outside_sandbox
        GLib.timeout_add(1000, self.check_and_start_webcam)

    @Gtk.Template.Callback()
    def on_close_request(self, window, event) -> bool:
        self.prepare_to_close()
        # Return False (don't stop the delete-event) so the window is closed
        # as usual after the cleanup.
        return False

    def check_and_start_webcam(self):
        scan_source = self.scanner_page.scan_source_viewstack.get_visible_child_name()
        log.info('Scan source: {}', scan_source)
        if scan_source == ScanSourceName.WEBCAM:
            self.scanner_page.request_camera_access()
        # Indicate that we don't want to repeat this callback.
        return False

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
        delegate = WiFiSaver()
        # This delegate will be used once and disposed.
        delegate.new_connection_saved.connect(self.on_wifi_saved)
        delegate.save_connection(wifi_info, self.nm_client)

    def cb_networkmanager_client_init_done(self, client: NM.Client, res: Gio.AsyncResult):
        """Callback for NM.Client initialization."""
        if not client:
            log.error('Failed to initialize NetworkManager client')
            return
        client.new_finish(res)
        self.nm_client = client
        log.debug('NM client: {}', client)

    def cb_wifi_secrets_retrieved(self, _src: WifiSecretsRetriever, uuid: str, failed: bool, password: str):
        """Callback for WiFi secrets retrieval."""
        if failed:
            log.info('Failed to retrieve WiFi secrets for UUID: {}', uuid)
            if self.generator_page:
                self.generator_page.set_wifi_network_error(uuid)
            return
        log.info('Retrieved password for UUID {}', uuid)
        if self.generator_page:
            self.generator_page.update_wifi_password(uuid, password)

    def on_paste_image(self, *args):
        self.scanner_page.receive_pasted_image()

    def on_request_saved_wifi_networks(self, _src: GeneratorPage):
        """Handle request to retrieve saved WiFi networks."""
        if not self.nm_client:
            log.error('No NM.Client available to retrieve saved WiFi networks')
            return

        wifi_networks = get_saved_wifi_networks(self.nm_client)
        for wifi_info in wifi_networks:
            # Map strength to icon name (GNOME symbolic icons)
            wifi_info.signal_strength_icon = icon_name_for_wifi_strength(wifi_info.signal_strength)

        log.info('Retrieved {} saved WiFi networks (sorted)', len(wifi_networks))
        if self.generator_page:
            self.generator_page.populate_wifi_networks(wifi_networks)

        # Asynchronously retrieve password for each connection.
        retriever = WifiSecretsRetriever()
        # This delegate will be used once and disposed: it is not attached to
        # the window, only its in-flight requests keep it alive.
        retriever.wifi_secrets_retrieved.connect(self.cb_wifi_secrets_retrieved)
        retriever.request_saved_wifi_secrets(self.nm_client)

    def on_wifi_saved(self, saver: WiFiSaver, ssid: str):
        # `saver` is no longer used and will be dropped.
        self.scanner_page.display_wifi_as_saved()

    def activate_pause_button(self):
        """Activate the Pause button if ScannerPage is visible and in an appropriate stage."""
        if self.job_viewstack.get_visible_child() == self.scanner_page and self.scanner_page.is_at_scanning:
            self.scanner_page.activate_pause_button()

    def process_file_from_commandline(self, file: Gio.File, mime_type: str):
        self.scanner_page.process_commandline_file(file, mime_type)

    def prepare_to_close(self):
        self.scanner_page.shuttingdown.set()
        # Tear down the GStreamer pipeline synchronously. It is to make sure
        # all the pending `on_new_webcam_sample` callbacks are processed before
        # the Python interpreter is destroyed, avoiding crash (observed with Python 3.14).
        self.scanner_page.teardown_webcam()
