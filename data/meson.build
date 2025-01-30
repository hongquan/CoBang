desktop_file = i18n.merge_file(
  input: 'vn.hoabinh.quan.CoBang.desktop.in',
  output: 'vn.hoabinh.quan.CoBang.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications',
)

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: [desktop_file])
endif

themedir = get_option('datadir') / 'icons/hicolor'
install_data('vn.hoabinh.quan.CoBang.svg', install_dir: themedir / 'scalable/apps')
subdir('48x48')

appstream_file = i18n.merge_file(
  input: 'vn.hoabinh.quan.CoBang.metainfo.xml.in',
  output: 'vn.hoabinh.quan.CoBang.metainfo.xml',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'metainfo',
)

appstreamcli = find_program('appstreamcli', required: false, disabler: true)
test(
  'Validate appstream file',
  appstreamcli,
  args: ['validate', '--no-net', '--explain', appstream_file],
)

install_data(
  'vn.hoabinh.quan.CoBang.gschema.xml',
  install_dir: get_option('datadir') / 'glib-2.0' / 'schemas',
)

compile_schemas = find_program('glib-compile-schemas', required: false, disabler: true)
test(
  'Validate schema file',
  compile_schemas,
  args: ['--strict', '--dry-run', meson.current_source_dir()],
)

service_conf = configuration_data()
service_conf.set('bindir', get_option('prefix') / get_option('bindir'))
configure_file(
  input: 'vn.hoabinh.quan.CoBang.service.in',
  output: 'vn.hoabinh.quan.CoBang.service',
  configuration: service_conf,
  install_dir: get_option('datadir') / 'dbus-1' / 'services',
)
