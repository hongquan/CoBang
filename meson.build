project('cobang',
          version: '0.1.0',
    meson_version: '>= 0.50.0',
  default_options: [ 'warning_level=2',
                   ],
)

pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'cobang')

i18n = import('i18n')
python = import('python')

pymod = python.find_installation('python3')

# Make sure Python is installed and found
if not pymod.found()
    error('No valid python3 binary found')
endif

dependency('glib-2.0')
dependency('gobject-2.0')
dependency('gobject-introspection-1.0')
dependency('gtk+-3.0', version: '>=3.24')
dependency('gstreamer-1.0')
dependency('zbar')


subdir('data')
subdir('po')

conf = configuration_data()
conf.set('PYTHON', pymod.path())
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
