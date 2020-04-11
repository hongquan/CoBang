from pathlib import Path


def get_ui_folder() -> Path:
    top_app_dir = Path(__file__).parent.parent
    data_folder = top_app_dir / 'data'
    if data_folder.exists():
        return data_folder


def get_ui_filepath(filename: str) -> Path:
    ui_folder = get_ui_folder()
    return ui_folder / filename


def get_ui_source(filename: str) -> str:
    filepath = get_ui_filepath(filename)
    return filepath.read_text()
