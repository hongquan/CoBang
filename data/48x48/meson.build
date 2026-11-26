custom_target(
  'cobang-icon-48',
  input: icon_svg,
  output: 'vn.hoabinh.quan.CoBang.png',
  command: [
    rsvg,
    '-w', '48',
    '-h', '48',
    '-a',
    '@INPUT@',
    '-o', '@OUTPUT@',
  ],
  install: true,
  install_dir: themedir / '48x48' / 'apps',
)
