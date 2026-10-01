#!/usr/bin/env python3
"""Stage the repository's documentation for MkDocs and build the site.

Usage (from ``server/``)::

    uv run python scripts/build_site.py            # stage and build into ../build/site
    uv run python scripts/build_site.py --serve    # stage and serve with live reload
    uv run python scripts/build_site.py --stage    # stage only (what the tests exercise)

The site is the repository's own Markdown. The pages are copied into ``build/site-src`` with
their paths kept, so every relative link between them works exactly as it does on GitHub,
and ``mkdocs build --strict`` fails on any link that does not resolve. ``README.md`` becomes
``index.md``; everything else keeps its name.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STAGE = REPO / "build" / "site-src"

#: Files published, relative to the repository root. README.md is renamed to index.md.
PAGES = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "LICENSE",
    "server/README.md",
    "server/.env.example",
    "protocol/PROTOCOL.md",
    "protocol/dict/README.md",
    "protocol/fixtures/README.md",
)
#: Folders published whole (Markdown only).
FOLDERS = ("docs",)
#: A Markdown link's target, without any fragment.
_LINK = re.compile(r"(?<=\]\()([^)#\s]+)")


def staged_pages(repo: Path) -> dict[str, Path]:
    """Every published file: its path on the site mapped to its source."""
    pages: dict[str, Path] = {}
    for relative in PAGES:
        source = repo / relative
        target = "index.md" if relative == "README.md" else relative
        pages[target] = source
    for folder in FOLDERS:
        for source in sorted((repo / folder).rglob("*.md")):
            pages[source.relative_to(repo).as_posix()] = source
    return pages


def stage(repo: Path, into: Path) -> list[str]:
    """Copy the published files into ``into`` (emptied first); return their site paths."""
    if into.exists():
        shutil.rmtree(into)
    staged = staged_pages(repo)
    for target, source in staged.items():
        destination = into / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        if target.endswith(".md"):
            destination.write_text(rewrite_links(source, repo), encoding="utf-8")
        else:
            shutil.copyfile(source, destination)
    return sorted(staged)


def rewrite_links(page: Path, repo: Path) -> str:
    """The page's text with links to the repository README pointing at the site's index."""
    readme = (repo / "README.md").resolve()

    def rewrite(match: re.Match[str]) -> str:
        target = match.group(1)
        if "://" in target or target.startswith("mailto:"):
            return target
        if (page.parent / target).resolve() == readme:
            return target[: -len("README.md")] + "index.md"
        return target

    return _LINK.sub(rewrite, page.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Stage, then build or serve unless ``--stage`` only."""
    parser = argparse.ArgumentParser(description="stage and build the documentation site")
    parser.add_argument("--serve", action="store_true", help="serve with live reload")
    parser.add_argument("--stage", action="store_true", help="stage only; do not run mkdocs")
    args = parser.parse_args(argv)
    paths = stage(REPO, STAGE)
    print(f"staged {len(paths)} files into {STAGE}")
    if args.stage:
        return 0
    command = [sys.executable, "-m", "mkdocs", "serve" if args.serve else "build", "--strict"]
    return subprocess.run(command, cwd=REPO, check=False).returncode  # noqa: S603 - fixed arguments


if __name__ == "__main__":
    raise SystemExit(main())
