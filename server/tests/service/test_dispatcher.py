from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from tests.conftest import PHONE, build_settings
from tests.service.conftest import Rig
from textwire.content.fakes import FakeFetcher
from textwire.content.fetch import Fetched
from textwire.service.dispatcher import Dispatcher
from textwire.service.handler import Handler, HandlerSettings, Reply
from textwire.service.library import Library
from textwire.transport.base import DeliveryStatus, TransportError
from textwire.transport.fake import FakeTransport


def dispatcher(rig: Rig, transport: FakeTransport) -> Dispatcher:
    return Dispatcher(
        transport=transport,
        handler=rig.handler,
        store=rig.store,
        clock=rig.clock,
        budget=rig.budget,
    )


async def test_duplicate_inbound_is_answered_and_charged_once(rig: Rig) -> None:
    transport = FakeTransport()
    worker = dispatcher(rig, transport)
    message = transport.deliver(PHONE, "a7 ?")
    await worker.process(message)
    await worker.process(message)
    assert len(transport.sent) == 1
    assert rig.budget.used() == 1
    assert rig.store.unhandled() == []


async def test_temporary_send_errors_back_off_then_succeed(rig: Rig) -> None:
    transport = FakeTransport()
    transport.failures = [TransportError("busy", retryable=True) for _ in range(2)]
    await dispatcher(rig, transport).send_all([Reply(PHONE, "hello")])
    assert rig.clock.slept == [1.0, 2.0]
    assert [message.text for message in transport.sent] == ["hello"]
    assert len(rig.store.pending_outbound(rig.clock.now() - timedelta(hours=1))) == 1


@pytest.mark.parametrize("retryable", [False, True])
async def test_failed_sends_stop_at_the_retry_limit(rig: Rig, retryable: bool) -> None:
    transport = FakeTransport()
    transport.failures = [TransportError("failed", retryable=retryable) for _ in range(4)]
    await dispatcher(rig, transport).send_all([Reply(PHONE, "hello")])
    assert transport.sent == []
    assert len(rig.clock.slept) == (3 if retryable else 0)


async def test_debug_loss_is_once_and_sends_are_spaced(rig: Rig) -> None:
    transport = FakeTransport()
    worker = Dispatcher(
        transport=transport,
        handler=rig.handler,
        store=rig.store,
        clock=rig.clock,
        budget=rig.budget,
        drop_once=(1,),
        send_gap_seconds=0.5,
    )
    replies = [Reply(PHONE, str(index), 0, index) for index in range(3)]
    await worker.send_all(replies)
    assert [message.text for message in transport.sent] == ["0", "2"]
    await worker.send_all(replies)
    assert [message.text for message in transport.sent] == ["0", "2", "0", "1", "2"]
    assert rig.clock.slept == [0.5, 0.5, 0.5]


async def test_delivery_sweep_tracks_prices_and_leaves_unknown_status_pending(rig: Rig) -> None:
    transport = FakeTransport()
    worker = dispatcher(rig, transport)
    await worker.send_all([Reply(PHONE, "first"), Reply(PHONE, "second")])
    first, second = transport.sent
    transport.statuses[first.id] = DeliveryStatus(first.id, "delivered", 0.05, "USD")
    await worker.sweep()
    assert [row.id for row in rig.store.pending_outbound(rig.clock.now())] == [second.id]
    assert rig.store.actual_cost(rig.clock.now().date()) == (0.05, "USD")


async def test_status_errors_do_not_stop_the_sweep(rig: Rig) -> None:
    class BrokenStatus(FakeTransport):
        async def status(self, message_id: str) -> DeliveryStatus | None:
            raise TransportError("unavailable", retryable=True)

    transport = BrokenStatus()
    worker = dispatcher(rig, transport)
    await worker.send_all([Reply(PHONE, "hello")])
    await worker.sweep()
    assert len(rig.store.pending_outbound(rig.clock.now())) == 1


async def test_a_failed_delivery_is_charged_and_retried_only_once(rig: Rig) -> None:
    transport = FakeTransport()
    worker = dispatcher(rig, transport)
    await worker.process(transport.deliver(PHONE, "a7 ?"))
    first = transport.sent[0]
    transport.statuses[first.id] = DeliveryStatus(first.id, "undelivered")
    await worker.sweep()
    assert len(transport.sent) == 2
    assert rig.budget.used() == 2
    second = transport.sent[1]
    transport.statuses[second.id] = DeliveryStatus(second.id, "undelivered")
    await worker.sweep()
    assert len(transport.sent) == 2
    assert rig.budget.used() == 2


async def test_a_failed_delivery_cannot_retry_past_the_daily_budget(rig: Rig) -> None:
    transport = FakeTransport()
    worker = dispatcher(rig, transport)
    await worker.process(transport.deliver(PHONE, "a7 ?"))
    rig.budget.charge(199)
    first = transport.sent[0]
    transport.statuses[first.id] = DeliveryStatus(first.id, "failed")
    await worker.sweep()
    assert len(transport.sent) == 1
    assert rig.budget.used() == 200


async def test_a_rejected_delivery_retry_stays_charged_and_is_not_repeated(rig: Rig) -> None:
    transport = FakeTransport()
    worker = dispatcher(rig, transport)
    await worker.process(transport.deliver(PHONE, "a7 ?"))
    first = transport.sent[0]
    transport.statuses[first.id] = DeliveryStatus(first.id, "failed")
    transport.failures = [TransportError("rejected", retryable=False)]
    await worker.sweep()
    await worker.sweep()
    assert len(transport.sent) == 1
    assert rig.budget.used() == 2


@pytest.mark.parametrize("unhandled", [False, True])
async def test_run_receives_and_shuts_down_its_workers(rig: Rig, unhandled: bool) -> None:
    transport = FakeTransport()
    if unhandled:
        rig.store.record_inbound(transport.deliver(PHONE, "?", message_id="old"))
    transport.deliver(PHONE, "a7 ?")
    stop = asyncio.Event()
    worker = dispatcher(rig, transport)
    task = asyncio.create_task(worker.run(stop))
    try:
        message = await asyncio.wait_for(transport.outbox.get(), 2)
        assert message.recipient == PHONE
    finally:
        stop.set()
        await asyncio.wait_for(task, 2)


async def test_a_handler_bug_is_logged_and_the_next_request_is_answered(rig: Rig) -> None:
    class BrokenFetcher(FakeFetcher):
        async def fetch(self, url: str) -> Fetched:
            raise RuntimeError("unexpected extractor failure")

    rig.handler = Handler(
        library=Library(BrokenFetcher({}), rig.search, search_results=5),
        store=rig.store,
        budget=rig.budget,
        dictionary=rig.dictionary,
        clock=rig.clock,
        settings=HandlerSettings.from_settings(build_settings(), "test"),
    )
    transport = FakeTransport()
    worker = dispatcher(rig, transport)
    await worker.process(transport.deliver(PHONE, "a7 g https://example.org"))
    await worker.process(transport.deliver(PHONE, "b0 ?"))
    assert len(transport.sent) == 1
    assert rig.store.unhandled() == []
