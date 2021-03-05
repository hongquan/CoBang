#!/usr/bin/env python3

import subprocess
from pathlib import Path

import click

from cobang.consts import SHORT_NAME


ROOT = Path(__file__).parent


@click.group()
def cli():
    pass


@cli.command()
def extract_translation():
    filepath = ROOT / 'po' / f'{SHORT_NAME}.pot'
    cmd = ('pybabel', 'extract', '-F', 'babel.cfg', '-o', filepath, '.')
    subprocess.run(cmd)


@cli.command()
@click.option('--locale', '-l', 'locales', multiple=True)
def update_translation(locales: str):
    valid_locales = {}
    if not locales:
        existing_files = ROOT.joinpath('po').glob('*.po')
        for filepath in existing_files:
            lo = filepath.with_suffix('').name
            valid_locales[lo] = filepath
    else:
        for lo in locales:
            filepath = ROOT / 'po' / f'{lo}.po'
            if filepath.exists():
                valid_locales[lo] = filepath
    if not valid_locales:
        click.echo('Locale files do not exist', err=True)
        return
    pot_path = ROOT / 'po' / f'{SHORT_NAME}.pot'
    for lo, filepath in valid_locales.items():
        cmd = ('pybabel', 'update', '-D', SHORT_NAME, '-l', lo, '-i', pot_path, '-o', filepath)
        subprocess.run(cmd)


@cli.command()
@click.option('--locale', '-l', 'locales', multiple=True)
def compile_translation(locales: str):
    valid_locales = {}
    if not locales:
        existing_files = ROOT.joinpath('po').glob('*.po')
        for filepath in existing_files:
            lo = filepath.with_suffix('').name
            valid_locales[lo] = filepath
    else:
        for lo in locales:
            filepath = ROOT / 'po' / f'{lo}.po'
            if filepath.exists():
                valid_locales[lo] = filepath
    if not valid_locales:
        click.echo('Locale files do not exist', err=True)
        return
    for lo, filepath in valid_locales.items():
        mo_folder: Path = ROOT / 'po' / lo / 'LC_MESSAGES'
        if not mo_folder.exists():
            mo_folder.mkdir(parents=True, exist_ok=True)
        cmd = ('pybabel', 'compile', '-D', SHORT_NAME, '-l', lo, '-i', filepath, '-d', 'po')
        subprocess.run(cmd)


if __name__ == '__main__':
    cli()
