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

import sys
from datetime import datetime

import gi
import zbar

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gio', '2.0')
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('Xdp', '1.0')
gi.require_version('XdpGtk4', '1.0')
gi.require_version('NM', '1.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Rsvg', '2.0')

from gettext import gettext as _

from logbook import Logger
from gi.repository import Adw, Gio, Gtk, Gst, NM, Xdp  # pyright: ignore[reportMissingModuleSource]

from .consts import BRAND_NAME, APP_ID, JobName, ScanSourceName
from .window import CoBangWindow
from .logging import GLibLogHandler
from .prep import guess_mimetype


DEVELOPPERS = ('Nguyễn Hồng Quân <ng.hong.quan@gmail.com>',)
ARTISTS = ('Shadd Gallegos', 'Lucide')
DONATE_TITLE = _('Support the developer')
COMMENTS = _('QR code / barcode scanner for Linux.\n%(donate_link)s') % {'donate_link': f"<a href='https://ko-fi.com/hongquanvn'>{DONATE_TITLE}</a>."}
log = Logger(__name__)


class CoBangApplication(Adw.Application):
    """The main application singleton class."""
    nm_client: NM.Client | None = None

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            # CoBang can be activated by context menu in file manager
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('about', self.on_about_action)
        self.portal = Xdp.Portal()
        self.zbar_scanner = zbar.ImageScanner()
        NM.Client.new_async(None, self.cb_networkmanager_client_init_done)

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        win = self.props.active_window
        if not win:
            win = CoBangWindow(application=self)
        win.present()

    def do_open(self, files: list[Gio.File], n_file: int, hint: str):
        """Called when the application is opened with files."""
        if not n_file:
            return
        # We only handle the first file
        file = files[0]
        log.debug('Opening file: {}', file)
        mime_type = guess_mimetype(file)
        log.info('MIME type: {}', mime_type)
        if not mime_type or not mime_type.startswith('image/'):
            log.info('Not an image. Ignore.')
            return
        win = self.props.active_window
        if not win:
            win = CoBangWindow(application=self)
        win.job_viewstack.set_visible_child_name(JobName.SCANNER)
        win.scan_source_viewstack.set_visible_child_name(ScanSourceName.IMAGE)
        win.process_file_from_commandline(file, mime_type)
        win.present()

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        if win := self.props.active_window:
            win.btn_pause.set_active(True)
        version = self.get_version() or '0.0'
        year = datetime.now().year
        about = Adw.AboutDialog(
            application_name=BRAND_NAME,
            application_icon=APP_ID,
            developer_name='Nguyễn Hồng Quân',
            version=version,
            developers=DEVELOPPERS,
            artists=ARTISTS,
            license_type=Gtk.License.GPL_3_0,
            copyright=f'© 2020 - {year} Nguyễn Hồng Quân',
            website='https://github.com/hongquan/CoBang',
            issue_url='https://github.com/hongquan/CoBang/issues',
            comments=COMMENTS,
        )
        # Translators: Replace "translator-credits" with your name/username, and optionally an email or URL.
        # about.set_translator_credits(_('translator-credits'))
        about.present(self.props.active_window)

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect('activate', callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f'app.{name}', shortcuts)

    def cb_networkmanager_client_init_done(self, client: NM.Client, res: Gio.AsyncResult):
        if not client:
            log.error('Failed to initialize NetworkManager client')
            return
        client.new_finish(res)
        self.nm_client = client
        log.debug('NM client: {}', client)


def main(version):
    """The application's entry point."""
    Gst.init(None)
    GLibLogHandler().push_application()
    app = CoBangApplication()
    app.set_version(version)
    return app.run(sys.argv)
