custom_target(
  'cobang-icon-24',
  input: icon_svg,
  output: 'vn.hoabinh.quan.CoBang.png',
  command: [
    rsvg,
    '-w', '24',
    '-h', '24',
    '-a',
    '@INPUT@',
    '-o', '@OUTPUT@',
  ],
  install: true,
  install_dir: themedir / '24x24' / 'apps',
)
