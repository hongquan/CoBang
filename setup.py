import re
from pathlib import Path

# This setup.py file is only to help build Debian package.
# It can not be used to install the app, because it cannot install the desktop files
# to correct place. That task is handled by debian/install file.
# This file can be converted from pyproject.toml, with help of dephell tool,
# but need to be modified afterward.

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

long_description = '''A missing native QR Code scanner application for Linux desktop.

It is written in Python, using GTK+ for UI, GStreamer for webcam capture and a part of ZBar \
for decoding QR code from image.
'''


def get_version():
    '''
    Get version string from pyproject.toml, so that we have a single source of data.
    '''
    filepath = Path('pyproject.toml')
    content = filepath.read_text()
    m = re.search(r'version\s*=\s*"([.\-\w]+)"', content)
    return m.group(1)


setup(
    long_description=long_description,
    name='cobang',
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
