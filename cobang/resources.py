from pathlib import Path

from .consts import SHORT_NAME

# Folder to look for icon, glade files
# - If this app is installed in ~/.local/bin and run from there, look for ~/.local/share/cobang
# - If this app is install in /usr/local/bin and run from there, look for /usr/local/share/cobang
# - If this app is run from source, look in the source folder


def get_ui_folder() -> Path:
    top_app_dir = Path(__file__).parent.parent.resolve()
    str_top_app_dir = str(top_app_dir)
    if str_top_app_dir.startswith('/usr/local/'):
        data_folder = Path(f'/usr/local/share/{SHORT_NAME}')
    elif str_top_app_dir.startswith('/usr/'):
        data_folder = Path(f'/usr/share/{SHORT_NAME}')
    elif str_top_app_dir.startswith(str(Path('~/.local/').expanduser())):
        data_folder = Path(f'~/.local/share/{SHORT_NAME}').expanduser()
    else:
        # Run from source
        data_folder = top_app_dir / 'data'
    if data_folder.exists():
        return data_folder


def get_ui_filepath(filename: str) -> Path:
    ui_folder = get_ui_folder()
    return ui_folder / filename


def get_ui_source(filename: str) -> str:
    filepath = get_ui_filepath(filename)
    return filepath.read_text()
