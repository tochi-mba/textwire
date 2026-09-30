from __future__ import annotations

import pytest

from textwire.protocol.tags import (
    SERVER_TAG_FIRST,
    TAG_COUNT,
    TagError,
    decode_tag,
    encode_tag,
    is_tag,
    next_server_tag,
)


@pytest.mark.parametrize(
    ("number", "text"), [(0, "00"), (9, "09"), (10, "0a"), (367, "a7"), (1259, "yz"), (1295, "zz")]
)
def test_tags_are_two_base36_characters(number: int, text: str) -> None:
    assert encode_tag(number) == text
    assert decode_tag(text) == number


def test_every_tag_round_trips() -> None:
    assert [decode_tag(encode_tag(tag)) for tag in range(TAG_COUNT)] == list(range(TAG_COUNT))


def test_tags_are_read_in_either_case() -> None:
    assert decode_tag("A7") == 367


@pytest.mark.parametrize("text", ["", "a", "abc", "a!", "é1"])
def test_other_text_is_not_a_tag(text: str) -> None:
    assert not is_tag(text)
    with pytest.raises(TagError):
        decode_tag(text)


@pytest.mark.parametrize("number", [-1, TAG_COUNT])
def test_numbers_outside_the_range_have_no_tag(number: int) -> None:
    with pytest.raises(TagError):
        encode_tag(number)


def test_the_server_range_starts_at_z0() -> None:
    assert encode_tag(SERVER_TAG_FIRST) == "z0"


@pytest.mark.parametrize(
    ("previous", "following"),
    [
        (None, "z0"),
        (0, "z0"),
        (SERVER_TAG_FIRST, "z1"),
        (TAG_COUNT - 2, "zz"),
        (TAG_COUNT - 1, "z0"),
    ],
)
def test_server_tags_cycle_through_z0_to_zz(previous: int | None, following: str) -> None:
    assert encode_tag(next_server_tag(previous)) == following
