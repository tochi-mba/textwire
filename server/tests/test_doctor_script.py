"""`make doctor` (tools/doctor.sh) tells a new machine what it is missing, and fails only for
what the server needs. Run here against stand-in tools so the answer does not depend on the
machine the tests are on."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "tools" / "doctor.sh"


def _doctor(tmp_path: Path, tools: dict[str, int]) -> subprocess.CompletedProcess[str]:
    """Run the script in an empty repository whose PATH holds only these tools.

    Each tool is a one-line shell script that exits with the given status.
    """
    shell = shutil.which("sh")
    if shell is None:
        pytest.skip("no POSIX shell on this machine; make doctor needs one too")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, status in tools.items():
        tool = bin_dir / name
        tool.write_text(f"#!/bin/sh\nexit {status}\n", encoding="utf-8", newline="\n")
        tool.chmod(0o755)
    (tmp_path / "server").mkdir()
    return subprocess.run(  # noqa: S603 - fixed arguments
        [shell, str(SCRIPT)],
        cwd=tmp_path,
        env={"PATH": str(bin_dir), "ANDROID_HOME": "", "ANDROID_SDK_ROOT": ""},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _rows(output: str) -> dict[str, str]:
    """Each row's name mapped to its verdict: ok, warn or fail."""
    rows: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if parts and parts[0] in {"ok", "warn", "fail"}:
            name = line[8:30].strip()
            rows[name] = parts[0]
    return rows


def test_a_machine_with_the_server_tools_passes_and_is_warned_about_the_rest(
    tmp_path: Path,
) -> None:
    result = _doctor(tmp_path, {"git": 0, "make": 0, "uv": 0})
    rows = _rows(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {rows[name] for name in ("git", "make", "uv")} == {"ok"}
    # The Android tools and Node are wanted, not needed: the server works without them.
    assert {rows[name] for name in ("java", "adb", "node", "android sdk")} == {"warn"}


def test_a_bare_machine_fails_and_names_the_fix_for_each_gap(tmp_path: Path) -> None:
    result = _doctor(tmp_path, {})
    rows = _rows(result.stdout)
    assert result.returncode == 1
    assert {rows[name] for name in ("git", "make", "uv", "server")} == {"fail"}
    for fix in ("winget install Git.Git", "winget install ezwinports.make", "astral-sh.uv"):
        assert fix in result.stdout
    assert "install uv first" in result.stdout


def test_a_server_that_fails_its_own_checks_fails_the_doctor(tmp_path: Path) -> None:
    result = _doctor(tmp_path, {"git": 0, "make": 0, "uv": 1})
    assert result.returncode == 1
    assert _rows(result.stdout)["uv"] == "ok"


def test_the_script_changes_nothing(tmp_path: Path) -> None:
    _doctor(tmp_path, {"git": 0, "make": 0, "uv": 0})
    assert sorted(path.name for path in tmp_path.iterdir()) == ["bin", "server"]
    assert list((tmp_path / "server").iterdir()) == []
