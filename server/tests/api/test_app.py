from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from tests.conftest import PHONE, REPO_ROOT, STRANGER, build_settings
from textwire import __version__
from textwire.api.app import RECENT, create_app, public_settings, retention
from textwire.clock import FakeClock
from textwire.config import Settings
from textwire.content.fakes import load_fixtures
from textwire.service.store import Store
from textwire.service.wiring import Components, build_components
from textwire.transport.fake import FakeTransport

ARTICLE = "https://dunmore-gazette.example/news/text-only-library"


def _components(clock: FakeClock, **overrides: object) -> Components:
    fetcher, search = load_fixtures(REPO_ROOT / "protocol" / "fixtures")
    return build_components(
        build_settings(**overrides),
        transport=FakeTransport(),
        fetcher=fetcher,
        search=search,
        clock=clock,
        store=Store(":memory:"),
    )


@pytest.fixture
async def wired(clock: FakeClock) -> AsyncIterator[tuple[AsyncClient, Components]]:
    """A client on the app with the dispatcher switched off, plus the components."""
    components = _components(clock)
    app = create_app(components, run_dispatcher=False)
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        yield http, components
    await components.aclose()


async def test_healthy_needs_nothing(wired: tuple[AsyncClient, Components]) -> None:
    http, _ = wired
    body = (await http.get("/healthy")).json()
    assert body == {"status": "alive", "version": __version__, "environment": "local"}


async def test_healthy_and_the_dashboard_answer_without_components() -> None:
    app = create_app(None)
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        assert (await http.get("/healthy")).json()["environment"] == ""
        assert (await http.get("/")).status_code == 200
        ready = await http.get("/ready")
        assert ready.status_code == 503
        assert ready.json() == {"status": "degraded", "checks": {"components": False}}
        assert (await http.get("/api/overview")).status_code == 503
        assert (await http.post("/api/probe", json={"number": PHONE})).status_code == 503


async def test_ready_checks_the_store_and_the_transport(
    wired: tuple[AsyncClient, Components],
) -> None:
    http, _ = wired
    body = (await http.get("/ready")).json()
    assert body == {
        "status": "ready",
        "checks": {"components": True, "store": True, "transport": True},
    }


async def test_ready_is_degraded_without_credentials(clock: FakeClock) -> None:
    components = _components(clock, twilio_number="")
    app = create_app(components, run_dispatcher=False)
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        ready = await http.get("/ready")
        assert ready.status_code == 503
        assert ready.json()["checks"]["transport"] is False
    await components.aclose()


async def test_the_dashboard_is_self_contained_html(wired: tuple[AsyncClient, Components]) -> None:
    http, _ = wired
    page = await http.get("/")
    assert page.headers["content-type"].startswith("text/html")
    assert "<title>textwire dashboard - REX Technologies</title>" in page.text
    assert "https://" not in page.text
    assert "/api/overview" in page.text
    assert "http://" not in page.text.replace("http://test", "")
    assert "<script src" not in page.text


async def test_the_overview_reflects_requests_and_documents(
    wired: tuple[AsyncClient, Components], clock: FakeClock
) -> None:
    http, components = wired
    transport = components.transport
    assert isinstance(transport, FakeTransport)
    message = transport.deliver(PHONE, f"a7 g {ARTICLE}", at=clock.now())
    await components.dispatcher.process(message)
    body = (await http.get("/api/overview")).json()
    assert body["version"] == __version__
    assert body["number"] == "+44...0000"
    assert body["allowed"] == 1
    assert body["alphabet"] == "b64"
    assert body["budget"]["limit"] == 200
    assert body["budget"]["used"] == len(transport.sent)
    assert body["outbound_today"] == len(transport.sent)
    [request] = body["requests"]
    assert request["number"] == "+44...0123"
    assert request["body"] == f"a7 g {ARTICLE}"
    assert request["replies"] == len(transport.sent)
    assert request["handled_at"] is not None
    [document] = body["documents"]
    assert (document["tag"], document["kind"], document["plain"]) == ("a7", "page", False)
    assert document["title"] == "Village gets its first text-only library"
    assert document["page_size"] == 12


async def test_the_overview_lists_at_most_the_recent_entries(
    wired: tuple[AsyncClient, Components], clock: FakeClock
) -> None:
    http, components = wired
    transport = components.transport
    assert isinstance(transport, FakeTransport)
    for _ in range(RECENT + 5):
        clock.advance(1)
        await components.dispatcher.process(transport.deliver(PHONE, "?", at=clock.now()))
    body = (await http.get("/api/overview")).json()
    assert len(body["requests"]) == RECENT
    assert body["requests"][0]["received_at"] > body["requests"][-1]["received_at"]


