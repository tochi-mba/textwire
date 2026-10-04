#!/usr/bin/env python3
"""Build the GitHub Pages site: the landing page in ``site/`` and the handbook under it.

Usage (from ``server/``)::

    uv run python scripts/build_site.py            # build the whole site into ../build/site
    uv run python scripts/build_site.py --serve    # serve the handbook with live reload
    uv run python scripts/build_site.py --stage    # stage the handbook's pages only

The handbook is the repository's own Markdown. The pages are copied into ``build/site-src``
with their paths kept, so every relative link between them works exactly as it does on
GitHub, and ``mkdocs build --strict`` fails on any link that does not resolve. ``README.md``
becomes ``index.md``; everything else keeps its name. MkDocs writes the handbook into
``build/site/handbook``, the landing page's files are copied in beside it, and
``check_site`` then checks the result, so a link from the landing page into the handbook
that does not resolve fails the build.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import check_site

REPO = Path(__file__).resolve().parents[2]
STAGE = REPO / "build" / "site-src"
#: The landing page: static files published as they are.
SITE = REPO / "site"
#: The assembled site, as Pages serves it. MkDocs writes the handbook into ``OUT/handbook``.
OUT = REPO / "build" / "site"

#: Files published, relative to the repository root. README.md is renamed to index.md.
PAGES = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "LICENSE",
    "server/README.md",
    "protocol/PROTOCOL.md",
    "protocol/dict/README.md",
    "protocol/fixtures/README.md",
    "benchmarks/README.md",
    "docs/stylesheets/rex.css",
    "site/favicon.svg",
)
#: Folders published whole (Markdown only).
FOLDERS = ("docs",)
#: Where a link to a file the site does not publish leads instead.
SOURCE = "https://github.com/tochi-mba/textwire/blob/main/"
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
    """The page's text with its links made to work on the site.

    A link to the repository README points at the site's index, and a link to a file the
    site does not publish (source code, ``.env.example``) points at that file on GitHub.
    """
    readme = (repo / "README.md").resolve()
    published = {source.resolve() for source in staged_pages(repo).values()}

    def rewrite(match: re.Match[str]) -> str:
        target = match.group(1)
        if "://" in target or target.startswith("mailto:"):
            return target
        resolved = (page.parent / target).resolve()
        if resolved == readme:
            return target[: -len("README.md")] + "index.md"
        if resolved not in published and resolved.is_file():
            return SOURCE + resolved.relative_to(repo.resolve()).as_posix()
        return target

    return _LINK.sub(rewrite, page.read_text(encoding="utf-8"))


def assemble(site: Path, out: Path) -> list[str]:
    """Copy the landing page's files into ``out``, beside the handbook; return their names."""
    out.mkdir(parents=True, exist_ok=True)
    names = sorted(source.name for source in site.iterdir() if source.is_file())
    for name in names:
        shutil.copyfile(site / name, out / name)
    return names


def main(argv: list[str] | None = None) -> int:
    """Stage, then build the whole site or serve the handbook unless ``--stage`` only."""
    parser = argparse.ArgumentParser(description="build the GitHub Pages site")
    parser.add_argument("--serve", action="store_true", help="serve the handbook, live reload")
    parser.add_argument("--stage", action="store_true", help="stage only; do not run mkdocs")
    args = parser.parse_args(argv)
    paths = stage(REPO, STAGE)
    print(f"staged {len(paths)} files into {STAGE}")
    if args.stage:
        return 0
    mkdocs = [sys.executable, "-m", "mkdocs"]
    if args.serve:
        return subprocess.run([*mkdocs, "serve", "--strict"], cwd=REPO, check=False).returncode  # noqa: S603 - fixed arguments
    if OUT.exists():
        shutil.rmtree(OUT)
    built = subprocess.run([*mkdocs, "build", "--strict"], cwd=REPO, check=False).returncode  # noqa: S603 - fixed arguments
    if built:
        return built
    names = assemble(SITE, OUT)
    print(f"copied {len(names)} landing page files into {OUT}")
    # Nothing is taken on trust now: the handbook is there, so every link into it must resolve.
    problems = check_site.check(OUT, generated=())
    for problem in problems:
        print(f"  - {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
