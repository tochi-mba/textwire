from __future__ import annotations

import pytest

from tests.conftest import PHONE, REPO_ROOT
from textwire.config import SafeSearch, Settings
from textwire.content.fakes import load_fixtures
from textwire.service import wiring
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


def test_the_fetch_and_search_settings_reach_the_real_providers(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: dict[str, dict[str, object]] = {}

    def capture(name: str) -> object:
        def build(**kwargs: object) -> object:
            built[name] = kwargs
            return object()

        return build

    monkeypatch.setattr(wiring, "HttpxFetcher", capture("fetcher"))
    monkeypatch.setattr(wiring, "DdgsSearchProvider", capture("search"))
    tuned = settings.model_copy(
        update={"fetch_max_redirects": 2, "search_safesearch": SafeSearch.STRICT}
    )
    wiring.default_fetcher(tuned)
    wiring.default_search(tuned)
    assert built["fetcher"]["max_redirects"] == 2
    assert built["search"]["safesearch"] == "strict"


async def test_the_snippet_setting_reaches_search_results(settings: Settings) -> None:
    fetcher, search = load_fixtures(REPO_ROOT / "protocol" / "fixtures")
    tuned = settings.model_copy(update={"search_snippet_chars": 0})
    components = build_components(tuned, transport=FakeTransport(), fetcher=fetcher, search=search)
    document = await components.library.search("bbc weather london")
    assert all(line[0].isdigit() for line in document.body.split("\n\n"))
    assert "\n" not in document.body.replace("\n\n", "")
    await components.aclose()
