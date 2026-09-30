"""Logging: JSON lines for machines, one readable line for people, masked numbers for both.

Call sites mask phone numbers themselves with :func:`mask_number`. The formatters scrub
every rendered line as well, so a number that slips into a message or an exception still
reaches the log masked.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from textwire.config import LogFormat

if TYPE_CHECKING:
    from typing import TextIO

_NUMBER = re.compile(r"\+\d{7,15}")

#: Loggers from dependencies that narrate every request at INFO.
_NOISY = ("httpx", "httpcore", "trafilatura", "ddgs", "primp", "hpack", "urllib3")

# Attributes every LogRecord has; anything else on a record came from ``extra=``.
_RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
}


def mask_number(number: str) -> str:
    """Mask a phone number to its first two and last four digits: ``+44...1234``."""
    digits = number.removeprefix("+")
    if len(digits) < 7:  # noqa: PLR2004 - shorter than any real E.164 number
        return "+***"
    return f"+{digits[:2]}...{digits[-4:]}"


def scrub(text: str) -> str:
    """Mask every E.164-looking number in ``text``."""
    return _NUMBER.sub(lambda match: mask_number(match.group(0)), text)


def _extras(record: logging.LogRecord) -> dict[str, object]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    """One JSON object per line with a fixed core and any ``extra=`` fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` as a JSON line."""
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": scrub(record.getMessage()),
        }
        for key, value in _extras(record).items():
            payload[key] = scrub(value) if isinstance(value, str) else value
        if record.exc_info and record.exc_info[0] is not None:
            payload["error"] = record.exc_info[0].__name__
            payload["traceback"] = scrub(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False, sort_keys=True)


class ConsoleFormatter(logging.Formatter):
    """``12:00:00 INFO    textwire.x: event key=value`` for a person at a terminal."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` as one scrubbed line, extras appended as ``key=value``."""
        line = super().format(record)
        extras = _extras(record)
        if extras:
            line += " " + " ".join(f"{key}={value}" for key, value in sorted(extras.items()))
        return scrub(line)


def configure_logging(level: str, fmt: LogFormat, stream: TextIO | None = None) -> None:
    """Send every log record to ``stream`` (stderr by default) in the chosen format."""
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(JsonFormatter() if fmt is LogFormat.JSON else ConsoleFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)
