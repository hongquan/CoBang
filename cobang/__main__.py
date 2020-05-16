import sys

from logbook.more import ColorizedStderrHandler
from .app import CoBangApplication


def main():
    with ColorizedStderrHandler().applicationbound():
        app = CoBangApplication()
        app.run(sys.argv)


if __name__ == '__main__':
    main()
