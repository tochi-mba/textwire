from __future__ import annotations

import pytest
import trafilatura

from tests.content.conftest import ARTICLE, NOTES, WIKIPEDIA
from textwire.content.extract import (
    MAX_BODY_CHARS,
    ExtractError,
    ExtractFault,
    extract_document,
)
from textwire.content.fakes import FakeFetcher, FakeSearchProvider, html_page
from textwire.content.fetch import Fetched
from textwire.protocol.envelope import Kind


async def test_the_article_fixture_reads_like_the_article(
    recorded: tuple[FakeFetcher, FakeSearchProvider],
) -> None:
    fetcher, _ = recorded
    document = extract_document(await fetcher.fetch(ARTICLE))
    assert document.kind is Kind.PAGE
    assert document.title == "Village gets its first text-only library"
    assert document.source == ARTICLE
    assert document.body.startswith("Residents of Dunmore, a hill village")
    assert (
        '"People here have phones, they just don\'t have data," said Morag Keir[1]' in document.body
    )
    assert "## How it works" in document.body
    assert "- Search the web by texting a few words" in document.body
    assert "1. A search usually takes four messages." in document.body
    assert "longer interview[1]" in document.body
    assert document.links == (
        "https://example.org/people/morag-keir",
        "https://dunmore-gazette.example/features/sms-history",
        "https://example.org/council",
    )
    for noise in (
        "Home",
        "Most read",
        "Back to top",
        "cite",
        "mailto",
        "javascript",
        "library.jpg",
    ):
        assert noise not in document.body


async def test_the_wikipedia_fixture_keeps_sixty_links_and_no_citations(
    recorded: tuple[FakeFetcher, FakeSearchProvider],
) -> None:
    fetcher, _ = recorded
    document = extract_document(await fetcher.fetch(WIKIPEDIA))
    assert document.title == "SMS gateway"
    assert document.body.startswith("An SMS gateway is used to bridge")
    assert len(document.links) == 60
    assert all(link.startswith(("http://", "https://")) for link in document.links)
    assert "cite_note" not in "".join(document.links)


async def test_plain_text_passes_through_with_joined_lines(
    recorded: tuple[FakeFetcher, FakeSearchProvider],
) -> None:
    fetcher, _ = recorded
    document = extract_document(await fetcher.fetch(NOTES))
    assert document.title == "reading-by-text.txt"
    assert document.body.splitlines()[0] == "Notes on reading the web by text message"
    assert "reduced to its words, compressed, and sent" in document.body


@pytest.fixture
def no_trafilatura(monkeypatch: pytest.MonkeyPatch) -> None:
    """trafilatura reads almost anything, so the fallback is reached by making it give up."""
    monkeypatch.setattr(trafilatura, "extract", lambda *_args, **_kwargs: None)


@pytest.mark.usefixtures("no_trafilatura")
def test_a_page_trafilatura_cannot_read_falls_back_to_its_paragraphs() -> None:
    html = (
        "<html><head><title> Tiny </title><script>var x = 1;</script></head><body>"
        "<nav><p>Menu <a href='/m'>m</a></p></nav><h1>Tiny page</h1>"
        "<p>One <a href='/two'>link</a> here.<a>bare</a></p>"
        "<ul><li>item</li><li> </li></ul><footer><p>foot</p></footer></body></html>"
    )
    document = extract_document(html_page("https://tiny.example/a", html))
    assert document.title == "Tiny page"
    assert document.body == "One link[1] here.bare\n\n- item"
    assert document.links == ("https://tiny.example/two",)


@pytest.mark.usefixtures("no_trafilatura")
def test_the_fallback_uses_the_title_element_when_there_is_no_heading() -> None:
    html = (
        "<html><head><title>Only a title</title></head>"
        "<body><p>x</p><span>loose</span></body></html>"
    )
    document = extract_document(html_page("https://tiny.example/", html))
    assert (document.title, document.body) == ("Only a title", "x")


@pytest.mark.usefixtures("no_trafilatura")
def test_the_host_names_a_page_with_no_title_at_all() -> None:
    document = extract_document(html_page("https://www.tiny.example/", "<p>just text</p>"))
    assert document.title == "tiny.example"


def test_metadata_names_a_page_whose_text_has_no_heading() -> None:
    paragraphs = "".join(f"<p>Paragraph number {n} of the body text.</p>" for n in range(5))
    html = "<html><head><title>From metadata</title></head><body>" + paragraphs
    document = extract_document(html_page("https://tiny.example/", html + "</body></html>"))
    assert document.title == "From metadata"


def test_a_page_without_metadata_is_named_by_its_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trafilatura, "extract_metadata", lambda *_a, **_k: None)
    paragraphs = "".join(f"<p>Paragraph number {n} of the body text.</p>" for n in range(5))
    html = "<html><body>" + paragraphs + "</body></html>"
    assert extract_document(html_page("https://tiny.example/", html)).title == "tiny.example"


def test_a_page_with_no_text_is_empty() -> None:
    with pytest.raises(ExtractError) as caught:
        extract_document(html_page("https://x.example/", "<html><body></body></html>"))
    assert caught.value.fault is ExtractFault.EMPTY
    assert caught.value.status_text == "E extract empty"


def test_an_empty_text_file_is_empty() -> None:
    fetched = Fetched(
        "https://x.example/a.txt", "https://x.example/a.txt", 200, "text/plain", b" \n"
    )
    with pytest.raises(ExtractError):
        extract_document(fetched)


def test_other_content_types_are_unsupported() -> None:
    fetched = Fetched(
        "https://x.example/a.pdf", "https://x.example/a.pdf", 200, "application/pdf", b"%PDF"
    )
    with pytest.raises(ExtractError) as caught:
        extract_document(fetched)
    assert caught.value.status_text == "E extract unsupported application/pdf"


@pytest.mark.parametrize(
    ("body", "title"),
    [
        (b"<!DOCTYPE html><title>Sniffed</title><p>hello there</p>", "Sniffed"),
        (b"plain words", "x.example"),
    ],
)
def test_a_missing_content_type_is_sniffed(body: bytes, title: str) -> None:
    document = extract_document(Fetched("https://x.example/", "https://x.example/", 200, "", body))
    assert document.title == title


def test_the_declared_charset_is_used() -> None:
    html = "<html><body><p>Caf\N{LATIN SMALL LETTER E WITH ACUTE} society</p></body></html>"
    fetched = Fetched(
        "https://x.example/",
        "https://x.example/",
        200,
        "text/html; charset=latin-1",
        html.encode("latin-1"),
    )
    assert "Caf\N{LATIN SMALL LETTER E WITH ACUTE}" in extract_document(fetched).body


def test_very_long_pages_are_cut_with_a_note() -> None:
    paragraphs = "\n\n".join(f"Paragraph {n} " + "word " * 50 for n in range(400))
    fetched = Fetched(
        "https://x.example/l.txt", "https://x.example/l.txt", 200, "text/plain", paragraphs.encode()
    )
    document = extract_document(fetched)
    assert len(document.body) <= MAX_BODY_CHARS + 40
    assert document.body.endswith("(The rest of this page was cut.)")


def test_a_single_enormous_paragraph_is_cut_at_the_limit() -> None:
    fetched = Fetched(
        "https://x.example/l.txt", "https://x.example/l.txt", 200, "text/plain", b"x" * 70_000
    )
    body = extract_document(fetched).body
    assert body.startswith("x" * MAX_BODY_CHARS)
    assert body.endswith("cut.)")
