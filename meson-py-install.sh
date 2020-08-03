#!/bin/sh

# Wrapper script, to pass DESTDIR to Python setup.py script

# This script could be ran from different folder (like in flatpak-builder case),
# which causes ./setup.py failing
# to find our source package, so we need to jump to the folder containing this script.
SELF="$(realpath $0)"
SELF_DIR="$(dirname $SELF)"
echo "Relocate to $SELF_DIR"
cd "$SELF_DIR"
python3 setup.py install --root="$DESTDIR" --prefix="$1"
cd -
