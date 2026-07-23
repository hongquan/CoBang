prepare-build:
   meson setup __build --prefix ~/.local/

build:
   ninja -C __build

install:
   ninja -C __build install

uninstall:
   ninja -C __build uninstall
   # Sometimes, the old files still remain, making the app load old UI files.
   rm -rf ~/.local/share/cobang/

reinstall: uninstall install

type-check:
   zuban check src/
