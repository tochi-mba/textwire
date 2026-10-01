"""The FastAPI application: health, the dashboard page and the JSON it draws.

Bound to localhost by default. It carries no authentication because it is an operator's
window onto their own machine; ``docs/OPERATIONS.md`` says what exposing it would need.
The dispatcher runs inside the app's lifespan, so ``textwire serve`` is one process.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from textwire import __version__
from textwire.api.dashboard import DASHBOARD_HTML
from textwire.logs import mask_number
from textwire.service.budget import BudgetExceededError
from textwire.service.probe import probe_frame

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from textwire.config import Settings
    from textwire.service.wiring import Components

#: How many recent requests, documents and log lines the dashboard shows.
RECENT = 30


class ProbeRequest(BaseModel):
    """Who to send a probe frame to."""

    number: str = Field(min_length=7, max_length=16)


def _overview(components: Components) -> dict[str, Any]:
    settings = components.settings
    summary = components.budget.summary()
    now = components.clock.now()
    recent = components.store.recent_inbound(RECENT)
    documents = components.store.recent_documents(RECENT)
    return {
        "version": __version__,
        "environment": settings.environment,
        "transport": settings.transport.value,
        "number": mask_number(settings.twilio_number) if settings.twilio_number else "",
        "alphabet": settings.frame_alphabet.value,
        "allowed": len(settings.allowed_numbers),
        "page_frames": settings.page_frames,
        "now": now.isoformat(timespec="seconds"),
        "budget": {
            "day": summary.day.isoformat(),
            "used": summary.used,
            "limit": summary.limit,
            "estimated_cost": round(summary.estimated_cost, 2),
            "actual_cost": round(summary.actual_cost, 4),
            "currency": summary.currency,
        },
        "outbound_today": components.store.outbound_on(now.date()),
        "requests": [
            {
                "id": row.id,
                "number": mask_number(row.number),
                "body": row.body,
                "received_at": row.received_at,
                "handled_at": row.handled_at,
                "replies": row.replies,
            }
            for row in recent
        ],
        "documents": [
            {
                "tag": doc.tag,
                "number": mask_number(doc.number),
                "kind": doc.kind,
                "title": doc.title,
                "created_at": doc.created_at,
                "page_size": doc.page_size,
                "plain": doc.plain,
            }
            for doc in documents
        ],
    }


def create_app(components: Components | None = None, *, run_dispatcher: bool = True) -> FastAPI:
    """The application. With ``components`` the dispatcher runs for the app's lifetime."""

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        stop = asyncio.Event()
        task = None
        if components is not None and run_dispatcher:
            task = asyncio.create_task(components.dispatcher.run(stop), name="dispatcher")
        app.state.started = True
        try:
            yield
        finally:
            stop.set()
            if task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="textwire", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None
    )
    app.state.components = components

    @app.get("/healthy")
    async def healthy() -> dict[str, Any]:
        """Alive: no I/O, never fails."""
        settings: Settings | None = components.settings if components is not None else None
        return {
            "status": "alive",
            "version": __version__,
            "environment": settings.environment if settings is not None else "",
        }

    @app.get("/ready")
    async def ready() -> JSONResponse:
        """Ready to answer requests: the store answers and the transport is configured."""
        checks: dict[str, bool] = {"components": components is not None}
        if components is not None:
            checks["store"] = components.store.ping()
            checks["transport"] = not components.settings.transport_problems()
        ready = all(checks.values())
        return JSONResponse(
            {"status": "ready" if ready else "degraded", "checks": checks},
            HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
        )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        """The operator's page; it draws ``/api/overview`` every few seconds."""
        return DASHBOARD_HTML

    @app.get("/api/overview")
    async def overview() -> dict[str, Any]:
        """Everything the dashboard shows."""
        if components is None:
            raise HTTPException(503, "the server is not wired to a transport")
        return _overview(components)

    @app.post("/api/probe")
    async def send_probe(body: ProbeRequest) -> dict[str, Any]:
        """Send one probe frame to an allowed number (docs/OPERATIONS.md section 5)."""
        if components is None:
            raise HTTPException(503, "the server is not wired to a transport")
        if body.number not in components.settings.allowed_numbers:
            raise HTTPException(403, "only numbers in TEXTWIRE_ALLOWED_NUMBERS can be probed")
        try:
            components.budget.check(1)
        except BudgetExceededError as exceeded:
            raise HTTPException(429, exceeded.status_text) from exceeded
        text = probe_frame(components.settings)
        sent = await components.transport.send(body.number, text)
        components.store.record_outbound(sent, tag=None, seq=None, at=components.clock.now())
        components.budget.charge(1)
        return {"id": sent.id, "characters": len(text), "to": mask_number(body.number)}

    return app


def retention(settings: Settings) -> timedelta:
    """How long the dashboard's history reaches back: the store's retention."""
    return timedelta(hours=settings.retention_hours)
