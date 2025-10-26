pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'cobang'
gnome = import('gnome')

blueprints = custom_target('blueprints',
  input: files(
    'ui/help-overlay.blp',
    'ui/window.blp',
    'ui/wifi-display.blp',
    'ui/url-display.blp',
    'ui/generator-page.blp',
  ),
  output: 'gtk',
  command: [find_program('blueprint-compiler', '/usr/bin/blueprint-compiler', '/usr/local/bin/blueprint-compiler'), 'batch-compile', '@OUTPUT@', '@CURRENT_SOURCE_DIR@/ui', '@INPUT@'],
)

gnome.compile_resources('cobang',
  'cobang.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  dependencies: blueprints,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'cobang.in',
  output: 'cobang',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

cobang_sources = [
  '__init__.py',
  'consts.py',
  'app.py',
  'logging.py',
  'messages.py',
  'net.py',
  'prep.py',
  'ui.py',
  'window.py',
  'custom_types.py',
]

install_data(cobang_sources, install_dir: moduledir)

subdir('pages')
