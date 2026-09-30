"""An in-memory SMS provider for tests and the simulator."""

from __future__ import annotations

import asyncio
import itertools
from typing import TYPE_CHECKING

from textwire.clock import EPOCH
from textwire.transport.base import DeliveryStatus, InboundMessage, SentMessage, TransportError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

#: The server's number in tests and the simulator: Ofcom's drama range, never a real phone.
FAKE_SERVER_NUMBER = "+447700900000"


class FakeTransport:
    """Messages go in through :meth:`deliver` and come out in :attr:`sent` and :attr:`outbox`.

    ``failures`` are raised by :meth:`send`, first to last, before any send succeeds, so a
    test can script a provider that fails twice and then recovers.
    """

    def __init__(self, number: str = FAKE_SERVER_NUMBER) -> None:
        self.number = number
        self.inbox: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbox: asyncio.Queue[SentMessage] = asyncio.Queue()
        self.sent: list[SentMessage] = []
        self.failures: list[TransportError] = []
        self.statuses: dict[str, DeliveryStatus] = {}
        self.closed = False
        self._ids = itertools.count(1)

    def deliver(
        self,
        sender: str,
        text: str,
        *,
        at: datetime = EPOCH,
        message_id: str | None = None,
    ) -> InboundMessage:
        """Queue an inbound SMS, as if a phone had just sent it."""
        message = InboundMessage(
            id=message_id or f"IN{next(self._ids)}",
            sender=sender,
            recipient=self.number,
            text=text,
            received_at=at,
        )
        self.inbox.put_nowait(message)
        return message

    async def receive(self) -> AsyncGenerator[InboundMessage]:
        """Inbound messages, waiting for each one."""
        while True:
            yield await self.inbox.get()

    async def send(self, recipient: str, text: str) -> SentMessage:
        """Record the message, or raise the next scripted failure."""
        if self.failures:
            raise self.failures.pop(0)
        message = SentMessage(id=f"SM{next(self._ids)}", recipient=recipient, text=text)
        self.sent.append(message)
        self.outbox.put_nowait(message)
        return message

    async def status(self, message_id: str) -> DeliveryStatus | None:
        """The status a test set for ``message_id``."""
        return self.statuses.get(message_id)

    async def aclose(self) -> None:
        """Nothing to release."""
        self.closed = True
