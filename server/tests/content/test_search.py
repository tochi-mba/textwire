from __future__ import annotations

import time
from typing import Any

import pytest
from ddgs.exceptions import DDGSException, RatelimitException

from textwire.content.search import DdgsSearchProvider, Hit, SearchError, SearchFault


class FakeDdgs:
    """Stands in for ddgs.DDGS: returns rows, or raises, and records the arguments."""

    def __init__(self, rows: list[dict[str, Any]] | Exception, delay: float = 0) -> None:
        self.rows = rows
        self.delay = delay
        self.calls: list[dict[str, Any]] = []

    def text(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append({"query": query, **kwargs})
        time.sleep(self.delay)
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows


def _provider(client: FakeDdgs, timeout: float = 5) -> DdgsSearchProvider:
    return DdgsSearchProvider(
        region="uk-en", backend="auto", timeout_seconds=timeout, client_factory=lambda: client
    )


async def test_results_become_hits_and_the_arguments_pass_through() -> None:
    client = FakeDdgs(
        [
            {"title": "A", "href": "https://a.example", "body": "first"},
            {"title": None, "href": "http://b.example", "body": None},
            {"title": "no link", "href": "", "body": "x"},
            {"title": "odd", "href": "ftp://c.example", "body": "x"},
        ]
    )
    hits = await _provider(client).search("weather", 5)
    assert hits == [Hit("A", "https://a.example", "first"), Hit("", "http://b.example", "")]
    assert client.calls == [
        {
            "query": "weather",
            "region": "uk-en",
            "safesearch": "moderate",
            "max_results": 5,
            "backend": "auto",
        }
    ]


async def test_results_are_capped_at_the_limit() -> None:
    rows = [{"title": str(n), "href": f"https://{n}.example", "body": ""} for n in range(8)]
    assert len(await _provider(FakeDdgs(rows)).search("x", 3)) == 3


async def test_no_results_is_an_empty_answer_not_an_error() -> None:
    assert await _provider(FakeDdgs(DDGSException("No results found."))).search("zzz", 5) == []


async def test_engine_failures_are_search_errors() -> None:
    with pytest.raises(SearchError) as caught:
        await _provider(FakeDdgs(RatelimitException("202 Ratelimit"))).search("x", 5)
    assert caught.value.fault is SearchFault.FAILED
    assert caught.value.status_text == "E search failed"


async def test_a_slow_search_times_out() -> None:
    with pytest.raises(SearchError) as caught:
        await _provider(FakeDdgs([], delay=0.5), timeout=0.05).search("x", 5)
    assert caught.value.status_text == "E search timeout"


def test_the_default_client_is_ddgs() -> None:
    provider = DdgsSearchProvider(region="uk-en", backend="auto", timeout_seconds=7.9)
    client = provider._factory()
    assert type(client).__name__ == "DDGS"
