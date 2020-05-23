# This setup.py file is only to help building Debian package.

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

long_description = '''A missing native QR Code scanner application for Linux desktop.

It is written in Python, using GTK+ for UI, GStreamer for webcam capture and a part of ZBar \
for decoding QR code from image.
'''

setup(
    long_description=long_description,
    name='cobang',
    version='0.1.0',
    description='QR code scanner for Linux desktop',
    python_requires='==3.*,>=3.7.0',
    author='Nguyễn Hồng Quân',
    author_email='ng.hong.quan@gmail.com',
    license='Apache-2.0',
    url='https://github.com/hongquan/CoBang',
    entry_points={"console_scripts": ["cobang = cobang.__main__:main"]},
    packages=['cobang'],
    package_dir={"": "."},
    package_data={"cobang": ["data/*.glade", "data/*.svg"]},
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
