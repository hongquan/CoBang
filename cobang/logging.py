import os.path
import inspect

import gi
import logbook
from logbook.handlers import Handler, StringFormatterHandlerMixin

gi.require_version('GLib', '2.0')

from gi.repository import GLib

from .consts import APP_ID


LOGBOOK_LEVEL_TO_GLIB = {
    logbook.DEBUG: GLib.LogLevelFlags.LEVEL_DEBUG,
    logbook.INFO: GLib.LogLevelFlags.LEVEL_INFO,
    logbook.WARNING: GLib.LogLevelFlags.LEVEL_WARNING,
    # For Error level, we translate to GLib Critical, instead of Error, because the later causes crash
    logbook.ERROR: GLib.LogLevelFlags.LEVEL_CRITICAL,
}


def _log(level: GLib.LogLevelFlags, message: str):
    stack = inspect.stack()
    line = stack[2][2]
    function = stack[2][3]
    filename = os.path.basename(stack[2][1])
    variant_message = GLib.Variant('s', message)
    variant_file = GLib.Variant('s', filename)
    variant_line = GLib.Variant('i', line)
    variant_func = GLib.Variant('s', function)

    variant_dict = GLib.Variant('a{sv}', {
        'MESSAGE': variant_message,
        'CODE_FILE': variant_file,
        'CODE_LINE': variant_line,
        'CODE_FUNC': variant_func
    })
    GLib.log_variant(APP_ID, level, variant_dict)


# Logbook custom handler to redirect message to GLib log
class GLibLogHandler(Handler, StringFormatterHandlerMixin):
    def emit(self, record):
        message = self.format(record)
        level = LOGBOOK_LEVEL_TO_GLIB[record.level]
        _log(level, message)
