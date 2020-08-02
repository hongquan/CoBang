project('cobang',
        version: '0.5.6',
        meson_version: '>= 0.50.0',
        default_options: [
          'warning_level=2',
        ],
)

pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()

i18n = import('i18n')
pymod = import('python')

python = pymod.find_installation('python3')
pythonver = python.language_version()
# Workaround for https://github.com/mesonbuild/meson/issues/5629
# https://gitlab.freedesktop.org/gstreamer/gst-python/issues/28
python_dep = dependency('python-@0@-embed'.format(pythonver), version: '> 3.7', required: false)

# Make sure Python is installed and found
if not python_dep.found()
  python_dep = python.dependency(version: '>= 3.7')
endif

dependency('glib-2.0')
dependency('gobject-2.0')
dependency('gobject-introspection-1.0')
dependency('gtk+-3.0', version: '>=3.24')
dependency('libnm', version: '>= 1.22')

gst_dep = dependency('gstreamer-1.0', version : '>= 1.16',
  fallback : ['gstreamer', 'gst_dep'])

conf = configuration_data()
conf.set('PYTHON', python.path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)


# To install the subdir "cobang", we don't use Meson's subdir function,
# because Meson doesn't generate Python package metadata.
# Issue: https://github.com/mesonbuild/meson/issues/7251

# Try to retrieve $DESTDIR envvar, which is not supported by Meson
sh = run_command('sh', '-c', 'printf $DESTDIR')
destdir = sh.stdout().strip()
pyapp_prefix = destdir / get_option('prefix')
meson.add_install_script('setup.py', 'install', '--prefix', pyapp_prefix)
subdir('data')
subdir('exe')
subdir('po')

meson.add_install_script('flatpak/meson/postinstall.py')
