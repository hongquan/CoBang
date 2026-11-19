pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'cyperuscoi'
gnome = import('gnome')

gnome.compile_resources('cyperuscoi',
  'cyperuscoi.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'cyperuscoi.in',
  output: 'cyperuscoi',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

cyperuscoi_sources = [
  '__init__.py',
  'consts.py',
  'app.py',
  'messages.py',
  'net.py',
  'prep.py',
  'ui.py',
  'window.py',
  'custom_types.py',
]

install_data(cyperuscoi_sources, install_dir: moduledir)

subdir('pages')
