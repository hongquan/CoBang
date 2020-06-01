project('cobang',
          version: '0.2.0',
    meson_version: '>= 0.50.0',
  default_options: [ 'warning_level=2',
                   ],
)

pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'cobang')

i18n = import('i18n')
pymod = import('python')

python = pymod.find_installation('python3')
pythonver = python.language_version()
# Workaround for https://github.com/mesonbuild/meson/issues/5629
# https://gitlab.freedesktop.org/gstreamer/gst-python/issues/28
python_dep = dependency('python-@0@-embed'.format(pythonver), version: '>= 3.7', required: false)

# Make sure Python is installed and found
if not python_dep.found()
  python_dep = python.dependency(version: '>= 3.7')
endif

dependency('glib-2.0')
dependency('gobject-2.0')
dependency('gobject-introspection-1.0')
dependency('gtk+-3.0', version: '>=3.24')
dependency('zbar')

gst_dep = dependency('gstreamer-1.0', version : '>= 1.16',
  fallback : ['gstreamer', 'gst_dep'])


subdir('data')
subdir('po')

conf = configuration_data()
conf.set('PYTHON', python.path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'cobang.in',
  output: 'cobang',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

meson.add_install_script('flatpak/meson/postinstall.py')
