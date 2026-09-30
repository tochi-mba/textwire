"""Where documents come from: the web, the search engine, and the server itself."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from textwire.content.extract import ExtractError, extract_document
from textwire.content.fetch import FetchError
from textwire.content.render import help_document, search_document
from textwire.content.search import SearchError

if TYPE_CHECKING:
    from textwire.content.document import Document
    from textwire.content.fetch import Fetcher
    from textwire.content.search import SearchProvider

log = logging.getLogger(__name__)


class Unavailable(Exception):  # noqa: N818 - a result, not a bug; reads better at call sites
    """A document could not be produced; ``status_text`` says why, for the phone."""

    def __init__(self, status_text: str) -> None:
        super().__init__(status_text)
        self.status_text = status_text


class Library:
    """Turns URLs and queries into documents, and every failure into a status line."""

    def __init__(self, fetcher: Fetcher, search: SearchProvider, *, search_results: int) -> None:
        self._fetcher = fetcher
        self._search = search
        self._results = search_results

    async def page(self, url: str) -> Document:
        """The readable document at ``url``."""
        try:
            fetched = await self._fetcher.fetch(url)
            return extract_document(fetched)
        except (FetchError, ExtractError) as error:
            log.info("page unavailable", extra={"url": url, "reason": error.status_text})
            raise Unavailable(error.status_text) from error

    async def search(self, query: str) -> Document:
        """The results page for ``query``."""
        try:
            hits = await self._search.search(query, self._results)
        except SearchError as error:
            log.info("search unavailable", extra={"reason": error.status_text})
            raise Unavailable(error.status_text) from error
        return search_document(query, hits)

    @staticmethod
    def help() -> Document:
        """The help page."""
        return help_document()

    async def aclose(self) -> None:
        """Release the fetcher's connections."""
        await self._fetcher.aclose()
