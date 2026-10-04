"""The ``textwire`` command: one entry point, one subcommand per job."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from textwire import __version__
from textwire.cli.bench import bench
from textwire.cli.doctor import doctor
from textwire.cli.serve import probe, serve
from textwire.cli.simulate import simulate
from textwire.vectors import check, find_repo_root, write

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

type Handler = Callable[[argparse.Namespace], int]


def _doctor(_args: argparse.Namespace) -> int:
    return doctor()


def _simulate(args: argparse.Namespace) -> int:
    drop = tuple(int(part) for part in args.drop.split(",") if part.strip()) if args.drop else ()
    return asyncio.run(
        simulate(
            offline=args.offline,
            commands=args.command_list or (),
            drop=drop,
            nak_after=args.nak,
            page_frames=args.page_frames,
        )
    )


def _serve(_args: argparse.Namespace) -> int:
    return asyncio.run(serve())


def _probe(args: argparse.Namespace) -> int:
    return asyncio.run(probe(args.number))


def _bench(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_repo_root()
    return bench(root, record=args.record, repeats=args.repeats)


def _vectors(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_repo_root()
    if args.action == "regen":
        changes = write(root)
        for change in changes:
            print(change)
        print(f"protocol/vectors regenerated: {len(changes)} file(s) changed")
        return 0
    problems = check(root)
    for problem in problems:
        print(problem)
    if problems:
        print("The golden vectors differ from the reference. If the change is intended, run")
        print("`make vectors`, review the diff, and update protocol/PROTOCOL.md to match.")
        return 1
    print("protocol/vectors match the reference")
    return 0


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

    command = commands.add_parser(
        "simulate", help="browse from the terminal with a virtual phone; no SMS are sent"
    )
    command.add_argument(
        "--offline", action="store_true", help="serve recorded pages from protocol/fixtures"
    )
    command.add_argument(
        "-c",
        "--command",
        dest="command_list",
        action="append",
        help="run this command instead of reading the keyboard (repeatable)",
    )
    command.add_argument("--drop", help="frame numbers to lose once, e.g. 3 or 2,5")
    command.add_argument(
        "--nak", type=float, default=3.0, help="seconds of silence before asking again"
    )
    command.add_argument("--page-frames", type=int, help="SMS per page (default from settings)")
    command.set_defaults(handler=_simulate)

    command = commands.add_parser("serve", help="run the server: poll for requests and answer")
    command.set_defaults(handler=_serve)

    command = commands.add_parser(
        "probe", help="send one frame with every byte value to a phone (route check)"
    )
    command.add_argument("number", help="the phone to send it to, in E.164 form")
    command.set_defaults(handler=_probe)

    command = commands.add_parser("vectors", help="regenerate or check the golden vectors")
    command.add_argument("action", choices=["regen", "check"])
    command.add_argument("--root", help="the repository root (found automatically)")
    command.set_defaults(handler=_vectors)

    command = commands.add_parser(
        "bench", help="measure SMS per page and pipeline speed against benchmarks/baseline.json"
    )
    command.add_argument("--record", action="store_true", help="write the result as the baseline")
    command.add_argument("--repeats", type=int, default=15, help="runs per timing (median)")
    command.add_argument("--root", help="the repository root (found automatically)")
    command.set_defaults(handler=_bench)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the subcommand named in ``argv`` and return the process exit status."""
    args = build_parser().parse_args(argv)
    handler: Handler = args.handler
    return handler(args)
