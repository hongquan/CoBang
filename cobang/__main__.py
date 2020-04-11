import sys

from .app import CoBangApplication


def main():
    app = CoBangApplication()
    app.run(sys.argv)


if __name__ == '__main__':
    main()
