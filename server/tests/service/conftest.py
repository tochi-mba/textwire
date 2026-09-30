"""A handler wired to fakes: recorded pages, an in-memory database and a fake clock."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta

import pytest

from tests.conftest import PHONE, REPO_ROOT, SERVER
from textwire.clock import FakeClock
from textwire.content.fakes import FakeFetcher, FakeSearchProvider, load_fixtures
from textwire.protocol.compress import Dictionary, load_dictionary
from textwire.protocol.envelope import Envelope, unpack_envelope
from textwire.protocol.frames import decode_frame, join_frames
from textwire.protocol.tags import decode_tag
from textwire.service.budget import Budget
from textwire.service.handler import Handler, HandlerSettings, Reply
from textwire.service.library import Library
from textwire.service.store import Store
from textwire.transport.base import InboundMessage

ARTICLE = "https://dunmore-gazette.example/news/text-only-library"
FIXTURES = REPO_ROOT / "protocol" / "fixtures"
_STORES: list[Store] = []


def memory_store() -> Store:
    """An in-memory store owned by the current test's cleanup fixture."""
    store = Store(":memory:")
    _STORES.append(store)
    return store


@pytest.fixture(autouse=True)
def _close_test_stores() -> Iterator[None]:
    yield
    while _STORES:
        _STORES.pop().close()


@dataclass
class Rig:
    """Everything a handler test touches."""

    handler: Handler
    store: Store
    budget: Budget
    clock: FakeClock
    fetcher: FakeFetcher
    search: FakeSearchProvider
    dictionary: Dictionary
    count: int = 0
    log: list[str] = field(default_factory=list)

    async def ask(self, text: str, sender: str = PHONE) -> list[Reply]:
        """Handle one inbound SMS and return the replies."""
        self.count += 1
        self.log.append(text)
        message = InboundMessage(f"IN{self.count}", sender, SERVER, text, self.clock.now())
        return await self.handler.handle(message)

    def envelope(self, replies: list[Reply]) -> Envelope:
        """The envelope a set of encoded replies carries."""
        frames = [decode_frame(reply.text) for reply in replies]
        return unpack_envelope(join_frames(frames), self.dictionary)


def build_rig(limit: int = 200, **overrides: object) -> Rig:
    """A rig with the recorded fixtures and the given budget."""
    fetcher, search = load_fixtures(FIXTURES)
    store = memory_store()
    clock = FakeClock()
    dictionary = load_dictionary()
    budget = Budget(store, clock, daily_limit=limit, price_per_segment=0.056, currency="USD")
    settings = HandlerSettings(
        allowed_numbers=frozenset({PHONE, "+447700900456"}),
        version="9.9.9",
        **overrides,  # type: ignore[arg-type]
    )
    handler = Handler(
        library=Library(fetcher, search, search_results=5),
        store=store,
        budget=budget,
        dictionary=dictionary,
        clock=clock,
        settings=settings,
    )
    return Rig(handler, store, budget, clock, fetcher, search, dictionary)


@pytest.fixture
def rig() -> Rig:
    """A handler over the recorded fixtures with a 200-SMS budget."""
    return build_rig()


def tag(text: str) -> int:
    """A tag's number."""
    return decode_tag(text)


NOTICE = timedelta(minutes=10)
