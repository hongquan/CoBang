#!/usr/bin/env python3

# Generate Flatpak-builder manifest file from PDM lock file.
# Keep:
# - Linux wheel files which target x86_64 or aarch64, Python 3.10 or later.
# - Neutral wheel files.
# - Tarball file, in case the Linux wheel files for the platform is not available.
# - If neutral wheel file is available, we don't keep tarball file.

import re
import json
from pathlib import Path, PurePath
from io import StringIO
from collections import deque

import click
import httpx
from packaging.tags import parse_tag
from pydantic import BaseModel
from ruamel.yaml import YAML

try:
    import tomllib
except ImportError:
    import tomli as tomllib


REGEX_PY_VERSION = re.compile(r'3(\d+)')


def parse_python_version(version: str) -> tuple[int, int] | None:
    m = REGEX_PY_VERSION.search(version)
    if not m:
        return None
    return (3, int(m.group(1)))


class InstallableFile(BaseModel):
    hash: str
    file: PurePath

    @property
    def is_neutral_wheel(self):
        return self.file.name.endswith('py3-none-any.whl')

    @property
    def is_linux_wheel(self):
        # FlatHub only supports x86_64 and aarch64
        return self.file.name.endswith(('x86_64.whl', 'aarch64.whl')) and 'linux' in self.file.name

    @property
    def is_recent_linux_wheel(self):
        '''Check if the wheel is built for Python 3.10 or later.'''
        if not self.is_linux_wheel:
            return False
        tag_string = self.file.stem.split('-', 2)[-1]
        tag = next(iter(parse_tag(tag_string)))
        ver = parse_python_version(tag.interpreter)
        if not ver:
            return False
        return ver >= (3, 10)

    @property
    def is_tarball(self):
        return self.file.name.endswith(('.tar.gz', '.tar.bz2', '.tar.xz'))


class Package(BaseModel):
    name: str
    version: str
    groups: list[str]
    files: list[InstallableFile]


class PDMLock(BaseModel):
    package: list[Package]


class FileDigest(BaseModel):
    sha256: str


class PyPIReleaseUrl(BaseModel):
    url: str
    digests: FileDigest


class PyPIRelease(BaseModel):
    urls: list[PyPIReleaseUrl]


def convert_to_flatpak_sources(package: Package):
    sources = []
    installable_files = tuple(f for f in package.files if f.is_neutral_wheel or f.is_recent_linux_wheel or f.is_tarball)
    # Remove tarball if there is neutral wheel
    if any(f.is_neutral_wheel for f in installable_files):
        installable_files = tuple(f for f in installable_files if f.is_neutral_wheel or f.is_linux_wheel)
    if not installable_files:
        return []
    pypi_files = get_pypi_release_files(package)
    for ifile in installable_files:
        sha256 = ifile.hash.split(':')[1]
        url = next((f for f in pypi_files if f.digests.sha256 == sha256), None)
        if not url:
            click.secho(f'Failed to find file URL for {package.name} v{package.version}', fg='red', err=True)
            continue
        sources.append({
            'type': 'file',
            'url': url.url,
            'sha256': sha256,
        })
    return sources


def get_pypi_release_files(package: Package):
    api_url = f'https://pypi.org/pypi/{package.name}/{package.version}/json'
    click.secho(f'Retrieving {api_url}...', fg='blue', err=True)
    resp = httpx.get(api_url).json()
    release = PyPIRelease.model_validate(resp)
    return release.urls


@click.command()
@click.argument('lockfile', type=click.Path(exists=True, path_type=Path))
@click.option('-o', '--out-file', type=click.Path(writable=True, path_type=Path), help='Output file, should have .json or .yml extension. Default to write to standard ouput in YAML format.')
def main(lockfile: Path, out_file: Path | None = None):
    """Generate Flatpak-builder manifest file from PDM lock file."""

    with lockfile.open('rb') as f:
        pdm_lock = PDMLock.model_validate(tomllib.load(f))
    packages = pdm_lock.package
    prod_packages = tuple(p for p in packages if 'default' in p.groups)
    sources = deque()
    dependencies = deque()
    for p in prod_packages:
        batch = convert_to_flatpak_sources(p)
        if not batch:
            continue
        sources.extend(batch)
        dependencies.append(p.name)
    out_dict = {
        'name': 'pdm-deps',
        'buildsystem': 'simple',
        'build-commands': [
            'python3 -m pip install --no-index --find-links="file://${PWD}" --prefix=${FLATPAK_DEST} --no-build-isolation ' + ' '.join(dependencies)
        ],
        'sources': tuple(sources)
    }
    if not out_file:
        yaml = YAML()
        s = StringIO()
        yaml.dump(out_dict, s)
        click.echo(s.getvalue())
        return
    if out_file.suffix == '.yml' or out_file.suffix == '.yaml':
        yaml = YAML()
        with out_file.open('w') as f:
            yaml.dump(out_dict, f)
        return
    with out_file.open('w') as f:
        json.dump(out_dict, f)


if __name__ == '__main__':
    main()
