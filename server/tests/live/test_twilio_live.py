"""Real SMS through the real account. Marked ``live``; never selected by default.

Run from ``server/`` with the account in ``.env`` and the target phone in the environment::

    TEXTWIRE_LIVE_TARGET=+447700900123 make test-live

It sends exactly one probe frame and costs one outbound SMS. Record the result and the cost
in docs/ACCEPTANCE.md.
"""

from __future__ import annotations

import os

import pytest

from textwire.cli.serve import probe
from textwire.config import load_settings

pytestmark = pytest.mark.live


@pytest.fixture
def target() -> str:
    number = os.environ.get("TEXTWIRE_LIVE_TARGET", "")
    if not number:
        pytest.skip("set TEXTWIRE_LIVE_TARGET to the phone that should receive the probe")
    return number


async def test_one_probe_frame_reaches_the_phone(target: str) -> None:
    settings = load_settings()
    assert settings.transport_problems() == [], "complete server/.env first"
    assert await probe(target, settings) == 0
