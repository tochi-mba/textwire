from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

scripts = pytest.importorskip("build_site")

_LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def test_the_readme_becomes_the_front_page_and_paths_are_kept() -> None:
    pages = scripts.staged_pages(REPO_ROOT)
    assert pages["index.md"] == REPO_ROOT / "README.md"
    assert "README.md" not in pages
    assert pages["docs/adr/0001-monorepo-protocol-server-android.md"].exists()
    assert pages["protocol/PROTOCOL.md"] == REPO_ROOT / "protocol" / "PROTOCOL.md"
    assert all(source.exists() for source in pages.values())


def test_every_page_in_the_nav_is_staged() -> None:
    nav = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    listed = re.findall(r":\s+([\w./-]+\.md)\s*$", nav, re.MULTILINE)
    staged = scripts.staged_pages(REPO_ROOT)
    assert listed
    assert [page for page in listed if page not in staged] == []


def test_every_staged_page_is_in_the_nav_or_a_dependency() -> None:
    nav = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    missing = [
        page for page in scripts.staged_pages(REPO_ROOT) if page.endswith(".md") and page not in nav
    ]
    assert missing == []


def test_relative_links_between_staged_pages_resolve(tmp_path: Path) -> None:
    into = tmp_path / "site-src"
    paths = scripts.stage(REPO_ROOT, into)
    assert "index.md" in paths
    broken: list[str] = []
    for page in paths:
        if not page.endswith(".md"):
            continue
        text = (into / page).read_text(encoding="utf-8")
        for target in _LINK.findall(text):
            if "://" in target or target.startswith("mailto:"):
                continue
            if not ((into / page).parent / target).resolve().exists():
                broken.append(f"{page} -> {target}")
    assert broken == []


def test_links_to_the_readme_point_at_the_front_page(tmp_path: Path) -> None:
    into = tmp_path / "site-src"
    scripts.stage(REPO_ROOT, into)
    server_readme = (into / "server" / "README.md").read_text(encoding="utf-8")
    assert "](../index.md)" in server_readme
    assert "](../README.md)" not in server_readme
    assert "](docs/ONBOARDING.md)" in (into / "index.md").read_text(encoding="utf-8")


def test_staging_replaces_a_previous_copy(tmp_path: Path) -> None:
    into = tmp_path / "site-src"
    into.mkdir()
    (into / "stale.md").write_text("old", encoding="utf-8")
    scripts.stage(REPO_ROOT, into)
    assert not (into / "stale.md").exists()


def test_stage_only_from_the_command_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(scripts, "STAGE", tmp_path / "staged")
    assert scripts.main(["--stage"]) == 0
    assert "staged" in capsys.readouterr().out
    assert (tmp_path / "staged" / "index.md").exists()


def test_build_runs_mkdocs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    class Done:
        returncode = 0

    def fake_run(command: list[str], **_kwargs: object) -> Done:
        calls.append(command)
        return Done()

    monkeypatch.setattr(scripts, "STAGE", tmp_path / "staged")
    monkeypatch.setattr(scripts.subprocess, "run", fake_run)
    assert scripts.main([]) == 0
    assert scripts.main(["--serve"]) == 0
    assert [command[-2] for command in calls] == ["build", "serve"]
    assert all(command[-1] == "--strict" for command in calls)
