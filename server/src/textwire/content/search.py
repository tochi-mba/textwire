"""Web search, behind an interface.

The default provider is the ``ddgs`` package, which needs no API key and falls back across
several engines. It is synchronous, so it runs in a worker thread with a timeout.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

from ddgs import DDGS
from ddgs.exceptions import DDGSException

if TYPE_CHECKING:
    from collections.abc import Callable


class SearchFault(StrEnum):
    """Why a search failed; the value follows ``E search``."""

    FAILED = "failed"
    TIMEOUT = "timeout"


class SearchError(Exception):
    """A search that produced no answer, as opposed to an answer with no results."""

    def __init__(self, fault: SearchFault) -> None:
        super().__init__(fault.value)
        self.fault = fault

    @property
    def status_text(self) -> str:
        """The status line the phone is sent: ``E search timeout``."""
        return f"E search {self.fault.value}"


@dataclass(frozen=True, slots=True)
class Hit:
    """One search result."""

    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    """Anything that can search the web."""

    async def search(self, query: str, limit: int) -> list[Hit]:
        """At most ``limit`` results for ``query``, best first."""
        ...


class DdgsClient(Protocol):
    """The part of ``ddgs.DDGS`` this module uses."""

    def text(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Text search results as dictionaries with title, href and body."""
        ...


class DdgsSearchProvider:
    """Searches through the ``ddgs`` metasearch package."""

    def __init__(
        self,
        *,
        region: str,
        backend: str,
        timeout_seconds: float,
        safesearch: str = "moderate",
        client_factory: Callable[[], DdgsClient] | None = None,
    ) -> None:
        self._region = region
        self._backend = backend
        self._timeout = timeout_seconds
        self._safesearch = safesearch
        self._factory = client_factory or (lambda: DDGS(timeout=max(1, int(timeout_seconds))))

    async def search(self, query: str, limit: int) -> list[Hit]:
        """At most ``limit`` results; an empty list when the engines found nothing."""

        def run() -> list[dict[str, Any]]:
            return self._factory().text(
                query,
                region=self._region,
                safesearch=self._safesearch,
                max_results=limit,
                backend=self._backend,
            )

        try:
            rows = await asyncio.wait_for(asyncio.to_thread(run), self._timeout)
        except TimeoutError as error:
            raise SearchError(SearchFault.TIMEOUT) from error
        except DDGSException as error:
            # ddgs reports an empty result set as an exception; it is an answer, not a failure.
            if "no results" in str(error).lower():
                return []
            raise SearchError(SearchFault.FAILED) from error
        hits = [
            Hit(
                title=str(row.get("title") or ""),
                url=str(row["href"]),
                snippet=str(row.get("body") or ""),
            )
            for row in rows
            if str(row.get("href") or "").startswith(("http://", "https://"))
        ]
        return hits[:limit]
