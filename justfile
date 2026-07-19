build:
   ninja -C __build

install:
   ninja -C __build install

uninstall:
   ninja -C __build uninstall

type-check:
   zuban check src/
