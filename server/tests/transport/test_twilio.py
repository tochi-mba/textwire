from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx

from tests.conftest import PHONE, SERVER
from tests.service.conftest import memory_store
from textwire.clock import EPOCH, FakeClock
from textwire.transport.base import TransportError
from textwire.transport.twilio import (
    LAST_SEEN_KEY,
    MAX_LIST_PAGES,
    OVERLAP,
    MessageResource,
    TwilioClient,
    TwilioTransport,
    signature_matches,
    webhook_signature,
)

SID = "AC" + "0" * 32
BASE = f"https://api.twilio.com/2010-04-01/Accounts/{SID}"


def _resource(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sid": "SM1",
        "direction": "inbound",
        "status": "received",
        "from": PHONE,
        "to": SERVER,
        "body": "a7 ?",
        "date_sent": "Wed, 30 Sep 2026 12:00:05 +0000",
        "date_created": "Wed, 30 Sep 2026 12:00:04 +0000",
        "price": None,
        "price_unit": None,
        "error_code": None,
        "num_segments": "1",
    }
    return {**base, **overrides}


def _client() -> TwilioClient:
    return TwilioClient(account_sid=SID, auth_token="token")


def _transport(client: TwilioClient, clock: FakeClock) -> TwilioTransport:
    return TwilioTransport(
        client=client,
        number=SERVER,
        store=memory_store(),
        clock=clock,
        poll_seconds=3,
        lookback=timedelta(hours=1),
    )


def test_resources_parse_twilio_json() -> None:
    resource = MessageResource.from_json(
        _resource(price="-0.05600", price_unit="USD", error_code=30003, status="undelivered")
    )
    assert resource.price == -0.056
    assert resource.price_unit == "USD"
    assert resource.error_code == 30003
    assert resource.date_sent == datetime(2026, 9, 30, 12, 0, 5, tzinfo=UTC)


def test_a_resource_without_dates_gets_now_as_created() -> None:
    resource = MessageResource.from_json({"sid": "SM9", "date_sent": None, "date_created": ""})
    assert resource.date_sent is None
    assert resource.date_created.tzinfo is UTC


@respx.mock
async def test_send_posts_the_form_with_basic_auth() -> None:
    route = respx.post(f"{BASE}/Messages.json").mock(
        return_value=httpx.Response(201, json=_resource(sid="SM7", direction="outbound-api"))
    )
    client = _client()
    resource = await client.send(sender=SERVER, recipient=PHONE, body="hello")
    await client.aclose()
    assert resource.sid == "SM7"
    request = route.calls.last.request
    assert request.headers["authorization"].startswith("Basic ")
    assert dict(httpx.QueryParams(request.content.decode())) == {
        "From": SERVER,
        "To": PHONE,
        "Body": "hello",
    }


def _paged(pages: int) -> Callable[[httpx.Request], httpx.Response]:
    """A Twilio listing of ``pages`` pages, one message each, linked by page tokens."""

    def respond(request: httpx.Request) -> httpx.Response:
        token = int(request.url.params.get("PageToken", "0"))
        following = (
            f"/2010-04-01/Accounts/{SID}/Messages.json?PageToken={token + 1}"
            if token + 1 < pages
            else None
        )
        return httpx.Response(
            200,
            json={"messages": [_resource(sid=f"SM{token}")], "next_page_uri": following},
        )

    return respond


@respx.mock
async def test_list_follows_pages_and_filters_by_recipient_and_time() -> None:
    route = respx.get(f"{BASE}/Messages.json").mock(side_effect=_paged(3))
    client = _client()
    found = await client.list_to(SERVER, datetime(2026, 9, 30, 11, 0, tzinfo=UTC))
    await client.aclose()
    assert [item.sid for item in found] == ["SM0", "SM1", "SM2"]
    params = route.calls[0].request.url.params
    assert params["To"] == SERVER
    assert params["DateSent>"] == "2026-09-30T11:00:00Z"
    assert params["PageSize"] == "100"
    assert route.calls[1].request.url.params["PageToken"] == "1"
    assert route.call_count == 3


@respx.mock
async def test_a_listing_that_never_ends_is_cut_off() -> None:
    route = respx.get(f"{BASE}/Messages.json").mock(side_effect=_paged(10_000))
    client = _client()
    found = await client.list_to(SERVER, datetime(2026, 9, 30, 11, 0, tzinfo=UTC))
    await client.aclose()
    assert len(found) == MAX_LIST_PAGES
    assert route.call_count == MAX_LIST_PAGES


@respx.mock
async def test_errors_carry_twilio_s_message_and_code() -> None:
    respx.get(f"{BASE}/Messages/SM1.json").mock(
        return_value=httpx.Response(404, json={"code": 20404, "message": "not found"})
    )
    client = _client()
    with pytest.raises(TransportError) as caught:
        await client.get("SM1")
    await client.aclose()
    assert str(caught.value) == "twilio 404: not found"
    assert caught.value.code == 20404
    assert not caught.value.retryable


