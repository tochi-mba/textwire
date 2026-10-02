"""Building the running parts from the configuration, in one place."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from textwire import __version__
from textwire.clock import SystemClock
from textwire.content.fetch import HttpxFetcher
from textwire.content.search import DdgsSearchProvider
from textwire.protocol.compress import load_dictionary
from textwire.service.budget import Budget
from textwire.service.dispatcher import Dispatcher
from textwire.service.handler import Handler, HandlerSettings
from textwire.service.library import Library
from textwire.service.store import Store

if TYPE_CHECKING:
    from textwire.clock import Clock
    from textwire.config import Settings
    from textwire.content.fetch import Fetcher
    from textwire.content.search import SearchProvider
    from textwire.protocol.compress import Dictionary
    from textwire.transport.base import Transport


@dataclass
class Components:
    """Everything the server runs, wired together."""

    settings: Settings
    store: Store
    budget: Budget
    library: Library
    handler: Handler
    dispatcher: Dispatcher
    transport: Transport
    dictionary: Dictionary
    clock: Clock

    async def aclose(self) -> None:
        """Release connections and close the database."""
        await self.library.aclose()
        await self.transport.aclose()
        self.store.close()


def default_fetcher(settings: Settings) -> HttpxFetcher:
    """The real fetcher, configured from the settings."""
    return HttpxFetcher(
        user_agent=settings.user_agent,
        timeout_seconds=settings.fetch_timeout_seconds,
        max_bytes=settings.fetch_max_bytes,
        max_redirects=settings.fetch_max_redirects,
    )


def default_search(settings: Settings) -> DdgsSearchProvider:
    """The real search provider, configured from the settings."""
    return DdgsSearchProvider(
        region=settings.search_region,
        backend=settings.search_backend,
        timeout_seconds=settings.search_timeout_seconds,
        safesearch=settings.search_safesearch.value,
    )


def build_components(
    settings: Settings,
    *,
    transport: Transport,
    fetcher: Fetcher | None = None,
    search: SearchProvider | None = None,
    clock: Clock | None = None,
    store: Store | None = None,
) -> Components:
    """Wire the server from ``settings``; any part can be supplied instead of built."""
    clock = clock if clock is not None else SystemClock()
    if store is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        store = Store(settings.database_path)
    dictionary = load_dictionary()
    budget = Budget(
        store,
        clock,
        daily_limit=settings.daily_segment_budget,
        price_per_segment=settings.price_per_segment,
        currency=settings.currency,
    )
    library = Library(
        fetcher if fetcher is not None else default_fetcher(settings),
        search if search is not None else default_search(settings),
        search_results=settings.search_results,
        snippet_chars=settings.search_snippet_chars,
    )
    handler = Handler(
        library=library,
        store=store,
        budget=budget,
        dictionary=dictionary,
        clock=clock,
        settings=HandlerSettings.from_settings(settings, __version__),
    )
    dispatcher = Dispatcher(
        transport=transport,
        handler=handler,
        store=store,
        clock=clock,
        budget=budget,
        send_retries=settings.send_retries,
        send_gap_seconds=settings.send_gap_ms / 1000,
        status_interval_seconds=settings.status_interval_seconds,
        retention=timedelta(hours=settings.retention_hours),
        drop_once=settings.debug_drop_once,
    )
    return Components(
        settings, store, budget, library, handler, dispatcher, transport, dictionary, clock
    )
