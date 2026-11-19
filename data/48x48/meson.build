if rsvg.found()
  custom_target(
    'cobang-icon-48',
    input: files('../vn.quokka.CyperusCoi.svg'),
    output: 'vn.quokka.CyperusCoi.png',
    command: [
      rsvg,
      '-w', '48',
      '-h', '48',
      '-a',
      '@INPUT@',
      '-o', '@OUTPUT@',
    ],
    install: true,
    install_dir: themedir / '48x48/apps',
  )
endif
