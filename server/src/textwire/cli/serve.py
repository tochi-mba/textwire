"""``textwire serve``: run the real server, and ``textwire probe``: send one test frame.

``serve`` builds the configured transport, wires the components, and serves the dashboard
with the dispatcher running inside its lifespan, until interrupted. ``probe`` sends a single
frame whose body holds every byte value the chosen alphabet must carry, so the phone's
Diagnostics screen can say whether the route preserved every character (docs/OPERATIONS.md
section 5).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

import uvicorn

from textwire.api.app import create_app
from textwire.clock import SystemClock
from textwire.config import TransportKind, load_settings
from textwire.logs import configure_logging, mask_number
from textwire.service.probe import probe_frame
from textwire.service.store import Store
from textwire.service.wiring import build_components
from textwire.transport.twilio import TwilioClient, TwilioTransport

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI

    from textwire.clock import Clock
    from textwire.config import Settings
    from textwire.transport.base import Transport

    type Runner = Callable[[FastAPI, Settings], Awaitable[None]]

log = logging.getLogger(__name__)


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


async def _uvicorn(app: FastAPI, settings: Settings) -> None:
    """Serve ``app`` with uvicorn until the process is told to stop."""
    config = uvicorn.Config(
        app, host=settings.host, port=settings.port, log_config=None, access_log=False
    )
    await uvicorn.Server(config).serve()


async def serve(settings: Settings | None = None, *, runner: Runner | None = None) -> int:
    """Run the server: the dispatcher and the dashboard in one process, until interrupted."""
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
    app = create_app(components)
    log.info(
        "serving",
        extra={
            "transport": settings.transport.value,
            "number": mask_number(settings.twilio_number),
            "allowed": len(settings.allowed_numbers),
            "alphabet": settings.frame_alphabet.value,
            "dashboard": f"http://{settings.host}:{settings.port}/",
        },
    )
    try:
        await (runner if runner is not None else _uvicorn)(app, settings)
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
