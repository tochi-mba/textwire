from __future__ import annotations

import pytest

from tests.conftest import OTHER_PHONE, PHONE, STRANGER, build_settings
from tests.service.conftest import ARTICLE, NOTICE, Rig, build_rig, tag
from textwire.content.fakes import html_page
from textwire.content.search import SearchError, SearchFault
from textwire.protocol.envelope import Kind
from textwire.protocol.gsm7 import is_gsm7, septets
from textwire.service.handler import HandlerSettings


async def test_strangers_get_nothing_and_cost_nothing(rig: Rig) -> None:
    assert await rig.ask("a7 ?", sender=STRANGER) == []
    assert rig.budget.used() == 0


async def test_a_page_arrives_as_frames_under_the_request_tag(rig: Rig) -> None:
    replies = await rig.ask(f"a7 g {ARTICLE}")
    assert {reply.tag for reply in replies} == {tag("a7")}
    assert [reply.seq for reply in replies] == list(range(len(replies)))
    assert all(reply.recipient == PHONE for reply in replies)
    assert 1 < len(replies) <= 12
    envelope = rig.envelope(replies)
    assert envelope.kind is Kind.PAGE
    assert envelope.page == 1
    assert envelope.text.startswith("# Village gets its first text-only library\n\n")
    assert rig.budget.used() == len(replies)
    assert rig.fetcher.requested == [ARTICLE]


async def test_the_size_can_be_chosen_and_is_capped(rig: Rig) -> None:
    small = await rig.ask(f"a7 g2 {ARTICLE}")
    assert len(small) <= 2
    assert rig.envelope(small).pages > 1
    capped = build_rig(max_page_frames=3)
    assert len(await capped.ask(f"a7 g200 {ARTICLE}")) <= 3


async def test_untagged_requests_get_server_tags_in_turn(rig: Rig) -> None:
    first = await rig.ask("s bbc weather london")
    second = await rig.ask("?")
    assert first[0].tag == tag("z0")
    assert second[0].tag == tag("z1")
    assert rig.envelope(first).kind is Kind.SEARCH
    assert rig.search.queries == ["bbc weather london"]


async def test_later_pages_come_by_the_document_s_tag_or_any_page_s(rig: Rig) -> None:
    first = rig.envelope(await rig.ask(f"a7 g2 {ARTICLE}"))
    second = rig.envelope(await rig.ask("b0 p a7 2"))
    third = rig.envelope(await rig.ask("b1 p b0 3"))
    assert (second.page, second.pages) == (2, first.pages)
    assert third.page == 3
    assert second.text.startswith("# Village gets its first text-only library")


async def test_asking_for_a_page_past_the_end_says_how_many_there_are(rig: Rig) -> None:
    pages = rig.envelope(await rig.ask(f"a7 g {ARTICLE}")).pages
    reply = rig.envelope(await rig.ask("b0 p a7 99"))
    assert (reply.kind, reply.text) == (Kind.STATUS, f"E page range 99/{pages}")


async def test_an_unknown_tag_is_reported(rig: Rig) -> None:
    assert rig.envelope(await rig.ask("b0 p q9 2")).text == "E page unknown q9"
    assert rig.envelope(await rig.ask("b1 l q9 2")).text == "E link unknown q9"


async def test_documents_are_private_to_each_number(rig: Rig) -> None:
    await rig.ask(f"a7 g {ARTICLE}")
    assert rig.envelope(await rig.ask("b0 p a7 1", sender=OTHER_PHONE)).text == "E page unknown a7"


async def test_links_are_followed_by_number(rig: Rig) -> None:
    rig.fetcher.pages["https://example.org/council"] = html_page(
        "https://example.org/council",
        "<html><head><title>Council</title></head><body>"
        + "".join(f"<p>Paragraph {n} about the parish council.</p>" for n in range(4))
        + "</body></html>",
    )
    await rig.ask(f"a7 g {ARTICLE}")
    followed = rig.envelope(await rig.ask("b0 l a7 3"))
    assert followed.text.startswith("# Council")
    assert rig.fetcher.requested[-1] == "https://example.org/council"


async def test_a_link_past_the_table_says_how_many_links_there_are(rig: Rig) -> None:
    await rig.ask(f"a7 g {ARTICLE}")
    assert rig.envelope(await rig.ask("b0 l a7 9")).text == "E link range 9/3"


async def test_a_page_that_cannot_be_fetched_is_a_status(rig: Rig) -> None:
    reply = await rig.ask("a7 g https://missing.example/")
    assert len(reply) == 1
    envelope = rig.envelope(reply)
    assert (envelope.kind, envelope.text) == (Kind.STATUS, "E fetch status 404")
    assert rig.budget.used() == 1


async def test_a_failed_search_is_a_status(rig: Rig) -> None:
    rig.search.results["broken"] = SearchError(SearchFault.FAILED)
    assert rig.envelope(await rig.ask("a7 s broken")).text == "E search failed"


async def test_frames_can_be_resent_verbatim_under_their_own_tag(rig: Rig) -> None:
    original = await rig.ask(f"a7 g {ARTICLE}")
    resent = await rig.ask("b0 r a7 0,2")
    assert [(reply.tag, reply.seq, reply.text) for reply in resent] == [
        (tag("a7"), 0, original[0].text),
        (tag("a7"), 2, original[2].text),
    ]
    assert rig.budget.used() == len(original) + 2


