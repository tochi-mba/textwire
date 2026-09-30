from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.conftest import build_settings
from textwire.cli.doctor import (
    Check,
    Status,
    data_dir_check,
    doctor,
    python_check,
    render,
    run_checks,
    transport_check,
)
from textwire.config import Settings, TransportKind


def test_a_current_python_passes() -> None:
    assert python_check((3, 12, 10)) == Check("python", Status.OK, "3.12.10")


def test_an_old_python_fails_with_the_fix() -> None:
    check = python_check((3, 11, 9))
    assert check.status is Status.FAIL
    assert "uv python install" in check.detail


def test_a_writable_data_directory_is_created(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b"
    check = data_dir_check(target)
    assert check.status is Status.OK
    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_an_unwritable_data_directory_fails(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory", encoding="utf-8")
    check = data_dir_check(blocker / "data")
    assert check.status is Status.FAIL
    assert str(blocker / "data") in check.detail


def test_missing_credentials_are_a_warning_not_a_failure() -> None:
    check = transport_check(build_settings(twilio_account_sid=""))
    assert check == Check("twilio transport", Status.WARN, "TEXTWIRE_TWILIO_ACCOUNT_SID is not set")


def test_complete_credentials_pass_without_being_verified() -> None:
    check = transport_check(build_settings(transport=TransportKind.TWILIO))
    assert check == Check("twilio transport", Status.OK, "configured (not verified)")


def test_run_checks_covers_python_configuration_data_and_transport(tmp_path: Path) -> None:
    checks = run_checks(lambda: build_settings(data_dir=tmp_path))
    assert [check.name for check in checks] == [
        "python",
        "configuration",
        "data directory",
        "twilio transport",
    ]
    assert all(check.status is Status.OK for check in checks)


def test_a_configuration_error_stops_the_checks_with_the_reason() -> None:
    def broken() -> Settings:
        return build_settings(page_frames=0)

    checks = run_checks(broken)
    assert [check.name for check in checks] == ["python", "configuration"]
    assert checks[1].status is Status.FAIL
    assert "page_frames" in checks[1].detail
    assert "\n" not in checks[1].detail


def test_an_unknown_variable_is_reported_as_a_configuration_failure() -> None:
    def typo() -> Settings:
        raise RuntimeError("unknown environment variables: TEXTWIRE_TYPO")

    checks = run_checks(typo)
    assert checks[1] == Check(
        "configuration", Status.FAIL, "unknown environment variables: TEXTWIRE_TYPO"
    )


def test_render_aligns_the_columns() -> None:
    text = render([Check("python", Status.OK, "3.12"), Check("data directory", Status.FAIL, "x")])
    assert text.splitlines() == [
        "  ok    python          3.12",
        "  fail  data directory  x",
    ]


def test_doctor_prints_the_report_and_passes(tmp_path: Path) -> None:
    printed: list[str] = []
    status = doctor(lambda: build_settings(data_dir=tmp_path), printed.append)
    assert status == 0
    assert "configuration" in printed[0]


def test_doctor_fails_when_a_check_fails() -> None:
    def broken() -> Settings:
        raise ValidationError.from_exception_data("Settings", [])

    assert doctor(broken, lambda _line: None) == 1


def test_doctor_by_default_reads_the_real_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert doctor() == 0
    assert "twilio transport" in capsys.readouterr().out
