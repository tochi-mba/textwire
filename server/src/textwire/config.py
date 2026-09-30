"""Runtime configuration.

Every setting is an environment variable prefixed ``TEXTWIRE_``, read from the process
environment and, for local runs, from ``server/.env``. Unknown variables under the prefix
are refused at startup, so a typo fails loudly instead of silently running on a default.
The full list, with what each one costs or risks, is in ``server/.env.example`` and
``docs/OPERATIONS.md``.
"""

from __future__ import annotations

import os
import re
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from textwire.protocol.alphabets import Alphabet

if TYPE_CHECKING:
    from collections.abc import Mapping

ENV_PREFIX = "TEXTWIRE_"

#: A phone number in E.164 form: a plus, a country code that does not start with 0, and up
#: to fifteen digits in all.
E164 = re.compile(r"\+[1-9]\d{6,14}")

#: A desktop browser's user agent with our name appended. Sites that refuse unknown clients
#: accept this; sites that want to know who is asking can still see it.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0 "
    "textwire/0.1 (+https://github.com/tochi-mba/textwire)"
)

#: The highest frame sequence number a response can have (255 frames, numbered from 0).
MAX_SEQ = 254


class LogFormat(StrEnum):
    """How log records are rendered."""

    JSON = "json"
    CONSOLE = "console"


class TransportKind(StrEnum):
    """Which SMS provider the server uses."""

    TWILIO = "twilio"
    GATEWAY = "gateway"


class InboundMode(StrEnum):
    """How inbound SMS reach the server when the transport is Twilio."""

    POLL = "poll"
    WEBHOOK = "webhook"


PositiveInt = Annotated[int, Field(gt=0)]
PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
FrameCount = Annotated[int, Field(ge=1, le=255)]


class Settings(BaseSettings):
    """The complete runtime configuration. Field ``foo`` is ``TEXTWIRE_FOO``."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    # Process
    environment: str = "local"
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.CONSOLE
    host: str = "127.0.0.1"
    port: PositiveInt = 8140
    data_dir: Path = Path("data")

    # Who may use the server: comma-separated E.164 numbers. Everyone else is ignored.
    allowed_numbers: Annotated[tuple[str, ...], NoDecode] = ()

    # Transport
    transport: TransportKind = TransportKind.TWILIO
    inbound: InboundMode = InboundMode.POLL
    poll_seconds: PositiveFloat = 3.0
    lookback_minutes: PositiveInt = 60
    send_retries: NonNegativeInt = 3
    send_gap_ms: NonNegativeInt = 0
    status_interval_seconds: PositiveFloat = 60.0
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    twilio_number: str = ""
    twilio_api_base: str = "https://api.twilio.com"
    public_base_url: str = ""
    gateway_url: str = ""
    gateway_username: str = ""
    gateway_password: SecretStr = SecretStr("")

    # Money
    daily_segment_budget: PositiveInt = 200
    price_per_segment: Annotated[float, Field(ge=0)] = 0.056
    currency: str = "USD"

    # Pages and searches
    # b64 is safe on any route; z85g carries 6% more per SMS and needs the alphabet probe to
    # have passed on your route first (docs/OPERATIONS.md).
    frame_alphabet: Alphabet = Alphabet.BASE64URL
    page_frames: FrameCount = 12
    max_page_frames: FrameCount = 40
    plain_messages: Annotated[int, Field(ge=1, le=9)] = 4
    search_results: Annotated[int, Field(ge=1, le=10)] = 5
    search_region: str = "uk-en"
    search_backend: str = "auto"
    search_timeout_seconds: PositiveFloat = 20.0
    fetch_timeout_seconds: PositiveFloat = 20.0
    fetch_max_bytes: PositiveInt = 3_000_000
    user_agent: str = DEFAULT_USER_AGENT

    # Retention and rate limits
    retention_hours: PositiveInt = 24
    notice_interval_minutes: PositiveInt = 10

    # Debugging: frame sequence numbers to skip, once, in the first multi-frame response
    # after startup. Used by the on-device acceptance run to exercise resend.
    debug_drop_once: Annotated[tuple[int, ...], NoDecode] = ()

    @field_validator("allowed_numbers", mode="before")
    @classmethod
    def _split_numbers(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("allowed_numbers")
    @classmethod
    def _numbers_are_e164(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for number in value:
            if not E164.fullmatch(number):
                msg = (
                    f"TEXTWIRE_ALLOWED_NUMBERS: {number!r} is not an E.164 number "
                    "like +447700900123"
                )
                raise ValueError(msg)
        return value

    @field_validator("debug_drop_once", mode="before")
    @classmethod
    def _split_seqs(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("debug_drop_once")
    @classmethod
    def _seqs_in_range(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        for seq in value:
            if not 0 <= seq <= MAX_SEQ:
                msg = f"TEXTWIRE_DEBUG_DROP_ONCE: {seq} is not a frame number from 0 to {MAX_SEQ}"
                raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.page_frames > self.max_page_frames:
            msg = "TEXTWIRE_PAGE_FRAMES must not exceed TEXTWIRE_MAX_PAGE_FRAMES"
            raise ValueError(msg)
        if self.twilio_number and not E164.fullmatch(self.twilio_number):
            msg = "TEXTWIRE_TWILIO_NUMBER must be an E.164 number like +447700900000"
            raise ValueError(msg)
        return self

    @property
    def database_path(self) -> Path:
        """Where the SQLite database lives."""
        return self.data_dir / "textwire.db"

    def transport_problems(self) -> list[str]:
        """What the configured transport still needs; empty when it can run."""
        if self.transport is TransportKind.TWILIO:
            needed = {
                "TEXTWIRE_TWILIO_ACCOUNT_SID": self.twilio_account_sid,
                "TEXTWIRE_TWILIO_AUTH_TOKEN": self.twilio_auth_token.get_secret_value(),
                "TEXTWIRE_TWILIO_NUMBER": self.twilio_number,
            }
            if self.inbound is InboundMode.WEBHOOK:
                needed["TEXTWIRE_PUBLIC_BASE_URL"] = self.public_base_url
        else:
            needed = {
                "TEXTWIRE_GATEWAY_URL": self.gateway_url,
                "TEXTWIRE_GATEWAY_USERNAME": self.gateway_username,
                "TEXTWIRE_GATEWAY_PASSWORD": self.gateway_password.get_secret_value(),
            }
        problems = [f"{name} is not set" for name, value in needed.items() if not value]
        if not self.allowed_numbers:
            problems.append("TEXTWIRE_ALLOWED_NUMBERS is empty, so every request is ignored")
        return problems


def check_for_unknown_env_vars(environ: Mapping[str, str] | None = None) -> None:
    """Refuse unknown ``TEXTWIRE_*`` variables so a typo fails at startup."""
    known = {ENV_PREFIX + name.upper() for name in Settings.model_fields}
    source = environ if environ is not None else os.environ
    unknown = sorted(key for key in source if key.startswith(ENV_PREFIX) and key not in known)
    if unknown:
        msg = "unknown environment variables: " + ", ".join(unknown)
        raise RuntimeError(msg)


def load_settings() -> Settings:
    """Load the settings, refusing unknown variables under the prefix."""
    check_for_unknown_env_vars()
    return Settings()