async def test_frames_that_are_gone_cannot_be_resent(rig: Rig) -> None:
    reply = await rig.ask("b0 r a7 0")
    assert reply[0].tag == tag("b0")
    assert rig.envelope(reply).text == "E resend unknown a7"


async def test_a_status_reply_can_itself_be_resent(rig: Rig) -> None:
    status = await rig.ask("a7 ?")
    assert await rig.ask("b0 r a7 0") == [status[0].__class__(PHONE, status[0].text, tag("a7"), 0)]


async def test_a_reused_tag_forgets_what_it_meant_before(rig: Rig) -> None:
    await rig.ask(f"a7 g {ARTICLE}")
    await rig.ask("a7 ?")
    assert rig.envelope(await rig.ask("b0 p a7 2")).text == "E page unknown a7"
    assert rig.envelope(await rig.ask("b1 r a7 5")).text == "E resend unknown a7"


async def test_usage_reports_today_s_count_and_estimate(rig: Rig) -> None:
    await rig.ask("a7 s bbc weather london")
    used = rig.budget.used()
    text = rig.envelope(await rig.ask("b0 ?")).text
    assert text == f"I 2026-09-30 {used}/200 sms ~{used * 0.056:.2f} USD v9.9.9"


async def test_help_is_a_page(rig: Rig) -> None:
    envelope = rig.envelope(await rig.ask("h"))
    assert envelope.kind is Kind.HELP
    assert envelope.text.startswith("# textwire help")


async def test_plain_replies_are_readable_and_point_to_the_next_page(rig: Rig) -> None:
    replies = await rig.ask("a7 s! bbc weather london")
    assert all(reply.seq is None and reply.tag == tag("a7") for reply in replies)
    assert replies[0].text.startswith("[a7 1/4] # Search: bbc weather london")
    assert replies[-1].text.endswith("\n>> p! a7 2")
    assert all(is_gsm7(reply.text) and septets(reply.text) <= 160 for reply in replies)
    following = await rig.ask("b0 p! a7 2")
    assert following[0].text.startswith("[b0 1/")


async def test_the_last_plain_page_has_no_footer(rig: Rig) -> None:
    replies = await rig.ask("a7 s9! bbc weather london")
    assert ">>" not in replies[-1].text


async def test_plain_errors_are_plain(rig: Rig) -> None:
    assert [reply.text for reply in await rig.ask("a7 g! https://missing.example/")] == [
        "[a7 1/1] E fetch status 404"
    ]


async def test_paging_keeps_the_size_of_the_same_mode(rig: Rig) -> None:
    await rig.ask(f"a7 g3 {ARTICLE}")
    assert len(await rig.ask("b0 p a7 2")) <= 3
    plain = await rig.ask("b1 p! a7 1")
    assert len(plain) == 4  # the plain default, not the encoded size


async def test_help_in_plain_text(rig: Rig) -> None:
    replies = await rig.ask("h!")
    assert replies[0].text.startswith("[z0 1/")
    assert "# textwire help" in replies[0].text


async def test_a_bad_request_gets_one_plain_notice_per_interval(rig: Rig) -> None:
    first = await rig.ask("hello there")
    assert [reply.text for reply in first] == ["E request unknown request. Send h! for help."]
    assert first[0].tag is None
    assert await rig.ask("still wrong") == []
    rig.clock.advance(NOTICE.total_seconds())
    assert len(await rig.ask("still wrong")) == 1
    assert rig.budget.used() == 2


async def test_a_long_bad_request_notice_still_fits_one_sms(rig: Rig) -> None:
    replies = await rig.ask("g " + "x" * 2100)
    assert replies[0].text == "E request url too long. Send h! for help."


async def test_an_exhausted_budget_refuses_before_fetching() -> None:
    rig = build_rig(limit=5)
    reply = await rig.ask(f"a7 g {ARTICLE}")
    assert rig.envelope(reply).text == "E budget 0/5"
    assert rig.fetcher.requested == []
    assert await rig.ask(f"a8 g {ARTICLE}") == []  # the notice is rate-limited
    assert rig.budget.used() == 1


async def test_the_exact_count_is_checked_when_the_reply_is_known() -> None:
    frames = len(await build_rig().ask(f"a7 g4 {ARTICLE}"))
    rig = build_rig(limit=frames + 1)
    await rig.ask(f"a7 g4 {ARTICLE}")
    # Paging needs no fetch, so only the exact count stands between it and the budget.
    reply = await rig.ask("b0 p a7 1")
    assert rig.envelope(reply).text == f"E budget {frames}/{frames + 1}"


async def test_plain_budget_notices_are_plain() -> None:
    rig = build_rig(limit=2)
    assert [reply.text for reply in await rig.ask("s! bbc weather london")] == [
        "[z0 1/1] E budget 0/2"
    ]


def test_handler_settings_come_from_the_server_settings() -> None:
    settings = build_settings(page_frames=8, max_page_frames=20, notice_interval_minutes=5)
    handler_settings = HandlerSettings.from_settings(settings, "1.2.3")
    assert handler_settings.allowed_numbers == frozenset({PHONE})
    assert (handler_settings.page_frames, handler_settings.max_page_frames) == (8, 20)
    assert handler_settings.notice_interval.total_seconds() == 300
    assert handler_settings.version == "1.2.3"


@pytest.mark.parametrize("text", ["a7 g", "?? ?", "z"])
async def test_every_bad_request_notice_is_one_gsm7_sms(text: str) -> None:
    rig = build_rig()
    [reply] = await rig.ask(text)
    assert is_gsm7(reply.text)
    assert len(reply.text) <= 160
