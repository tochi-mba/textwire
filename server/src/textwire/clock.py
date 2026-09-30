"""Time, behind an interface so every timer in the server can be tested without waiting.

Nothing in the server reads the wall clock or sleeps except through a :class:`Clock`.
Production code gets :class:`SystemClock`; tests and the simulator get :class:`FakeClock`,
whose ``sleep`` returns immediately after moving time forward.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Protocol

#: A fixed, timezone-aware instant that fake clocks start from unless told otherwise.
EPOCH = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


class Clock(Protocol):
    """The server's only source of time."""

    def now(self) -> datetime:
        """The current instant, always timezone-aware UTC."""
        ...

    async def sleep(self, seconds: float) -> None:
        """Suspend the caller for ``seconds``."""
        ...


class SystemClock:
    """The real clock."""

    def now(self) -> datetime:
        """The current instant in UTC."""
        return datetime.now(UTC)

    async def sleep(self, seconds: float) -> None:
        """Sleep on the event loop."""
        await asyncio.sleep(seconds)


class FakeClock:
    """A clock that moves only when told to.

    ``sleep`` records the requested duration, advances time by it and yields to the event
    loop once, so code under test that backs off or polls runs at full speed while still
    observing time passing.
    """

    def __init__(self, start: datetime = EPOCH) -> None:
        if start.tzinfo is None:
            msg = "FakeClock needs a timezone-aware start"
            raise ValueError(msg)
        self._now = start
        self.slept: list[float] = []

    def now(self) -> datetime:
        """The fake current instant."""
        return self._now

    def advance(self, seconds: float) -> None:
        """Move time forward without sleeping."""
        self._now += timedelta(seconds=seconds)

    async def sleep(self, seconds: float) -> None:
        """Record the sleep, advance time, and let other tasks run once."""
        self.slept.append(seconds)
        self.advance(seconds)
        await asyncio.sleep(0)
