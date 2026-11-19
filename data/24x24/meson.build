if rsvg.found()
  custom_target(
    'cobang-icon-24',
    input: 'vn.quokka.CyperusCoi.svg',
    output: 'vn.quokka.CyperusCoi.png',
    command: [
      rsvg,
      '-w', '24',
      '-h', '24',
      '-a',
      '@INPUT@',
      '-o', '@OUTPUT@',
    ],
    install: true,
    install_dir: themedir / '24x24/apps',
  )
endif
