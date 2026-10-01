"""The Pages site is checked before it is published, and the shipped site passes."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

check_site = pytest.importorskip("check_site")

GOOD = """<!doctype html><html lang="en"><head><title>Thing - REX Technologies</title>
<meta name="description" content="A thing.">
<link rel="stylesheet" href="styles.css"></head>
<body><a href="#top">top</a><main id="top"><h1>Thing</h1><img src="mark.svg" alt="">
<a href="https://github.com/tochi-mba/Thing">source</a> <a href="./">home</a>
<a href="handbook/docs/ONBOARDING/#install">guide</a> <a href="mailto:a@example.com">mail</a>
<code>make &amp;&amp; run</code><button data-copy="make && run">Copy</button></main>
<script src="app.js"></script></body></html>
"""


def _site(tmp_path: Path, html: str = GOOD, *, nojekyll: bool = True) -> Path:
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(html, encoding="utf-8")
    for name in ("styles.css", "app.js", "mark.svg"):
        (site / name).write_text("", encoding="utf-8")
    if nojekyll:
        (site / ".nojekyll").write_text("", encoding="utf-8")
    return site


def test_the_shipped_site_passes() -> None:
    assert check_site.check() == []


def test_the_shipped_site_is_the_one_in_this_repository() -> None:
    assert REPO_ROOT / "site" == check_site.SITE
    assert (check_site.SITE / "404.html").is_file()


def test_a_sound_site_has_no_problems(tmp_path: Path) -> None:
    assert check_site.check(_site(tmp_path), "Thing") == []


def test_a_missing_index_is_the_only_problem_worth_naming(tmp_path: Path) -> None:
    [problem] = check_site.check(tmp_path, "Thing")
    assert problem.endswith("is missing; there is no site to publish.")


@pytest.mark.parametrize(
    ("change", "said"),
    [
        (("<title>Thing", "<title>Other"), "the title does not name Thing."),
        (("REX Technologies", "Somebody"), "the page does not name REX Technologies."),
        ((' lang="en"', ""), "the html element has no lang attribute."),
        (("<h1>Thing</h1>", ""), "the page has 0 h1 headings; it needs exactly one."),
        (
            ("<h1>Thing</h1>", "<h1>Thing</h1><h1>Again</h1>"),
            "the page has 2 h1 headings; it needs exactly one.",
        ),
        (
            ('<meta name="description" content="A thing.">', ""),
            "the page has no meta description.",
        ),
        (
            ('href="styles.css"', 'href="missing.css"'),
            "asset 'missing.css' is referenced but missing.",
        ),
        (
            ('href="#top"', 'href="#nowhere"'),
            "anchor '#nowhere' points at an id that does not exist.",
        ),
        (
            ('href="./"', 'href="pricing.html"'),
            "link 'pricing.html' points at a page that does not exist.",
        ),
        (
            ('<img src="mark.svg" alt="">', '<img src="mark.svg">'),
            "image 'mark.svg' has no alt text.",
        ),
        (
            ('data-copy="make && run"', 'data-copy="make && walk"'),
            "the Copy button beside 'make && run' copies 'make && walk' instead.",
        ),
        (("source</a>", "source</a> coming soon"), "draft text left in the page: 'coming soon'."),
        (
            ("github.com/tochi-mba/Thing", "github.com/somebody-else/Thing"),
            "the page links to GitHub owners other than tochi-mba: ['somebody-else'].",
        ),
    ],
)
def test_each_kind_of_problem_is_named(tmp_path: Path, change: tuple[str, str], said: str) -> None:
    old, new = change
    assert old in GOOD
    problems = check_site.check(_site(tmp_path, GOOD.replace(old, new)), "Thing")
    assert problems == [f"index.html: {said}"]


def test_a_site_without_nojekyll_is_named(tmp_path: Path) -> None:
    [problem] = check_site.check(_site(tmp_path, nojekyll=False), "Thing")
    assert problem.startswith("site/.nojekyll is missing")


def test_every_page_is_checked_not_only_the_index(tmp_path: Path) -> None:
    site = _site(tmp_path)
    other = GOOD.replace("<title>Thing", "<title>Lost").replace(
        '<meta name="description" content="A thing.">', ""
    )
    (site / "404.html").write_text(other, encoding="utf-8")
    # Only the front page needs a description; every page needs the product in its title.
    assert check_site.check(site, "Thing") == ["404.html: the title does not name Thing."]


def test_remote_assets_and_empty_sources_are_not_checked_for_existence(tmp_path: Path) -> None:
    html = GOOD.replace(
        '<link rel="stylesheet" href="styles.css">',
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">'
        '<link rel="preconnect" href="//fonts.gstatic.com"><img src="" alt="">',
    )
    assert check_site.check(_site(tmp_path, html), "Thing") == []


def test_a_link_into_the_handbook_is_trusted_only_until_the_handbook_is_there(
    tmp_path: Path,
) -> None:
    site = _site(tmp_path)
    missing = (
        "index.html: link 'handbook/docs/ONBOARDING/#install' points at a page that does not exist."
    )
    # Nothing is generated in this site, so the same link is a problem.
    assert check_site.check(site, "Thing", generated=()) == [missing]
    # Once the folder exists, the page inside it has to exist too.
    (site / "handbook").mkdir()
    assert check_site.check(site, "Thing") == [missing]
    page = site / "handbook" / "docs" / "ONBOARDING"
    page.mkdir(parents=True)
    assert check_site.check(site, "Thing") == [missing]
    (page / "index.html").write_text("", encoding="utf-8")
    assert check_site.check(site, "Thing") == []


def test_main_reports_and_exits_as_a_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check_site.main([str(_site(tmp_path)), "Thing"]) == 0
    assert "site checks passed" in capsys.readouterr().out
    assert check_site.main([str(tmp_path), "Thing"]) == 1
    out = capsys.readouterr().out
    assert "1 problem(s) with the site:" in out
    assert "there is no site to publish" in out


def test_main_defaults_to_the_shipped_site(monkeypatch: pytest.MonkeyPatch) -> None:
    assert check_site.main([]) == 0
    monkeypatch.setattr(check_site.sys, "argv", ["check_site.py"])
    assert check_site.main() == 0
