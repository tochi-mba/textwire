"""The daily segment budget (ADR-0012): a hard cap on what a day can cost."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from textwire.clock import Clock
    from textwire.service.store import Store


class BudgetExceededError(Exception):
    """A reply would take the day past its budget."""

    def __init__(self, used: int, limit: int) -> None:
        super().__init__(f"{used}/{limit}")
        self.used = used
        self.limit = limit

    @property
    def status_text(self) -> str:
        """The status line the phone is sent: ``E budget 200/200``."""
        return f"E budget {self.used}/{self.limit}"


@dataclass(frozen=True, slots=True)
class BudgetSummary:
    """One UTC day's usage."""

    day: date
    used: int
    limit: int
    estimated_cost: float
    actual_cost: float
    currency: str


class Budget:
    """Checks and charges outbound segments against the day's limit (UTC days)."""

    def __init__(
        self,
        store: Store,
        clock: Clock,
        *,
        daily_limit: int,
        price_per_segment: float,
        currency: str,
    ) -> None:
        self._store = store
        self._clock = clock
        self._limit = daily_limit
        self._price = price_per_segment
        self._currency = currency

    def _today(self) -> date:
        return self._clock.now().date()

    def used(self) -> int:
        """Segments charged today."""
        return self._store.segments_on(self._today())[0]

    def check(self, segments: int) -> None:
        """Raise :class:`BudgetExceededError` if ``segments`` more would pass today's limit."""
        used = self.used()
        if used + segments > self._limit:
            raise BudgetExceededError(used, self._limit)

    def charge(self, segments: int) -> None:
        """Charge ``segments`` to today, with their estimated cost."""
        self._store.add_segments(self._today(), segments, segments * self._price)

    def summary(self) -> BudgetSummary:
        """Today's usage, the estimate, and what the provider has actually charged so far."""
        today = self._today()
        used, estimated = self._store.segments_on(today)
        actual, _unit = self._store.actual_cost(today)
        return BudgetSummary(today, used, self._limit, estimated, actual, self._currency)
