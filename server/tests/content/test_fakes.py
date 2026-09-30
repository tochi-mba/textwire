from __future__ import annotations

import pytest

from tests.content.conftest import ARTICLE
from textwire.content.document import MAX_LINKS, Document
from textwire.content.fakes import FakeFetcher, FakeSearchProvider, html_page
from textwire.content.fetch import FetchError, FetchFault
from textwire.content.search import Hit, SearchError, SearchFault
from textwire.protocol.envelope import Kind


async def test_the_fake_fetcher_serves_its_table_and_records_requests() -> None:
    page = html_page("https://a.example", "<p>x</p>")
    fetcher = FakeFetcher(
        {"https://a.example": page, "https://b.example": FetchError(FetchFault.TIMEOUT)}
    )
    assert await fetcher.fetch("https://a.example") is page
    with pytest.raises(FetchError) as timeout:
        await fetcher.fetch("https://b.example")
    assert timeout.value.fault is FetchFault.TIMEOUT
    with pytest.raises(FetchError) as missing:
        await fetcher.fetch("https://c.example")
    assert missing.value.status_text == "E fetch status 404"
    assert fetcher.requested == ["https://a.example", "https://b.example", "https://c.example"]
    await fetcher.aclose()
    assert fetcher.closed


async def test_the_fake_search_serves_its_table_and_records_queries() -> None:
    hits = [Hit("a", "https://a.example", ""), Hit("b", "https://b.example", "")]
    search = FakeSearchProvider({"q": hits, "bad": SearchError(SearchFault.FAILED)})
    assert await search.search("q", 1) == hits[:1]
    assert await search.search("unknown", 5) == []
    with pytest.raises(SearchError):
        await search.search("bad", 5)
    assert search.queries == ["q", "unknown", "bad"]


async def test_the_recorded_fixtures_load(recorded: tuple[FakeFetcher, FakeSearchProvider]) -> None:
    fetcher, search = recorded
    assert (await fetcher.fetch(ARTICLE)).body.startswith(b"<!doctype html>")
    hits = await search.search("bbc weather london", 5)
    assert len(hits) == 5
    assert hits[0].url.startswith("https://")


def test_a_document_keeps_at_most_sixty_links() -> None:
    links = tuple(f"https://x.example/{n}" for n in range(MAX_LINKS + 1))
    with pytest.raises(ValueError, match="at most 60 links"):
        Document(kind=Kind.PAGE, title="t", body="b", links=links)
