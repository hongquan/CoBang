# Copyright © 2020, Nguyễn Hồng Quân <ng.hong.quan@gmail.com>

import gi
import logbook
from logbook.handlers import Handler, StringFormatterHandlerMixin

gi.require_version('GLib', '2.0')

from gi.repository import GLib

from .consts import SHORT_NAME


LOGBOOK_LEVEL_TO_GLIB = {
    logbook.DEBUG: GLib.LogLevelFlags.LEVEL_DEBUG,
    logbook.INFO: GLib.LogLevelFlags.LEVEL_INFO,
    logbook.WARNING: GLib.LogLevelFlags.LEVEL_WARNING,
    # For Error level, we translate to GLib Critical, instead of Error, because the later causes crash
    logbook.ERROR: GLib.LogLevelFlags.LEVEL_CRITICAL,
}


def _log(level: GLib.LogLevelFlags, message: str):
    variant_message = GLib.Variant('s', message)

    variant_dict = GLib.Variant('a{sv}', {
        'MESSAGE': variant_message,
    })
    GLib.log_variant(SHORT_NAME, level, variant_dict)


# Logbook custom handler to redirect message to GLib log
class GLibLogHandler(Handler, StringFormatterHandlerMixin):
    def emit(self, record):
        message = self.format(record)
        level = LOGBOOK_LEVEL_TO_GLIB[record.level]
        _log(level, message)
