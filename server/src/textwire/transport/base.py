"""The interface every SMS provider implements, and the values that cross it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

#: Statuses after which a message's status never changes again.
FINAL_STATUSES = frozenset({"delivered", "undelivered", "failed", "received", "canceled", "read"})
#: Final statuses that mean the message did not reach the phone.
FAILED_STATUSES = frozenset({"undelivered", "failed", "canceled"})


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """An SMS that arrived at the server's number."""

    id: str
    sender: str
    recipient: str
    text: str
    received_at: datetime


@dataclass(frozen=True, slots=True)
class SentMessage:
    """An SMS the provider accepted for delivery."""

    id: str
    recipient: str
    text: str


@dataclass(frozen=True, slots=True)
class DeliveryStatus:
    """What the provider knows about a sent message."""

    id: str
    status: str
    price: float | None = None
    price_unit: str | None = None
    error_code: int | None = None

    @property
    def is_final(self) -> bool:
        """Whether the status can no longer change."""
        return self.status in FINAL_STATUSES

    @property
    def is_failure(self) -> bool:
        """Whether the message is known not to have arrived."""
        return self.status in FAILED_STATUSES


class TransportError(Exception):
    """The provider refused or failed a request."""

    def __init__(self, message: str, *, retryable: bool, code: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.code = code


class Transport(Protocol):
    """An SMS provider the server receives from and sends through."""

    def receive(self) -> AsyncIterator[InboundMessage]:
        """Inbound messages as they arrive, forever. The same message may be yielded twice."""
        ...

    async def send(self, recipient: str, text: str) -> SentMessage:
        """Hand one single-segment SMS to the provider."""
        ...

    async def status(self, message_id: str) -> DeliveryStatus | None:
        """The provider's current view of a sent message, if it has one."""
        ...

    async def aclose(self) -> None:
        """Release connections."""
        ...
