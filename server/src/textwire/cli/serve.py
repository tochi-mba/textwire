"""``textwire serve``: run the real server, and ``textwire probe``: send one test frame.

``serve`` builds the configured transport, wires the components and runs the dispatcher
until interrupted. ``probe`` sends a single frame whose body holds every byte value the
chosen alphabet must carry, so the phone's Diagnostics screen can say whether the route
preserved every character (docs/OPERATIONS.md section 5).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from datetime import timedelta
from typing import TYPE_CHECKING

from textwire.clock import SystemClock
from textwire.config import TransportKind, load_settings
from textwire.logs import configure_logging, mask_number
from textwire.protocol.frames import Frame, body_bytes, encode_frame
from textwire.protocol.tags import TAG_COUNT
from textwire.service.store import Store
from textwire.service.wiring import build_components
from textwire.transport.twilio import TwilioClient, TwilioTransport

if TYPE_CHECKING:
    from textwire.clock import Clock
    from textwire.config import Settings
    from textwire.transport.base import Transport

log = logging.getLogger(__name__)

#: The tag a probe frame carries: the last server tag, which a phone never allocates.
PROBE_TAG = TAG_COUNT - 1


class ConfigurationError(Exception):
    """The settings cannot run the requested command."""


def build_transport(settings: Settings, store: Store, clock: Clock) -> Transport:
    """The configured SMS provider, or :class:`ConfigurationError` saying what is missing."""
    problems = settings.transport_problems()
    if problems:
        raise ConfigurationError("; ".join(problems))
    if settings.transport is not TransportKind.TWILIO:
        msg = "the Android gateway transport is not built yet; set TEXTWIRE_TRANSPORT=twilio"
        raise ConfigurationError(msg)
    client = TwilioClient(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token.get_secret_value(),
        base_url=settings.twilio_api_base,
    )
    return TwilioTransport(
        client=client,
        number=settings.twilio_number,
        store=store,
        clock=clock,
        poll_seconds=settings.poll_seconds,
        lookback=timedelta(minutes=settings.lookback_minutes),
    )


def probe_frame(settings: Settings) -> str:
    """A frame whose body cycles through every byte value the alphabet must carry."""
    size = body_bytes(settings.frame_alphabet)
    body = bytes((index * 7 + 3) % 256 for index in range(size))
    return encode_frame(Frame(tag=PROBE_TAG, seq=0, total=1, body=body), settings.frame_alphabet)


async def serve(settings: Settings | None = None, stop: asyncio.Event | None = None) -> int:
    """Run the server until ``stop`` is set or the process is interrupted."""
    settings = settings if settings is not None else load_settings()
    configure_logging(settings.log_level, settings.log_format)
    clock = SystemClock()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    store = Store(settings.database_path)
    try:
        transport = build_transport(settings, store, clock)
    except ConfigurationError as error:
        store.close()
        print(f"cannot start: {error}. Run `textwire doctor`.")
        return 2
    components = build_components(settings, transport=transport, clock=clock, store=store)
    stop = stop if stop is not None else asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(signum, stop.set)
    log.info(
        "serving",
        extra={
            "transport": settings.transport.value,
            "number": mask_number(settings.twilio_number),
            "allowed": len(settings.allowed_numbers),
            "alphabet": settings.frame_alphabet.value,
        },
    )
    try:
        await components.dispatcher.run(stop)
    finally:
        await components.aclose()
    return 0


async def probe(recipient: str, settings: Settings | None = None) -> int:
    """Send one probe frame to ``recipient`` and print what was sent."""
    settings = settings if settings is not None else load_settings()
    configure_logging(settings.log_level, settings.log_format)
    store = Store(":memory:")
    try:
        transport = build_transport(settings, store, SystemClock())
    except ConfigurationError as error:
        store.close()
        print(f"cannot probe: {error}. Run `textwire doctor`.")
        return 2
    text = probe_frame(settings)
    try:
        sent = await transport.send(recipient, text)
    finally:
        await transport.aclose()
        store.close()
    print(f"sent probe {sent.id} to {mask_number(recipient)} ({len(text)} characters):")
    print(text)
    print("On the phone, open Diagnostics: the frame must decode with no CRC error.")
    return 0
