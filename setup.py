#!/usr/bin/env python3

# This setup.py file is only to help build Debian package.
# It can not be used to install the app, because it cannot install the desktop files
# to correct place. That task is handled by debian/install file.
# This file can be converted from pyproject.toml, with help of dephell tool,
# but need to be modified afterward.

import re
import os
from pathlib import Path

from setuptools import setup

long_description = '''A missing native QR Code scanner application for Linux desktop.

It is written in Python, using GTK+ for UI, GStreamer for webcam capture and a part of ZBar \
for decoding QR code from image.
'''

SOURCE_DIR = Path(__file__).parent


def get_version():
    '''
    Get version string from pyproject.toml, so that we have a single source of data.
    '''
    filepath = SOURCE_DIR / 'pyproject.toml'
    content = filepath.read_text()
    m = re.search(r'version\s*=\s*"([.\-\w]+)"', content)
    return m.group(1)


# Hack: When building by flatpak-builder, this script is ran from different location
# and setuptools cannot find the source folder to install. So, in that case,
# we just change "current directory" to the correct location.
running_dir = os.getcwd()
if str(SOURCE_DIR) != running_dir:
    os.chdir(SOURCE_DIR)

setup(
    name='cobang',
    long_description=long_description,
    version=get_version(),
    description='QR code scanner for Linux desktop',
    python_requires='==3.*,>=3.7.0',
    author='Nguyễn Hồng Quân',
    author_email='ng.hong.quan@gmail.com',
    license='GPL-3.0-or-later',
    url='https://github.com/hongquan/CoBang',
    entry_points={"console_scripts": ["cobang = cobang.__main__:main"]},
    packages=['cobang'],
    package_dir={"": "."},
    install_requires=[
        'logbook==1.*,>=1.5.3', 'single-version==1.*,>=1.1.0',
    ],
    extras_require={
        "dev": [
            "black==19.*,>=19.10.0.b0", "pygobject-stubs==0.*,>=0.0.2",
            "pytest==5.*,>=5.2.0"
        ]
    },
)

os.chdir(running_dir)