async def test_a_probe_goes_to_an_allowed_number_and_is_charged(
    wired: tuple[AsyncClient, Components],
) -> None:
    http, components = wired
    transport = components.transport
    assert isinstance(transport, FakeTransport)
    reply = await http.post("/api/probe", json={"number": PHONE})
    assert reply.status_code == 200
    assert reply.json() == {"id": "SM1", "characters": 160, "to": "+44...0123"}
    assert len(transport.sent[0].text) == 160
    assert components.budget.used() == 1
    assert (await http.get("/api/overview")).json()["outbound_today"] == 1


async def test_a_probe_to_a_stranger_is_refused(wired: tuple[AsyncClient, Components]) -> None:
    http, components = wired
    reply = await http.post("/api/probe", json={"number": STRANGER})
    assert reply.status_code == 403
    assert "TEXTWIRE_ALLOWED_NUMBERS" in reply.json()["detail"]
    assert components.budget.used() == 0


async def test_a_probe_is_refused_when_the_budget_is_spent(clock: FakeClock) -> None:
    components = _components(clock, daily_segment_budget=1)
    components.budget.charge(1)
    app = create_app(components, run_dispatcher=False)
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        reply = await http.post("/api/probe", json={"number": PHONE})
    await components.aclose()
    assert reply.status_code == 429
    assert reply.json()["detail"] == "E budget 1/1"


async def test_a_malformed_probe_body_is_rejected(wired: tuple[AsyncClient, Components]) -> None:
    http, _ = wired
    assert (await http.post("/api/probe", json={"number": "12"})).status_code == 422


async def test_the_dispatcher_runs_inside_the_lifespan(clock: FakeClock, tmp_path: Path) -> None:
    components = _components(clock)
    app = create_app(components)
    transport = components.transport
    assert isinstance(transport, FakeTransport)
    async with LifespanManager(app):
        transport.deliver(PHONE, "?", at=clock.now())
        for _ in range(50):
            await __import__("asyncio").sleep(0)
            if transport.sent:
                break
    assert transport.sent
    await components.aclose()


def test_retention_follows_the_settings() -> None:
    assert retention(build_settings(retention_hours=6)) == timedelta(hours=6)


async def test_the_overview_shows_every_setting_with_secrets_hidden(
    wired: tuple[AsyncClient, Components],
) -> None:
    http, components = wired
    config = (await http.get("/api/overview")).json()["config"]
    assert set(config) == {f"TEXTWIRE_{name.upper()}" for name in Settings.model_fields}
    assert config["TEXTWIRE_TWILIO_AUTH_TOKEN"] == "set"
    assert config["TEXTWIRE_GATEWAY_PASSWORD"] == "not set"
    assert config["TEXTWIRE_TWILIO_NUMBER"] == "+44...0000"
    assert config["TEXTWIRE_TWILIO_ACCOUNT_SID"].endswith("...0000")
    assert config["TEXTWIRE_ALLOWED_NUMBERS"] == ["+44...0123"]
    assert config["TEXTWIRE_GATEWAY_URL"] == ""
    assert config["TEXTWIRE_TRANSPORT"] == "twilio"
    assert config["TEXTWIRE_DATA_DIR"] == components.settings.data_dir.as_posix()
    assert config["TEXTWIRE_DEBUG_DROP_ONCE"] == []
    assert config["TEXTWIRE_PAGE_FRAMES"] == 12
    assert config["TEXTWIRE_DASHBOARD"] is True
    text = (await http.get("/api/overview")).text
    assert "test-auth-token" not in text
    assert PHONE not in text


def test_an_empty_masked_setting_stays_empty() -> None:
    view = public_settings(build_settings(twilio_number="", twilio_account_sid=""))
    assert view["TEXTWIRE_TWILIO_NUMBER"] == ""
    assert view["TEXTWIRE_TWILIO_ACCOUNT_SID"] == ""


async def test_with_the_dashboard_off_only_health_answers(clock: FakeClock) -> None:
    components = _components(clock, dashboard=False)
    app = create_app(components, run_dispatcher=False)
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        for method, path in (("GET", "/"), ("GET", "/api/overview"), ("POST", "/api/probe")):
            response = await http.request(method, path, json={"number": PHONE})
            assert response.status_code == 404, path
            assert "TEXTWIRE_DASHBOARD=false" in response.text
        assert (await http.get("/healthy")).status_code == 200
        assert (await http.get("/ready")).status_code == 200
    await components.aclose()
