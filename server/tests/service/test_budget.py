from __future__ import annotations

from datetime import date

import pytest

from tests.service.conftest import memory_store
from textwire.clock import FakeClock
from textwire.service.budget import Budget, BudgetExceededError
from textwire.service.store import Store
from textwire.transport.base import DeliveryStatus, SentMessage


def _budget(clock: FakeClock, limit: int = 10) -> tuple[Budget, Store]:
    store = memory_store()
    return Budget(store, clock, daily_limit=limit, price_per_segment=0.05, currency="USD"), store


def test_charges_add_up_to_the_limit_and_no_further(clock: FakeClock) -> None:
    budget, _ = _budget(clock)
    budget.check(10)
    budget.charge(7)
    assert budget.used() == 7
    budget.check(3)
    with pytest.raises(BudgetExceededError) as caught:
        budget.check(4)
    assert (caught.value.used, caught.value.limit) == (7, 10)
    assert caught.value.status_text == "E budget 7/10"


def test_a_new_utc_day_starts_from_zero(clock: FakeClock) -> None:
    budget, _ = _budget(clock)
    budget.charge(10)
    clock.advance(12 * 3600)
    assert budget.used() == 0
    budget.check(10)


def test_the_summary_has_estimated_and_actual_cost(clock: FakeClock) -> None:
    budget, store = _budget(clock)
    budget.charge(4)
    store.record_outbound(SentMessage("SM1", "+447700900123", "x"), tag=1, seq=0, at=clock.now())
    store.update_outbound(DeliveryStatus("SM1", "delivered", 0.056, "USD"))
    summary = budget.summary()
    assert summary.day == date(2026, 9, 30)
    assert (summary.used, summary.limit, summary.currency) == (4, 10, "USD")
    assert round(summary.estimated_cost, 2) == 0.2
    assert summary.actual_cost == 0.056
