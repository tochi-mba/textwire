from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from textwire.protocol.gsm7 import is_gsm7, septets
from textwire.protocol.plain import (
    FOOTER_SEPTETS,
    MESSAGE_SEPTETS,
    PREFIX_SEPTETS,
    format_plain_page,
    plain_pages,
)


def test_short_text_is_one_page_of_one_message() -> None:
    assert plain_pages("E budget 200/200", 4) == [["E budget 200/200"]]


def test_empty_text_is_one_empty_message() -> None:
    assert plain_pages("   ", 4) == [[""]]
    assert format_plain_page([""], "a7", None) == ["[a7 1/1]"]


def test_messages_break_at_paragraphs_then_lines_then_spaces() -> None:
    paragraph = "word " * 20  # 100 characters
    pages = plain_pages(f"{paragraph}\n\n{paragraph}\n\n{paragraph}", 9)
    assert pages == [[paragraph.strip(), paragraph.strip(), paragraph.strip()]]


def test_a_word_longer_than_a_message_is_cut() -> None:
    [[first, second]] = plain_pages("x" * 200, 9)
    assert first == "x" * (MESSAGE_SEPTETS - PREFIX_SEPTETS)
    assert second == "x" * (200 - len(first))


def test_the_prefix_is_counted_in_septets_not_characters() -> None:
    [message] = format_plain_page(["x"], "a7", None)
    assert septets(message) - 1 == PREFIX_SEPTETS


def test_a_message_full_of_chips_still_fits_one_sms() -> None:
    chips = " ".join(f"w[{n}]" for n in range(1, 60))
    for bodies in plain_pages(chips, 9):
        for message in format_plain_page(bodies, "a7", 2):
            assert septets(message) <= MESSAGE_SEPTETS


def test_the_last_message_of_a_page_leaves_room_for_the_footer() -> None:
    pages = plain_pages("word " * 200, 2)
    first_page = pages[0]
    assert septets(first_page[0]) <= MESSAGE_SEPTETS - PREFIX_SEPTETS
    assert septets(first_page[1]) <= MESSAGE_SEPTETS - PREFIX_SEPTETS - FOOTER_SEPTETS
    assert len(pages) > 1


def test_text_is_converted_to_gsm7_first() -> None:
    assert plain_pages("it\N{RIGHT SINGLE QUOTATION MARK}s \N{GRINNING FACE} ok", 1) == [
        ["it's  ok"]
    ]


@pytest.mark.parametrize("messages", [0, 10])
def test_a_plain_page_has_one_to_nine_messages(messages: int) -> None:
    with pytest.raises(ValueError, match="1 to 9"):
        plain_pages("x", messages)


def test_pages_are_prefixed_and_point_to_the_next_page() -> None:
    assert format_plain_page(["one", "two"], "a7", 2) == [
        "[a7 1/2] one",
        "[a7 2/2] two\n>> p! a7 2",
    ]
    assert format_plain_page(["only"], "z0", None) == ["[z0 1/1] only"]


@settings(max_examples=60)
@given(st.text(min_size=1, max_size=3000), st.integers(1, 9), st.integers(1, 255))
def test_every_formatted_message_fits_one_sms(text: str, messages: int, page: int) -> None:
    pages = plain_pages(text, messages)
    for index, bodies in enumerate(pages):
        assert 1 <= len(bodies) <= messages
        following = page if index < len(pages) - 1 else None
        for message in format_plain_page(bodies, "zz", following):
            assert is_gsm7(message)
            assert septets(message) <= MESSAGE_SEPTETS
