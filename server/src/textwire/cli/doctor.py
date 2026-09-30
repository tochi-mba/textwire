"""``textwire doctor``: say what this machine and configuration are missing, and how to fix it.

Each check reports ``ok``, ``warn`` or ``fail``. Warnings are things that stop the real
server but not the tests or the simulator, such as missing Twilio credentials; failures stop
everything. The exit status is 1 when anything failed.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import ValidationError

from textwire.config import load_settings

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from textwire.config import Settings

MINIMUM_PYTHON = (3, 12)


class Status(StrEnum):
    """How a check came out."""

    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class Check:
    """One line of the doctor's report."""

    name: str
    status: Status
    detail: str


def python_check(version: Sequence[int] | None = None) -> Check:
    """The interpreter (the running one by default) is new enough."""
    if version is None:
        version = tuple(sys.version_info[:3])
    shown = ".".join(str(part) for part in version[:3])
    if tuple(version[:2]) >= MINIMUM_PYTHON:
        return Check("python", Status.OK, shown)
    return Check(
        "python", Status.FAIL, f"{shown}; install Python 3.12 or newer (uv python install)"
    )


def data_dir_check(path: Path) -> Check:
    """The data directory exists or can be created, and is writable."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".doctor-probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check("data directory", Status.FAIL, f"{path}: {exc.strerror or exc}")
    return Check("data directory", Status.OK, str(path.resolve()))


def transport_check(settings: Settings) -> Check:
    """The configured transport has what it needs to run the real server."""
    problems = settings.transport_problems()
    if problems:
        return Check(f"{settings.transport} transport", Status.WARN, "; ".join(problems))
    return Check(f"{settings.transport} transport", Status.OK, "configured (not verified)")


def _one_line(error: Exception) -> str:
    lines = [line.strip() for line in str(error).splitlines() if line.strip()]
    return " ".join(lines[1:] if isinstance(error, ValidationError) else lines)


def run_checks(load: Callable[[], Settings] = load_settings) -> list[Check]:
    """Every check, in the order a person would fix them."""
    checks = [python_check()]
    try:
        settings = load()
    except (ValidationError, RuntimeError) as exc:
        checks.append(Check("configuration", Status.FAIL, _one_line(exc)))
        return checks
    checks.append(Check("configuration", Status.OK, f"environment {settings.environment!r}"))
    checks.append(data_dir_check(settings.data_dir))
    checks.append(transport_check(settings))
    return checks


def render(checks: Sequence[Check]) -> str:
    """The report as aligned text."""
    width = max(len(check.name) for check in checks)
    return "\n".join(
        f"  {check.status.value:<5} {check.name:<{width}}  {check.detail}" for check in checks
    )


def doctor(
    load: Callable[[], Settings] = load_settings,
    out: Callable[[str], object] = print,
) -> int:
    """Print the report; 1 if anything failed, else 0."""
    checks = run_checks(load)
    out(render(checks))
    return 1 if any(check.status is Status.FAIL for check in checks) else 0
