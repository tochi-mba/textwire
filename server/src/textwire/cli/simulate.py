"""``textwire simulate``: browse from the terminal through the real server and a virtual phone.

With ``--offline`` the pages and searches come from ``protocol/fixtures``, so it works with no
network at all. Without it, pages and searches are real; only the SMS are simulated, and
nothing is sent or charged.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from textwire.clock import SystemClock
from textwire.config import load_settings
from textwire.content.fakes import load_fixtures
from textwire.service.store import Store
from textwire.service.wiring import default_fetcher, default_search
from textwire.simulate.session import PHONE_NUMBER, Session, repl
from textwire.vectors import find_repo_root

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from textwire.config import Settings
    from textwire.content.fetch import Fetcher
    from textwire.content.search import SearchProvider

FIXTURES = ("protocol", "fixtures")


async def _terminal_input(prompt: str) -> str | None:
    try:
        return await asyncio.to_thread(input, prompt)
    except EOFError:
        return None


def scripted(
    commands: Sequence[str], write: Callable[[str], object]
) -> Callable[[str], Awaitable[str | None]]:
    """A reader that types ``commands`` one at a time, echoing each, then ends the input."""
    queue = list(commands)

    async def read(prompt: str) -> str | None:
        if not queue:
            return None
        command = queue.pop(0)
        write(f"{prompt}{command}")
        return command

    return read


def simulator_settings(
    base: Settings, *, drop: tuple[int, ...], page_frames: int | None
) -> Settings:
    """The server settings for a simulation: only the virtual phone is allowed."""
    update: dict[str, object] = {"allowed_numbers": (PHONE_NUMBER,), "debug_drop_once": drop}
    if page_frames is not None:
        update["page_frames"] = page_frames
        update["max_page_frames"] = max(page_frames, base.max_page_frames)
    return base.model_copy(update=update)


async def simulate(
    *,
    offline: bool,
    commands: Sequence[str] = (),
    drop: tuple[int, ...] = (),
    nak_after: float = 3.0,
    page_frames: int | None = None,
    write: Callable[[str], object] = print,
    read: Callable[[str], Awaitable[str | None]] | None = None,
) -> int:
    """Run a simulation; ``commands`` replace the keyboard when given."""
    settings = simulator_settings(load_settings(), drop=drop, page_frames=page_frames)
    fetcher: Fetcher
    search: SearchProvider
    if offline:
        fetcher, search = load_fixtures(find_repo_root().joinpath(*FIXTURES))
        write("Offline: pages and searches come from protocol/fixtures/index.json.")
    else:
        fetcher, search = default_fetcher(settings), default_search(settings)
    session = Session(
        settings,
        fetcher=fetcher,
        search=search,
        store=Store(":memory:"),
        clock=SystemClock(),
        nak_after=nak_after,
    )
    reader = read or (scripted(commands, write) if commands else _terminal_input)
    async with session:
        await repl(session, reader, write)
    return 0
