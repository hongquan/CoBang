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
    Adw,  # pyright: ignore[reportMissingModuleSource]
    Gio,  # pyright: ignore[reportMissingModuleSource]
    GLib,  # pyright: ignore[reportMissingModuleSource]
    GObject,  # pyright: ignore[reportMissingModuleSource]
    Gtk,  # pyright: ignore[reportMissingModuleSource]
    Xdp,  # pyright: ignore[reportMissingModuleSource]
    XdpGtk4,  # pyright: ignore[reportMissingModuleSource]
)  # pyright: ignore[reportMissingModuleSource]
from logbook import Logger

from .consts import (
    ENV_EMULATE_SANDBOX,
    JobName,
    ScanSourceName,
)
from .custom_types import WifiNetworkInfo
from .messages import WifiInfoMessage
from .net import add_wifi_connection, is_connected_same_wifi
from .pages.generator import GeneratorPage
from .pages.scanner import ScannerPage
from .ui import icon_name_for_wifi_strength


log = Logger(__name__)


# This UI file is to be compiled from *.blp file.
@Gtk.Template.from_resource('/vn/hoabinh/quan/CoBang/gtk/window.ui')
class CoBangWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'CoBangWindow'
    in_mobile_screen = GObject.Property(type=bool, default=False, nick='in-mobile-screen')
    # PyGobject seems not to support re-computing GObject.Property yet. So we will make it writable
    # and manually set new value later.
    is_outside_sandbox = GObject.Property(type=bool, default=False, nick='is-outside-sandbox')

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
        self.scanner_page.connect('request-camera-access', self.on_camera_access_requested)
        self.scanner_page.connect('poll-wifi-connection-status', self.on_wifi_connection_status_polled)
        self.scanner_page.connect('request-connect-wifi', self.on_wifi_connecting_requested)

        # Connect signals from generator page
        self.generator_page.connect('request-saved-wifi-networks', self.on_request_saved_wifi_networks)

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
        if self.get_application():
            outside_sandbox = not self.portal.running_under_sandbox() and not os.getenv(ENV_EMULATE_SANDBOX)
            log.debug('Calculated is_outside_sandbox: {}', outside_sandbox)
            self.is_outside_sandbox = outside_sandbox
        GLib.timeout_add(1000, self.check_and_start_webcam)

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
        add_wifi_connection(wifi_info, self.cb_wifi_connect_done, self.nm_client)

    def cb_networkmanager_client_init_done(self, client: NM.Client, res: Gio.AsyncResult):
        """Callback for NM.Client initialization."""
        if not client:
            log.error('Failed to initialize NetworkManager client')
            return
        client.new_finish(res)
        self.nm_client = client
        log.debug('NM client: {}', client)

    def cb_wifi_secrets_retrieved(self, conn: NM.RemoteConnection, res: Gio.AsyncResult):
        """Callback for WiFi secrets retrieval."""
        try:
            secrets_variant = conn.get_secrets_finish(res)
        except GLib.Error as e:
            log.warning('Failed to retrieve WiFi secrets for "{}": {}', conn.get_id(), e)
            return
        if not secrets_variant:
            log.debug('No secrets returned for connection "{}"', conn.get_id())
            return

        # The variant is a dict with setting names as keys
        # e.g., {'802-11-wireless-security': {'psk': 'password'}}
        secrets = secrets_variant.unpack()
        wireless_security = secrets.get(NM.SETTING_WIRELESS_SECURITY_SETTING_NAME, {})

        if not wireless_security:
            log.debug('No wireless security setting in secrets for UUID: {}', conn.get_uuid())
            return

        # Try different password fields based on key management type
        if password := (
            wireless_security.get('psk')
            or wireless_security.get('wep-key0')
            or wireless_security.get('leap-password')
            or ''
        ):
            log.info('Retrieved password for "{}" Wi-Fi: {}', conn.get_id(), password)
            self.generator_page.update_wifi_password(conn.get_uuid(), password)
        else:
            log.debug('No password found in secrets for UUID: {}', conn.get_uuid())

    def on_paste_image(self, *args):
        self.scanner_page.on_paste_image()

    def on_request_saved_wifi_networks(self, _src: GeneratorPage):
        """Handle request to retrieve saved WiFi networks."""
        if not self.nm_client:
            log.error('No NM.Client available to retrieve saved WiFi networks')
            return

        wifi_networks = []
        connections = self.nm_client.get_connections()

        # Map SSID -> strongest signal (0-100)
        strengths: dict[str, int] = {}
        for device in self.nm_client.get_devices():  # type: ignore[attr-defined]
            if device.get_device_type() != NM.DeviceType.WIFI:
                continue
            for ap in device.get_access_points():
                ssid_bytes = ap.get_ssid()
                if not ssid_bytes:
                    continue
                ap_ssid = ssid_bytes.get_data().decode('utf-8', errors='ignore')
                strengths[ap_ssid] = max(strengths.get(ap_ssid, 0), ap.get_strength())

        # Currently active WiFi SSIDs
        active_ssids = set(
            ac.get_id()
            for ac in self.nm_client.get_active_connections()
            if ac.get_connection_type() == NM.SETTING_WIRELESS_SETTING_NAME
        )

        for conn in connections:
            wireless_setting = conn.get_setting_wireless()
            if not wireless_setting:
                continue
            ssid_bytes = wireless_setting.get_ssid()
            if not ssid_bytes:
                continue
            ssid = ssid_bytes.get_data().decode('utf-8', errors='ignore')

            # It is not possible to get Wi-Fi password from the `NM.SettingWirelessSecurity`
            password = ''
            key_mgmt = 'none'
            if wireless_security := conn.get_setting_wireless_security():
                key_mgmt = wireless_security.get_key_mgmt() or 'none'
                log.debug('WiFi key management: "{}"', key_mgmt)

            wifi_info = WifiNetworkInfo(
                uuid=conn.get_uuid(),
                ssid=ssid,
                password=password,
                key_mgmt=key_mgmt,
                is_active=ssid in active_ssids,
                signal_strength=strengths.get(ssid, 0),
            )
            # Map strength to icon name (GNOME symbolic icons)
            wifi_info.signal_strength_icon = icon_name_for_wifi_strength(wifi_info.signal_strength)
            wifi_networks.append(wifi_info)

        # Sort: active first, then by descending signal strength using stored fields
        wifi_networks.sort(key=lambda w: (w.is_active, w.signal_strength), reverse=True)

        log.info('Retrieved {} saved WiFi networks (sorted)', len(wifi_networks))
        self.generator_page.populate_wifi_networks(wifi_networks)

        # Asynchronously retrieve password for each connection
        for conn in connections:
            if conn.get_setting_wireless():
                # Request secrets for wireless security setting
                conn.get_secrets_async(NM.SETTING_WIRELESS_SECURITY_SETTING_NAME, None, self.cb_wifi_secrets_retrieved)

    def cb_wifi_connect_done(self, client: NM.Client, res: Gio.AsyncResult):
        """Callback for WiFi connection attempt."""
        try:
            conn = client.add_connection_finish(res)
            log.info('Successfully added and activated WiFi connection: {}', conn.get_id())
        except GLib.Error as e:
            log.error('Failed to add/activate WiFi connection: {}', e)
            return
        self.scanner_page.display_wifi_as_saved()

    def activate_pause_button(self):
        """Activate the Pause button if ScannerPage is visible and in an appropriate stage."""
        if self.job_viewstack.get_visible_child() == self.scanner_page and self.scanner_page.is_scanning():
            self.scanner_page.activate_pause_button()

    def process_file_from_commandline(self, file: Gio.File, mime_type: str):
        self.scanner_page.process_commandline_file(file, mime_type)
