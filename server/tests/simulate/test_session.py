from __future__ import annotations

import pytest

from tests.conftest import REPO_ROOT, build_settings
from textwire.clock import SystemClock
from textwire.content.fakes import load_fixtures
from textwire.protocol.alphabets import Alphabet
from textwire.protocol.envelope import Envelope, Kind
from textwire.service.store import Store
from textwire.simulate.phone import Incomplete, Page, PlainReply
from textwire.simulate.session import PHONE_NUMBER, Session, render, repl

ARTICLE = "https://dunmore-gazette.example/news/text-only-library"


def session(alphabet: Alphabet = Alphabet.BASE64URL, drop: tuple[int, ...] = ()) -> Session:
    fetcher, search = load_fixtures(REPO_ROOT / "protocol" / "fixtures")
    return Session(
        build_settings(
            allowed_numbers=(PHONE_NUMBER,),
            frame_alphabet=alphabet,
            debug_drop_once=drop,
            send_gap_ms=0,
        ),
        fetcher=fetcher,
        search=search,
        store=Store(":memory:"),
        clock=SystemClock(),
        nak_after=1.0,
    )


@pytest.mark.parametrize("alphabet", list(Alphabet))
async def test_browse_search_page_and_plain_replies_over_the_real_dispatcher(
    alphabet: Alphabet,
) -> None:
    async with session(alphabet) as browser:
        assert await browser.run_command("") == ""
        assert "Commands" in await browser.run_command("help")
        assert "open a page" in await browser.run_command("n")
        assert "open a page" in await browser.run_command("l 1")
        search = await browser.run_command("s bbc weather london")
        assert "BBC" in search
        assert "SMS" in search
        first = browser.reading
        assert first is not None
        assert "sms" in await browser.run_command("?")
        assert browser.reading == first
        assert "page 1/" in await browser.run_command("p 1")
        assert "page 1/" in await browser.run_command("b")
        assert "page" in await browser.run_command("n")
        assert "plain SMS" in await browser.run_command("s! bbc weather london")
        assert "page 1/" in await browser.run_command(f"g {ARTICLE}")
        assert "E link range" in await browser.run_command("l 9")
    assert browser.transport.closed


@pytest.mark.parametrize("alphabet", list(Alphabet))
async def test_a_lost_frame_is_recovered_without_refetching_the_page(alphabet: Alphabet) -> None:
    async with session(alphabet, (1,)) as browser:
        result = await browser.run_command(f"g {ARTICLE}")
        assert "1 resend request(s)" in result
        assert "page 1/" in result
        assert any(" r 00 1" in request for request in browser.phone.sent)


def test_render_reports_complete_plain_and_incomplete_replies() -> None:
    page = Page(0, Envelope(Kind.PAGE, 1, 2, "hello"), 3, 0, 1.25)
    assert render(page) == "hello\n\n-- page 1/2 | 3 SMS | 1.2 s | reply 00"
    assert render(PlainReply(0, ("one", "two"))) == "one\ntwo\n\n-- 2 plain SMS"
    assert "missing 1, 2" in render(Incomplete(0, 1, 3, (1, 2)))
    assert "0/? frames; missing everything" in render(Incomplete(0, 0, None, ()))


@pytest.mark.parametrize("ending", [None, "q", "quit", " EXIT "])
async def test_repl_prints_only_nonempty_replies_and_stops(ending: str | None) -> None:
    commands = iter(["", "help", ending])
    output: list[str] = []

    async def read(prompt: str) -> str | None:
        assert prompt == "> "
        return next(commands)

    async with session() as browser:
        await repl(browser, read, output.append)
    assert len(output) == 2
    assert "simulator" in output[0]
    assert "Commands" in output[1]


async def test_an_unstarted_session_can_be_closed() -> None:
    browser = session()
    await browser.__aexit__()
    assert browser.transport.closed
