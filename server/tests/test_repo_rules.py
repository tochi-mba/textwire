"""Rules about the repository itself, checked on every run so they cannot rot."""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, SERVER_ROOT
from textwire import __version__

MAX_LINES = 800
PRAGMA = "pragma: " + "no cover"  # split so this file does not trip its own rule


def _python_files() -> list[Path]:
    return sorted(
        path
        for folder in ("src", "tests", "scripts")
        for path in (SERVER_ROOT / folder).rglob("*.py")
    )


def test_python_files_stay_under_the_line_ceiling() -> None:
    too_long = {
        str(path.relative_to(SERVER_ROOT)): lines
        for path in _python_files()
        if (lines := len(path.read_text(encoding="utf-8").splitlines())) > MAX_LINES
    }
    assert too_long == {}


def test_no_coverage_pragmas_anywhere() -> None:
    offenders = [
        str(path.relative_to(SERVER_ROOT))
        for path in _python_files()
        if PRAGMA in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_every_version_agrees() -> None:
    project = tomllib.loads((SERVER_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version_file = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert project["project"]["version"] == version_file == __version__


def test_every_adr_is_listed_in_the_index() -> None:
    index = (REPO_ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
    adrs = sorted(
        path.name for path in (REPO_ROOT / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")
    )
    assert adrs, "no ADRs found"
    missing = [name for name in adrs if f"({name})" not in index]
    assert missing == []


def test_adr_numbers_are_unique_and_contiguous() -> None:
    numbers = sorted(
        int(path.name[:4])
        for path in (REPO_ROOT / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")
    )
    assert numbers == list(range(1, len(numbers) + 1))


def test_the_changelog_follows_keep_a_changelog() -> None:
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "keepachangelog.com" in changelog
    assert re.search(r"^## \[Unreleased\]$", changelog, re.MULTILINE)


def test_markdown_links_between_repository_files_resolve() -> None:
    broken: list[str] = []
    for document in sorted(REPO_ROOT.glob("*.md")) + sorted((REPO_ROOT / "docs").rglob("*.md")):
        text = document.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            if "://" in target or target.startswith("mailto:"):
                continue
            if not (document.parent / target).exists():
                broken.append(f"{document.relative_to(REPO_ROOT)} -> {target}")
    assert broken == []


def test_every_source_file_is_tracked_by_git() -> None:
    """A gitignore rule once hid a source package named data; CI saw a repo missing files."""
    git = shutil.which("git")
    if git is None or not (REPO_ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    tracked = set(
        subprocess.run(  # noqa: S603 - fixed arguments
            [git, "-C", str(REPO_ROOT), "ls-files", "-z"], capture_output=True, check=True
        )
        .stdout.decode("utf-8")
        .split("\0")
    )
    roots = [SERVER_ROOT / "src", *sorted((REPO_ROOT / "android").glob("*/src"))]
    untracked = [
        path.relative_to(REPO_ROOT).as_posix()
        for root in roots
        for path in root.rglob("*")
        if path.is_file()
        and not ({"build", "__pycache__"} & set(path.parts))
        and path.relative_to(REPO_ROOT).as_posix() not in tracked
    ]
    assert untracked == []
