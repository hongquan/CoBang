"""Dispatch point for ``python -m dev <command>``."""

import sys

import click

from .extraction import extract_widget_hierarchy


@click.group()
def cli() -> None:
    pass


cli.add_command(extract_widget_hierarchy)


def main() -> None:
    cli(sys.argv[1:])


if __name__ == '__main__':
    main()
