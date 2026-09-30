"""The dispatcher: receives from the transport, answers through the handler, sends, follows up.

Every inbound message is recorded before it is handled, so a message the provider reports
twice is answered once. Sends are retried with backoff when the provider says the failure is
temporary. A maintenance loop follows the delivery status and real price of recent messages,
resends a frame once if the provider says it was not delivered, and purges old data.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from textwire.logs import mask_number
from textwire.service.budget import BudgetExceededError
from textwire.service.handler import Reply
from textwire.transport.base import TransportError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from textwire.clock import Clock
    from textwire.service.budget import Budget
    from textwire.service.handler import Handler
    from textwire.service.store import Store
    from textwire.transport.base import InboundMessage, SentMessage, Transport

log = logging.getLogger(__name__)


class Dispatcher:
    """Runs the server's receive and maintenance loops."""

    def __init__(
        self,
        *,
        transport: Transport,
        handler: Handler,
        store: Store,
        clock: Clock,
        budget: Budget,
        send_retries: int = 3,
        send_gap_seconds: float = 0.0,
        status_interval_seconds: float = 60.0,
        retention: timedelta = timedelta(hours=24),
        drop_once: Iterable[int] = (),
    ) -> None:
        self._transport = transport
        self._handler = handler
        self._store = store
        self._clock = clock
        self._budget = budget
        self._retries = send_retries
        self._gap = send_gap_seconds
        self._interval = status_interval_seconds
        self._retention = retention
        self._drop_once = frozenset(drop_once)

    async def run(self, stop: asyncio.Event) -> None:
        """Receive and maintain until ``stop`` is set."""
        unhandled = self._store.unhandled()
        if unhandled:
            log.warning(
                "requests were recorded but not fully answered before the last stop",
                extra={"count": len(unhandled)},
            )
        tasks = [
            asyncio.create_task(self._receive_loop(), name="receive"),
            asyncio.create_task(self._maintenance_loop(), name="maintenance"),
        ]
        await stop.wait()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _receive_loop(self) -> None:
        async for message in self._transport.receive():
            await self.process(message)

    async def _maintenance_loop(self) -> None:
        while True:
            await self._clock.sleep(self._interval)
            await self.sweep()

    async def process(self, message: InboundMessage) -> None:
        """Answer one inbound message, unless it was already answered."""
        if self._store.seen_inbound(message.id):
            return
        self._store.record_inbound(message)
        try:
            replies = await self._handler.handle(message)
        except Exception:
            # A bug in handling one request must not stop the server answering the next.
            log.exception("handling failed", extra={"sender": mask_number(message.sender)})
            replies = []
        await self.send_all(replies)
        self._store.mark_handled(message.id, self._clock.now())

    async def send_all(self, replies: list[Reply]) -> None:
        """Send replies in order, skipping any frames the debug setting says to drop once."""
        dropped: frozenset[int] = frozenset()
        encoded = [reply for reply in replies if reply.seq is not None]
        if self._drop_once and len(encoded) > 1:
            dropped, self._drop_once = self._drop_once, frozenset()
        for index, reply in enumerate(replies):
            if reply.seq in dropped:
                log.warning("debug: dropped a frame on purpose", extra={"seq": reply.seq})
                continue
            await self._send(reply)
            if self._gap and index < len(replies) - 1:
                await self._clock.sleep(self._gap)

    async def _send(self, reply: Reply) -> SentMessage | None:
        attempt = 0
        while True:
            try:
                sent = await self._transport.send(reply.recipient, reply.text)
            except TransportError as error:
                if not error.retryable or attempt >= self._retries:
                    log.error(  # noqa: TRY400 - the message says it all; no traceback needed
                        "send failed",
                        extra={"error": str(error), "code": error.code, "attempts": attempt + 1},
                    )
                    return None
                await self._clock.sleep(2.0**attempt)
                attempt += 1
                continue
            self._store.record_outbound(sent, tag=reply.tag, seq=reply.seq, at=self._clock.now())
            return sent

    async def sweep(self) -> None:
        """Follow recent messages' delivery, resend failed ones once, and purge old data."""
        now = self._clock.now()
        for row in self._store.pending_outbound(since=now - self._retention):
            try:
                status = await self._transport.status(row.id)
            except TransportError as error:
                log.warning("status lookup failed", extra={"error": str(error)})
                continue
            if status is None:
                continue
            self._store.update_outbound(status)
            if status.is_failure and not row.retried:
                self._store.mark_retried(row.id)
                try:
                    self._budget.check(1)
                except BudgetExceededError:
                    log.warning("delivery retry refused by daily budget")
                    continue
                self._budget.charge(1)
                log.warning("resending a message the provider could not deliver")
                sent = await self._send(Reply(row.number, row.body, row.tag, row.seq))
                if sent is not None:
                    self._store.mark_retried(sent.id)
        self._store.purge(now - self._retention)
