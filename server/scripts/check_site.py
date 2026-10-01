#!/usr/bin/env python3
"""Check the GitHub Pages site before it is published.

A static site has no compiler, so nothing otherwise catches a broken anchor, a missing
asset, a link to a page that is not there, a Copy button that copies something other than
the command beside it, or draft text that escaped. This is that gate: the test suite runs
it on ``site/``, and ``build_site.py`` runs it again on the assembled site, handbook and all.

Standard library only, on purpose: checking a page with no build step should need nothing.

Usage::

    python scripts/check_site.py                       # the site in this repository
    python scripts/check_site.py path/to/site textwire  # any site, naming its product
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parents[2] / "site"
PRODUCT = "textwire"
OWNER = "tochi-mba"
"""Every GitHub link on a REX site points at this owner; anything else is a stale copy."""

GENERATED = ("handbook/",)
"""Folders the build adds beside the landing page. A link into one is checked once the
folder is there (the assembled site) and taken on trust while it is not (``site/`` alone)."""

FORBIDDEN_PATTERNS = (
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bTBD\b",
    r"\bLorem ipsum\b",
    r"\bXXX\b",
    r"\bcoming soon\b",
)
"""Text that means a draft escaped."""

REMOTE = ("http://", "https://", "data:", "//", "mailto:")


class PageParser(HTMLParser):
    """Collects the ids, links, assets and commands a page depends on."""

    def __init__(self) -> None:
        """Start with nothing collected."""
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.assets: list[str] = []
        self.title = ""
        self.lang = ""
        self.description = ""
        self.headings = 0
        self.images_without_alt: list[str] = []
        self.copies: list[tuple[str, str]] = []
        self._in_title = False
        self._in_code = False
        self._code = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record what the tag refers to."""
        values = {key: (value or "") for key, value in attrs}
        if "id" in values:
            self.ids.add(values["id"])
        if tag == "html":
            self.lang = values.get("lang", "")
        if tag == "meta" and values.get("name") == "description":
            self.description = values.get("content", "")
        if tag == "h1":
            self.headings += 1
        if tag == "title":
            self._in_title = True
        if tag == "code":
            self._in_code = True
            self._code = ""
        if tag == "a" and "href" in values:
            self.hrefs.append(values["href"])
        if tag == "img":
            self.assets.append(values.get("src", ""))
            # An explicitly empty alt marks an image decorative; a missing one does not.
            if "alt" not in values:
                self.images_without_alt.append(values.get("src") or "(no src)")
        if tag == "link" and "href" in values:
            self.assets.append(values["href"])
        if tag == "script" and values.get("src"):
            self.assets.append(values["src"])
        if "data-copy" in values:
            # A Copy button copies the command shown in the <code> just before it.
            self.copies.append((self._code, values["data-copy"]))

    def handle_endtag(self, tag: str) -> None:
        """Leave the title or the code element."""
        if tag == "title":
            self._in_title = False
        if tag == "code":
            self._in_code = False

    def handle_data(self, data: str) -> None:
        """Gather the title's and the current command's text."""
        if self._in_title:
            self.title += data
        if self._in_code:
            self._code += data


def check(
    site: Path = SITE, product: str = PRODUCT, generated: tuple[str, ...] = GENERATED
) -> list[str]:
    """Every problem with the site. Empty means it is publishable."""
    if not (site / "index.html").exists():
        return [f"{site / 'index.html'} is missing; there is no site to publish."]
    problems: list[str] = []
    if not (site / ".nojekyll").exists():
        problems.append(
            "site/.nojekyll is missing: without it Pages runs the site through Jekyll, "
            "which drops files beginning with an underscore."
        )
    for page in sorted(site.glob("*.html")):
        problems.extend(
            f"{page.name}: {problem}" for problem in _check_page(page, product, generated)
        )
    return problems


def _check_page(page: Path, product: str, generated: tuple[str, ...]) -> list[str]:
    html = page.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(html)
    return [
        *_structure_problems(page, parser, html, product),
        *_reference_problems(page, parser, generated),
        *_text_problems(parser, html),
    ]


def _structure_problems(page: Path, parser: PageParser, html: str, product: str) -> list[str]:
    """What every page must say about itself."""
    problems: list[str] = []
    if product not in parser.title:
        problems.append(f"the title does not name {product}.")
    if "REX Technologies" not in html:
        problems.append("the page does not name REX Technologies.")
    if not parser.lang:
        problems.append("the html element has no lang attribute.")
    if parser.headings != 1:
        problems.append(f"the page has {parser.headings} h1 headings; it needs exactly one.")
    if page.name == "index.html" and not parser.description:
        problems.append("the page has no meta description.")
    return problems


def _reference_problems(page: Path, parser: PageParser, generated: tuple[str, ...]) -> list[str]:
    """Assets, anchors and links that lead nowhere."""
    problems = [
        f"asset '{asset}' is referenced but missing."
        for asset in parser.assets
        if asset
        and not asset.startswith(REMOTE)
        and not (page.parent / asset.split("?")[0]).exists()
    ]
    for href in parser.hrefs:
        if href.startswith("#"):
            if href[1:] and href[1:] not in parser.ids:
                problems.append(f"anchor '{href}' points at an id that does not exist.")
        elif not href.startswith(REMOTE) and not _resolves(page.parent, href, generated):
            problems.append(f"link '{href}' points at a page that does not exist.")
    return problems


def _text_problems(parser: PageParser, html: str) -> list[str]:
    """Missing alt text, Copy buttons that copy something else, drafts, and stale owners."""
    problems = [f"image '{image}' has no alt text." for image in parser.images_without_alt]
    problems.extend(
        f"the Copy button beside '{shown}' copies '{copied}' instead."
        for shown, copied in parser.copies
        if shown.strip() != copied.strip()
    )
    for pattern in FORBIDDEN_PATTERNS:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            problems.append(f"draft text left in the page: '{match.group(0)}'.")
    owners = set(re.findall(r"https://github\.com/([^/\"'\s]+)/", html))
    if owners - {OWNER}:
        problems.append(f"the page links to GitHub owners other than {OWNER}: {sorted(owners)}.")
    return problems


def _resolves(folder: Path, href: str, generated: tuple[str, ...]) -> bool:
    """Whether a relative link leads to a file, or to a folder with an index page."""
    path = re.split(r"[?#]", href, maxsplit=1)[0]
    for prefix in generated:
        if path.startswith(prefix) and not (folder / prefix).exists():
            return True
    target = folder / path
    if target.is_dir():
        return (target / "index.html").exists()
    return target.exists()


def main(argv: list[str] | None = None) -> int:
    """Check the site named on the command line, or this repository's."""
    args = sys.argv[1:] if argv is None else argv
    site = Path(args[0]) if args else SITE
    product = args[1] if len(args) > 1 else PRODUCT
    problems = check(site, product)
    if problems:
        print(f"{len(problems)} problem(s) with the site:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("site checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
