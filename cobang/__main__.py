import sys

from .app import CoBangApplication
from .logging import GLibLogHandler


def main():
    with GLibLogHandler().applicationbound():
        app = CoBangApplication()
        return app.run(sys.argv)


if __name__ == '__main__':
    main()
