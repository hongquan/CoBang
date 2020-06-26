import tempfile
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit
from typing import Optional

import gi
import requests
from kiss_headers import parse_it
from PIL import Image, UnidentifiedImageError

gi.require_version('Gio', '2.0')
from gi.repository import Gio

from .consts import SHORT_NAME, WELKNOWN_IMAGE_EXTS


# Folder to look for icon, glade files
# - If this app is installed in ~/.local/bin and run from there, look for ~/.local/share/cobang
# - If this app is install in /usr/local/bin and run from there, look for /usr/local/share/cobang
# - If this app is install in /app/, which is the case of Faltpak container, look for /app/share/cobang
# - If this app is run from source, look in the source folder

DOT_LOCAL = Path('~/.local').expanduser()


def get_location_prefix() -> Path:
    top_app_dir = Path(__file__).parent.parent.resolve()
    str_top_app_dir = str(top_app_dir)
    if str_top_app_dir.startswith('/usr/local/'):
        return Path('/usr/local/')
    if str_top_app_dir.startswith('/usr/'):
        return Path('/usr/')
    if str_top_app_dir.startswith('/app/'):
        return Path('/app/')
    if str_top_app_dir.startswith(str(DOT_LOCAL)):
        return DOT_LOCAL
    # Run from source
    return top_app_dir


def get_ui_folder() -> Path:
    prefix = get_location_prefix()
    # Note: The trailing slash "/" is stripped by Path()
    str_prefix = str(prefix)
    if str_prefix.startswith(('/usr', '/app', str(DOT_LOCAL))):
        return prefix / 'share' / SHORT_NAME
    # Run from source
    return prefix / 'data'


def get_locale_folder() -> Path:
    prefix = get_location_prefix()
    return prefix / 'locale'


def get_ui_filepath(filename: str) -> Path:
    ui_folder = get_ui_folder()
    return ui_folder / filename


def get_ui_source(filename: str) -> str:
    filepath = get_ui_filepath(filename)
    return filepath.read_text()


def is_local_real_image(path: str) -> bool:
    try:
        Image.open(path)
        return True
    except (UnidentifiedImageError, ValueError):
        return False
    return False


def maybe_remote_image(url: str):
    parsed = urlsplit(url)
    suffix = Path(parsed.path).suffix
    # Strip leading dot
    ext = suffix[1:].lower()
    return ext in WELKNOWN_IMAGE_EXTS


def guess_content_type(file: Gio.File) -> str:
    info: Gio.FileInfo = file.query_info(Gio.FILE_ATTRIBUTE_STANDARD_FAST_CONTENT_TYPE,
                                         Gio.FileQueryInfoFlags.NONE, None)
    return info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_STANDARD_FAST_CONTENT_TYPE)


def cache_http_file(uri: str) -> Optional[Gio.File]:
    with requests.get(uri, timeout=5, stream=True) as resp:
        h = parse_it(resp)
        if not str(h.content_type).startswith('image/'):
            return
        ext = mimetypes.guess_extension(str(h.content_type or '')) or ''
        # Is an image, guess filename
        if 'Content-Disposition' in h:
            filename = h.content_disposition.filename
        else:
            path = Path(urlsplit(uri).path)
            filename = path.name
        dirpath = tempfile.mkdtemp(prefix=SHORT_NAME)
        filepath = Path(dirpath) / (filename + ext)
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content():
                f.write(chunk)
    return Gio.File.new_for_path(str(filepath))
