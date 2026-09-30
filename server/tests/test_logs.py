from __future__ import annotations

import io
import json
import logging
import sys

import pytest

from textwire.config import LogFormat
from textwire.logs import (
    ConsoleFormatter,
    JsonFormatter,
    configure_logging,
    mask_number,
    scrub,
)


def _record(message: str, *args: object, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("textwire.test", logging.INFO, __file__, 1, message, args, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


@pytest.mark.parametrize(
    ("number", "masked"),
    [("+447700900123", "+44...0123"), ("447700900123", "+44...0123"), ("+12345", "+***")],
)
def test_numbers_are_masked_to_two_and_four_digits(number: str, masked: str) -> None:
    assert mask_number(number) == masked


def test_scrub_masks_every_number_in_a_line() -> None:
    assert scrub("from +447700900123 to +447700900000") == "from +44...0123 to +44...0000"


def test_scrub_leaves_short_digit_runs_alone() -> None:
    assert scrub("page +12 of 30") == "page +12 of 30"


def test_json_lines_carry_the_fixed_fields_and_extras() -> None:
    line = JsonFormatter().format(_record("sent %s frames", 12, tag="a7", to="+447700900123"))
    payload = json.loads(line)
    assert payload["event"] == "sent 12 frames"
    assert payload["level"] == "info"
    assert payload["logger"] == "textwire.test"
    assert payload["tag"] == "a7"
    assert payload["to"] == "+44...0123"
    assert payload["ts"].endswith("+00:00")


def test_json_lines_mask_numbers_in_the_message_and_keep_non_strings() -> None:
    payload = json.loads(JsonFormatter().format(_record("from +447700900123", frames=3)))
    assert payload["event"] == "from +44...0123"
    assert payload["frames"] == 3


def test_json_lines_describe_exceptions_without_leaking_numbers() -> None:
    try:
        raise ValueError("bad sender +447700900123")  # noqa: TRY301
    except ValueError:
        record = _record("failed")
        record.exc_info = sys.exc_info()
    payload = json.loads(JsonFormatter().format(record))
    assert payload["error"] == "ValueError"
    assert "+44...0123" in payload["traceback"]
    assert "+447700900123" not in payload["traceback"]


def test_console_lines_are_readable_and_masked() -> None:
    line = ConsoleFormatter().format(_record("to %s", "+447700900123", tag="a7", frames=2))
    assert line.endswith("INFO    textwire.test: to +44...0123 frames=2 tag=a7")


def test_console_lines_without_extras_have_no_trailing_space() -> None:
    assert ConsoleFormatter().format(_record("hello")).endswith("textwire.test: hello")


@pytest.mark.parametrize(("fmt", "starts"), [(LogFormat.JSON, "{"), (LogFormat.CONSOLE, "")])
def test_configure_logging_routes_records_to_the_stream(fmt: LogFormat, starts: str) -> None:
    stream = io.StringIO()
    configure_logging("debug", fmt, stream)
    try:
        logging.getLogger("textwire.test").debug("hello %s", "+447700900123")
        assert stream.getvalue().startswith(starts)
        assert "+44...0123" in stream.getvalue()
        assert logging.getLogger("httpx").level == logging.WARNING
    finally:
        logging.getLogger().handlers.clear()


def test_configure_logging_defaults_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("info", LogFormat.CONSOLE)
    try:
        logging.getLogger("textwire.test").info("to stderr")
        assert "to stderr" in capsys.readouterr().err
    finally:
        logging.getLogger().handlers.clear()
