"""The simulator session: the real server and a virtual phone, talking over the fake transport.

``textwire simulate`` runs one of these in the terminal. It speaks the same short commands a
person would text, keeps track of the page being read, and prints each reply the way the app
lays it out.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textwire.protocol.envelope import Kind
from textwire.protocol.tags import encode_tag
from textwire.service.wiring import build_components
from textwire.simulate.phone import Page, PlainReply, VirtualPhone
from textwire.transport.fake import FakeTransport

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from textwire.clock import Clock
    from textwire.config import Settings
    from textwire.content.fetch import Fetcher
    from textwire.content.search import SearchProvider
    from textwire.service.store import Store
    from textwire.simulate.phone import Outcome

#: The virtual phone's number: Ofcom's drama range.
PHONE_NUMBER = "+447700900123"

HELP = """Commands (the same ones you would text):
  g <address>     open a page             s <words>     search
  l <n>           follow link n           n / b         next / previous page
  p <n>           page n                  ?             usage today
  h               server help             q             quit
Add ! after the letter for a plain-text reply, as any phone would get: s! weather london"""


@dataclass
class Reading:
    """The document on screen: the tag of any reply of it, and which page is showing."""

    tag: int
    page: int
    pages: int


def render(outcome: Outcome) -> str:
    """A reply as the terminal shows it."""
    match outcome:
        case Page(tag, envelope, frames, resends, seconds):
            note = f", {resends} resend request(s)" if resends else ""
            footer = (
                f"-- page {envelope.page}/{envelope.pages} | {frames} SMS | "
                f"{seconds:.1f} s{note} | reply {encode_tag(tag)}"
            )
            return f"{envelope.text}\n\n{footer}"
        case PlainReply(_tag, messages):
            return "\n".join(messages) + f"\n\n-- {len(messages)} plain SMS"
    return (
        f"-- reply {encode_tag(outcome.tag)} stopped after "
        f"{outcome.received}/{outcome.total or '?'} frames; "
        f"missing {', '.join(map(str, outcome.missing)) or 'everything'}"
    )


class Session:
    """A running server, a virtual phone, and what is being read."""

    def __init__(
        self,
        settings: Settings,
        *,
        fetcher: Fetcher,
        search: SearchProvider,
        store: Store,
        clock: Clock,
        nak_after: float,
    ) -> None:
        self.transport = FakeTransport()
        self.components = build_components(
            settings,
            transport=self.transport,
            fetcher=fetcher,
            search=search,
            clock=clock,
            store=store,
        )
        self.phone = VirtualPhone(
            transport=self.transport,
            number=PHONE_NUMBER,
            dictionary=self.components.dictionary,
            clock=clock,
            nak_after=nak_after,
        )
        self.reading: Reading | None = None
        self._stop = asyncio.Event()
        self._server: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Session:
        self._server = asyncio.create_task(self.components.dispatcher.run(self._stop))
        return self

    async def __aexit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._server is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._server
        await self.components.aclose()

    def _translate(self, command: str) -> str | None:
        """The request text for a simulator command, or None when it needs a page on screen."""
        head, _, rest = command.partition(" ")
        verb, plain = head.rstrip("!").lower(), "!" if head.endswith("!") else ""
        reading = self.reading
        if verb in ("n", "b"):
            if reading is None:
                return None
            page = reading.page + (1 if verb == "n" else -1)
            return f"p{plain} {encode_tag(reading.tag)} {max(1, min(page, reading.pages))}"
        if verb in ("l", "p") and rest.strip().isdigit():
            if reading is None:
                return None
            return f"{verb}{plain} {encode_tag(reading.tag)} {rest.strip()}"
        return command

    async def run_command(self, command: str) -> str:
        """Carry out one command and return what to print."""
        command = command.strip()
        if not command:
            return ""
        if command.lower() in ("help", "help!"):
            return HELP
        request = self._translate(command)
        if request is None:
            return "-- open a page or run a search first"
        outcome = await self.phone.ask(request)
        if isinstance(outcome, Page) and outcome.envelope.kind is not Kind.STATUS:
            self.reading = Reading(outcome.tag, outcome.envelope.page, outcome.envelope.pages)
        return render(outcome)


async def repl(
    session: Session,
    read: Callable[[str], Awaitable[str | None]],
    write: Callable[[str], object],
) -> None:
    """Read commands until ``q`` or the end of input, printing each reply."""
    write("textwire simulator. Type help for commands, q to quit.")
    while True:
        line = await read("> ")
        if line is None or line.strip().lower() in ("q", "quit", "exit"):
            return
        output = await session.run_command(line)
        if output:
            write(output)