@respx.mock
async def test_server_errors_and_rate_limits_are_retryable() -> None:
    respx.post(f"{BASE}/Messages.json").mock(return_value=httpx.Response(429, text="slow down"))
    client = _client()
    with pytest.raises(TransportError) as caught:
        await client.send(sender=SERVER, recipient=PHONE, body="x")
    await client.aclose()
    assert caught.value.retryable
    assert caught.value.code is None
    assert "slow down" in str(caught.value)


@respx.mock
async def test_timeouts_and_connection_failures_are_retryable() -> None:
    respx.get(f"{BASE}/Messages/SM1.json").mock(side_effect=httpx.ReadTimeout("slow"))
    respx.get(f"{BASE}/Messages/SM2.json").mock(side_effect=httpx.ConnectError("down"))
    client = _client()
    for sid in ("SM1", "SM2"):
        with pytest.raises(TransportError) as caught:
            await client.get(sid)
        assert caught.value.retryable
    await client.aclose()


@respx.mock
async def test_polling_yields_new_inbound_messages_once_in_order(clock: FakeClock) -> None:
    respx.get(f"{BASE}/Messages.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "messages": [
                    _resource(sid="SM2", date_created="Wed, 30 Sep 2026 12:00:09 +0000"),
                    _resource(sid="SM1"),
                    _resource(sid="SM3", direction="outbound-api", body="frame"),
                ],
                "next_page_uri": None,
            },
        )
    )
    transport = _transport(_client(), clock)
    first = await transport.poll()
    assert [message.id for message in first] == ["SM1", "SM2"]
    assert first[0].sender == PHONE
    assert first[0].received_at == datetime(2026, 9, 30, 12, 0, 4, tzinfo=UTC)
    transport._store.record_inbound(first[0])
    transport._store.record_inbound(first[1])
    assert await transport.poll() == []
    assert transport._store.get_state(LAST_SEEN_KEY) == "2026-09-30T12:00:09+00:00"
    await transport.aclose()


@respx.mock
async def test_the_first_poll_looks_back_an_hour_and_later_ones_overlap(clock: FakeClock) -> None:
    route = respx.get(f"{BASE}/Messages.json").mock(
        return_value=httpx.Response(200, json={"messages": [_resource()], "next_page_uri": None})
    )
    transport = _transport(_client(), clock)
    await transport.poll()
    assert route.calls[0].request.url.params["DateSent>"] == "2026-09-30T11:00:00Z"
    await transport.poll()
    expected = (datetime(2026, 9, 30, 12, 0, 4, tzinfo=UTC) - OVERLAP).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert route.calls[1].request.url.params["DateSent>"] == expected
    await transport.aclose()


@respx.mock
async def test_receive_polls_forever_and_survives_provider_errors(clock: FakeClock) -> None:
    route = respx.get(f"{BASE}/Messages.json")
    route.side_effect = [
        httpx.Response(503, text="down"),
        httpx.Response(200, json={"messages": [_resource(sid="SM5")], "next_page_uri": None}),
    ]
    transport = _transport(_client(), clock)
    stream = transport.receive()
    message = await anext(stream)
    assert message.id == "SM5"
    assert clock.slept == [3]
    await stream.aclose()
    await transport.aclose()


@respx.mock
async def test_send_and_status_map_to_the_transport_types(clock: FakeClock) -> None:
    respx.post(f"{BASE}/Messages.json").mock(
        return_value=httpx.Response(201, json=_resource(sid="SM7", direction="outbound-api"))
    )
    respx.get(f"{BASE}/Messages/SM7.json").mock(
        return_value=httpx.Response(
            200,
            json=_resource(sid="SM7", status="delivered", price="-0.05600", price_unit="USD"),
        )
    )
    transport = _transport(_client(), clock)
    sent = await transport.send(PHONE, "frame")
    assert (sent.id, sent.recipient, sent.text) == ("SM7", PHONE, "frame")
    status = await transport.status("SM7")
    assert status is not None
    assert (status.status, status.price, status.price_unit) == ("delivered", 0.056, "USD")
    assert status.is_final
    assert not status.is_failure
    assert transport.number == SERVER
    await transport.aclose()


def test_webhook_signatures_follow_twilio_s_recipe() -> None:
    url = "https://sms.example/webhooks/twilio"
    form = {"To": SERVER, "From": PHONE, "Body": "a7 ?"}
    signature = webhook_signature(url, form, "token")
    assert signature_matches(url, form, "token", signature)
    assert not signature_matches(url, form, "other", signature)
    assert not signature_matches(url, {**form, "Body": "x"}, "token", signature)


def test_the_recorded_twilio_shapes_still_parse() -> None:
    """The fields the server reads, as Twilio documented them in 2026-09."""
    recorded = json.loads(
        '{"sid": "SMabc", "direction": "inbound", "status": "received", "from": "+447700900123",'
        ' "to": "+447700900000", "body": "hi", "num_segments": "2",'
        ' "date_sent": "Wed, 30 Sep 2026 12:00:05 +0000",'
        ' "date_created": "Wed, 30 Sep 2026 12:00:04 +0000", "price": null,'
        ' "price_unit": "USD", "error_code": null, "uri": "/2010-04-01/x"}'
    )
    resource = MessageResource.from_json(recorded)
    assert resource.sid == "SMabc"
    assert resource.body == "hi"
    assert resource.date_created < EPOCH + timedelta(seconds=5)
