# pyright: reportMissingImports=false

from pathlib import Path

from single_version import get_version


__version__ = get_version('cobang', Path(__file__).parent.parent)

if __version__.replace('.', '').replace('0', '') == '':
    try:
        # This file is put by Meson build script,
        # which doesn't support generate Python package metadata.
        from .fallback_version import VERSION
        __version__ = VERSION
    except ImportError:
        pass
