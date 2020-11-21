#!/usr/bin/env python3

# This setup.py file is only to help build Debian package.
# It can not be used to install the app, because it cannot install the desktop files
# to correct place. That task is handled by debian/install file.
# This file can be converted from pyproject.toml, with help of dephell tool,
# but need to be modified afterward.

import re
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

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


# Ref: https://stackoverflow.com/q/40051076/502780
# Ref: https://jichu4n.com/posts/how-to-add-custom-build-steps-and-commands-to-setuppy/
class BuildWithMo(_build_py):
    def run(self):
        self.run_command('compile_catalog')
        super().run()


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
    include_package_data=True,
    install_requires=[
        'logbook==1.*,>=1.5.3', 'single-version==1.*,>=1.1.0',
    ],
    setup_requires=['babel'],
    extras_require={
        "dev": [
            "black==19.*,>=19.10.0.b0", "pygobject-stubs==0.*,>=0.0.2",
            "pytest==5.*,>=5.2.0"
        ]
    },
    cmdclass={
        'build_py': BuildWithMo,
    },
)
