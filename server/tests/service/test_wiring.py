from __future__ import annotations

from tests.conftest import PHONE
from textwire.config import Settings
from textwire.service.wiring import build_components
from textwire.transport.fake import FakeTransport


async def test_default_wiring_creates_a_database_and_closes_connections(settings: Settings) -> None:
    transport = FakeTransport()
    components = build_components(settings, transport=transport)
    assert settings.database_path.is_file()
    assert components.store.ping()
    assert components.budget.used() == 0
    # Status uses no external content provider and therefore cannot make an HTTP request.
    replies = await components.handler.handle(transport.deliver(PHONE, "00 ?"))
    assert len(replies) == 1
    await components.aclose()
    assert transport.closed
