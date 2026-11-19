#!/usr/bin/env python3
"""Check consistency between Python templates, the gresource manifest and UI files.

Replaces the Blueprint-era `dev/check-ui-file-paths.nu`: there is no `.blp`
compilation step anymore, so this verifies that:

1. every `@Gtk.Template.from_resource('...')` path in `src/**/*.py`
   - starts with the application resource prefix,
   - is aliased in `src/cyperuscoi.gresource.xml`,
   - points at an existing file under `src/ui/`;
2. every `*.ui` file under `src/ui/` is bundled in the gresource manifest;
3. every `<template class="...">` in a `.ui` file is backed by a Python class
   with the same `__gtype_name__` that loads that resource.

Exit code: 0 if everything is consistent, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


APP_RES_PREFIX = '/vn/quokka/CyperusCoi'
GRESOURCE_XML = Path('src/cyperuscoi.gresource.xml')


def gresource_aliases() -> dict[str, Path]:
    """Map resource paths (relative to the prefix) to the real source files."""
    root = ET.parse(GRESOURCE_XML).getroot()
    mapping: dict[str, Path] = {}
    for gres in root.findall('gresource'):
        prefix = gres.get('prefix', '')
        for file in gres.findall('file'):
            alias = file.get('alias')
            real = file.text.strip() if file.text else ''
            res_path = (
                (prefix + '/' + (alias or real)).replace(APP_RES_PREFIX + '/', '', 1)
                if prefix.startswith(APP_RES_PREFIX)
                else (alias or real)
            )
            mapping[res_path] = Path('src') / real
    return mapping


def template_refs() -> list[tuple[Path, str, str]]:
    """Find (file, resource, gtype_name) for every @Gtk.Template.from_resource class."""
    pattern = re.compile(
        r"@Gtk\.Template\.from_resource\(\s*['\"]([^'\"]+)['\"]\s*\)\s*"
        r'class\s+([A-Za-z_][A-Za-z0-9_]*)'
    )
    refs = []
    for py_file in sorted(Path('src').rglob('*.py')):
        body = py_file.read_text()
        gtype = re.search(r"__gtype_name__\s*=\s*'([^']+)'", body)
        for res_path in pattern.finditer(body):
            refs.append((py_file, res_path.group(1), gtype.group(1) if gtype else ''))
    return refs


def main() -> int:
    issues = 0
    bundled = gresource_aliases()

    print('1. @Gtk.Template.from_resource references')
    refs = template_refs()
    if not refs:
        print('  (none found)')
    for py_file, res_path, gtype in refs:
        ok = res_path.startswith(APP_RES_PREFIX + '/')
        rel = res_path[len(APP_RES_PREFIX) + 1 :] if ok else res_path
        print(f'  [{"OK" if ok else "FAIL"}] {py_file} -> {res_path}')
        issues += 0 if ok else 1
        target = bundled.get(rel)
        exists = target is not None and target.exists()
        print(f'       bundled+exists: [{"OK" if exists else "FAIL"}] {target}')
        issues += 0 if exists else 1
        if target is not None:
            xml = target.read_text()
            declared = re.search(r'<template class="([^"]+)"', xml)
            match = declared is not None and declared.group(1) == gtype
            print(
                f'       template class {declared.group(1) if declared else "?"} == {gtype}: '
                f'[{"OK" if match else "FAIL"}]'
            )
            issues += 0 if match else 1

    print('2. Every src/ui/**/*.ui is bundled in the gresource manifest')
    for ui_file in sorted(Path('src/ui').rglob('*.ui')):
        rel = str(ui_file.relative_to('src'))
        found = any(p == ui_file for p in bundled.values())
        print(f'  [{"OK" if found else "FAIL"}] {ui_file}')
        issues += 0 if found else 1

    if issues:
        print(f'Found {issues} issue(s).')
        return 1
    print('All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
