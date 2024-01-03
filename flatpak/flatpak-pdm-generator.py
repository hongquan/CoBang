#!/usr/bin/env python3

import sys
import json
from pathlib import Path
from io import StringIO
from collections import deque
from typing import TypedDict

import click
import httpx
from pydantic import BaseModel
from ruamel.yaml import YAML

try:
    import tomllib
except ImportError:
    import tomli as tomllib


class InstallableFile(BaseModel):
    hash: str
    file: str

    @property
    def is_neutral_wheel(self):
        return self.file.endswith('py3-none-any.whl')

    @property
    def is_tarball(self):
        return self.file.endswith('.tar.gz')


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


def convert_to_flatpak_source(package: Package):
    ifile = next((f for f in package.files if f.is_neutral_wheel), None)
    if not ifile:
        ifile = next((f for f in package.files if f.is_tarball), None)
    if ifile:
        sha256 = ifile.hash.split(':')[1]
        url = find_file_url(package, sha256)
        if not url:
            click.secho(f'Failed to find file URL for {package.name}', fg='red', err=True)
            return
        return {
            'type': 'file',
            'url': url,
            'sha256': sha256,
        }


def find_file_url(package: Package, sha256: str):
    api_url = f'https://pypi.org/pypi/{package.name}/{package.version}/json'
    resp = httpx.get(api_url).json()
    release = PyPIRelease.model_validate(resp)
    for r in release.urls:
        if r.digests.sha256 == sha256:
            return r.url


@click.command()
@click.argument('lockfile', type=click.Path(exists=True, path_type=Path))
@click.option('-o', '--out-file', type=click.Path(writable=True, path_type=Path))
def main(lockfile: Path, out_file: Path | None = None):
    """Flatpak PDM generator"""
    with lockfile.open('rb') as f:
        pdm_lock = PDMLock.model_validate(tomllib.load(f))
    packages = pdm_lock.package
    prod_packages = tuple(p for p in packages if 'default' in p.groups)
    sources = deque()
    dependencies = deque()
    for p in prod_packages:
        source = convert_to_flatpak_source(p)
        if not source:
            continue
        sources.append(source)
        dependencies.append(p.name)
    out_dict = {
        'name': 'pdm-deps',
        'buildsystem': 'simple',
        'build-commands': [
            'python3 -m pip install --no-index --find-links="file://${PWD}" --prefix=${FLATPAK_DEST} ' + ' '.join(dependencies)
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
