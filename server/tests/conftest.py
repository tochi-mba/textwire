"""Fixtures shared by every test.

The phone numbers come from Ofcom's range reserved for drama (07700 900000 to 900999), so
no test can ever text a real person.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from textwire.clock import FakeClock
from textwire.config import ENV_PREFIX, Settings

#: The phone that makes requests in tests.
PHONE = "+447700900123"
#: A second allowed phone, for tests about keeping numbers apart.
OTHER_PHONE = "+447700900456"
#: A sender that is not allowed.
STRANGER = "+447700900999"
#: The server's own number.
SERVER = "+447700900000"

#: The repository root: the directory holding ``protocol/`` and ``server/``.
REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = REPO_ROOT / "server"


def build_settings(**overrides: Any) -> Settings:
    """Settings for tests: no .env file, one allowed phone, Twilio credentials filled in."""
    defaults: dict[str, Any] = {
        "_env_file": None,
        "allowed_numbers": (PHONE,),
        "twilio_account_sid": "AC" + "0" * 32,
        "twilio_auth_token": "test-auth-token",
        "twilio_number": SERVER,
    }
    return Settings(**{**defaults, **overrides})


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test sees the developer's own ``TEXTWIRE_*`` variables."""
    for key in list(os.environ):
        if key.startswith(ENV_PREFIX):
            monkeypatch.delenv(key)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Default test settings with a private data directory."""
    return build_settings(data_dir=tmp_path / "data")


@pytest.fixture
def clock() -> FakeClock:
    """A clock that starts at 2026-09-30 12:00 UTC and moves only when told."""
    return FakeClock()
