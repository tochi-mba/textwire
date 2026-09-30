from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from textwire.clock import EPOCH, FakeClock, SystemClock


def test_the_system_clock_is_timezone_aware() -> None:
    assert SystemClock().now().tzinfo is UTC


async def test_the_system_clock_sleeps_on_the_event_loop() -> None:
    before = datetime.now(UTC)
    await SystemClock().sleep(0)
    assert datetime.now(UTC) >= before


def test_a_fake_clock_starts_at_the_epoch_and_advances_on_request() -> None:
    clock = FakeClock()
    assert clock.now() == EPOCH
    clock.advance(90)
    assert clock.now() == EPOCH + timedelta(seconds=90)


async def test_a_fake_clock_sleep_records_and_advances() -> None:
    clock = FakeClock()
    await clock.sleep(2.5)
    await clock.sleep(1)
    assert clock.slept == [2.5, 1]
    assert clock.now() == EPOCH + timedelta(seconds=3.5)


def test_a_fake_clock_refuses_a_naive_start() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FakeClock(datetime(2026, 1, 1))  # noqa: DTZ001 - the point of the test
