"""Fakes for the content pipeline's outside world, and the recorded fixtures they serve.

Tests use these directly. The offline simulator uses them with the fixtures in
``protocol/fixtures/``, whose ``index.json`` maps URLs and queries to recorded files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from textwire.content.fetch import Fetched, FetchError, FetchFault
from textwire.content.search import Hit, SearchError

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class FakeFetcher:
    """Answers from a table of URLs; anything else is a 404."""

    pages: dict[str, Fetched | FetchError] = field(default_factory=dict)
    requested: list[str] = field(default_factory=list)
    closed: bool = False

    async def fetch(self, url: str) -> Fetched:
        """The recorded answer for ``url``."""
        self.requested.append(url)
        answer = self.pages.get(url)
        if answer is None:
            raise FetchError(FetchFault.STATUS, "404")
        if isinstance(answer, FetchError):
            raise answer
        return answer

    async def aclose(self) -> None:
        """Nothing to release."""
        self.closed = True


@dataclass
class FakeSearchProvider:
    """Answers from a table of queries; anything else has no results."""

    results: dict[str, list[Hit] | SearchError] = field(default_factory=dict)
    queries: list[str] = field(default_factory=list)

    async def search(self, query: str, limit: int) -> list[Hit]:
        """The recorded results for ``query``, at most ``limit``."""
        self.queries.append(query)
        answer = self.results.get(query, [])
        if isinstance(answer, SearchError):
            raise answer
        return answer[:limit]


def html_page(url: str, html: str, content_type: str = "text/html; charset=utf-8") -> Fetched:
    """A fetched HTML page, for tests."""
    return Fetched(
        url=url, final_url=url, status=200, content_type=content_type, body=html.encode()
    )


def load_fixtures(directory: Path) -> tuple[FakeFetcher, FakeSearchProvider]:
    """Fakes serving the recorded pages and searches listed in ``directory/index.json``."""
    index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
    fetcher = FakeFetcher()
    for page in index["pages"]:
        fetcher.pages[page["url"]] = Fetched(
            url=page["url"],
            final_url=page["url"],
            status=200,
            content_type=page["content_type"],
            body=(directory / page["file"]).read_bytes(),
        )
    search = FakeSearchProvider()
    for recorded in index["searches"]:
        rows = json.loads((directory / recorded["file"]).read_text(encoding="utf-8"))
        search.results[recorded["query"]] = [
            Hit(title=row["title"], url=row["href"], snippet=row["body"]) for row in rows
        ]
    return fetcher, search
