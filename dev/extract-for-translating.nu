#!/usr/bin/env nu
xgettext --from-code=UTF-8 --add-comments --keyword=_ --keyword=C_:1c,2 src/ui/*.blp src/*.py -o po/cobang.pot
