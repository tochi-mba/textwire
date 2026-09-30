from __future__ import annotations

import pytest

from tests.conftest import PHONE
from textwire.transport.base import DeliveryStatus, TransportError
from textwire.transport.fake import FakeTransport


@pytest.mark.parametrize(
    "status", ["queued", "sent", "delivered", "failed", "undelivered", "canceled"]
)
def test_delivery_status_classification(status: str) -> None:
    delivery = DeliveryStatus("SM1", status)
    assert delivery.is_final == (status in {"delivered", "failed", "undelivered", "canceled"})
    assert delivery.is_failure == (status in {"failed", "undelivered", "canceled"})


async def test_fake_transport_exposes_the_same_messages_to_both_endpoints() -> None:
    transport = FakeTransport()
    inbound = transport.deliver(PHONE, "00 ?", message_id="provider-id")
    stream = transport.receive()
    assert await anext(stream) == inbound
    await stream.aclose()
    transport.failures.append(TransportError("busy", retryable=True, code=429))
    with pytest.raises(TransportError) as caught:
        await transport.send(PHONE, "hello")
    assert (caught.value.retryable, caught.value.code) == (True, 429)
    sent = await transport.send(PHONE, "hello")
    assert await transport.outbox.get() == sent
    assert transport.sent == [sent]
    assert await transport.status(sent.id) is None
    status = DeliveryStatus(sent.id, "delivered")
    transport.statuses[sent.id] = status
    assert await transport.status(sent.id) == status
    await transport.aclose()
    assert transport.closed
