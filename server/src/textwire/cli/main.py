"""The ``textwire`` command: one entry point, one subcommand per job."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from textwire import __version__
from textwire.cli.doctor import doctor

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

type Handler = Callable[[argparse.Namespace], int]


def _doctor(_args: argparse.Namespace) -> int:
    return doctor()


def build_parser() -> argparse.ArgumentParser:
    """The argument parser for every subcommand."""
    parser = argparse.ArgumentParser(
        prog="textwire",
        description="A text-mode web delivered over SMS.",
    )
    parser.add_argument("--version", action="version", version=f"textwire {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    command = commands.add_parser("doctor", help="check this machine and the configuration")
    command.set_defaults(handler=_doctor)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the subcommand named in ``argv`` and return the process exit status."""
    args = build_parser().parse_args(argv)
    handler: Handler = args.handler
    return handler(args)
