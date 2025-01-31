import io

from logbook import Logger
from gi.repository import Gio  # pyright: ignore[reportMissingModuleSource]


log = Logger(__name__)


def guess_mimetype(file: Gio.File) -> str:
    # If file is local, we check magic bytes to determine the content type, otherwise we guess from file extension.
    attr = Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE if file.is_native() else Gio.FILE_ATTRIBUTE_STANDARD_FAST_CONTENT_TYPE
    log.debug('Querying attribute: {}', attr)
    info = file.query_info(attr, Gio.FileQueryInfoFlags.NONE, None)
    return info.get_attribute_string(attr)
