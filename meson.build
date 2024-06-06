project('cobang',
        version: '0.13.0',
        meson_version: '>= 0.61',
        default_options: [
          'warning_level=2',
        ],
)

pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()

i18n = import('i18n')
pymod = import('python')

python = pymod.find_installation('python3')
python_dep = python.dependency(embed:true, required : true)

dependency('glib-2.0')
dependency('gobject-2.0')
dependency('gobject-introspection-1.0')
dependency('gtk+-3.0', version: '>=3.24')

conf = configuration_data()
conf.set('PYTHON', python.path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

install_subdir(
  meson.project_name(),
  install_dir: python.get_install_dir()
)
subdir('data')
subdir('exe')
subdir('po')

configure_file(
  input: 'misc/fallback_version.py.in',
  output: 'fallback_version.py',
  configuration: conf,
  install: true,
  install_dir: python.get_install_dir() / meson.project_name()
)


meson.add_install_script('flatpak/meson/postinstall.py')
