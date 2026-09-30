from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from textwire.protocol.alphabets import (
    Z85G_MARKER,
    Alphabet,
    AlphabetError,
    decode_text,
    encode_bytes,
)
from textwire.protocol.gsm7 import BASIC, septets


def test_base64url_carries_120_bytes_in_160_characters() -> None:
    assert len(encode_bytes(bytes(120), Alphabet.BASE64URL)) == 160
    assert Alphabet.BASE64URL.frame_bytes == 120
    assert Alphabet.BASE64URL.marker == ""


def test_z85g_carries_127_bytes_in_160_characters() -> None:
    assert len(encode_bytes(bytes(127), Alphabet.Z85G)) == 160
    assert len(encode_bytes(bytes(128), Alphabet.Z85G)) == 161
    assert Alphabet.Z85G.frame_bytes == 127
    assert Alphabet.Z85G.marker == Z85G_MARKER


def test_z85g_matches_the_z85_reference_vector() -> None:
    # RFC 32's example, before the five swapped symbols come into play.
    hello = bytes([0x86, 0x4F, 0xD2, 0x6F, 0xB5, 0x59, 0xF7, 0x5B])
    assert encode_bytes(hello, Alphabet.Z85G) == ".HelloWorld"


def test_every_z85g_character_is_one_gsm7_septet_and_ascii() -> None:
    text = encode_bytes(bytes(range(256)) * 2, Alphabet.Z85G)
    assert septets(text) == len(text)
    assert all(0x21 <= ord(char) < 0x7F and char in BASIC for char in text)


@given(st.binary(max_size=200), st.sampled_from(list(Alphabet)))
def test_every_byte_string_survives_a_round_trip(data: bytes, alphabet: Alphabet) -> None:
    text = encode_bytes(data, alphabet)
    assert decode_text(text) == (data, alphabet)


@pytest.mark.parametrize(
    "text",
    [
        "AAAAA",  # a base64url remainder of one
        "AB",  # non-canonical base64url
        "AAAA=",  # padding
        "AAA*",  # outside base64url
        ".AAAAAA",  # a z85g remainder of one
        ".~",  # outside z85g
        ".#####",  # a block above 2**32 - 1
        ".#1",  # a non-canonical tail
        "." + "0" * 3 + "#",  # a non-canonical tail of two bytes
    ],
)
def test_non_canonical_or_foreign_text_is_rejected(text: str) -> None:
    with pytest.raises(AlphabetError):
        decode_text(text)


def test_z85g_tails_are_canonical() -> None:
    for length in range(1, 9):
        data = bytes(range(200, 200 + length))
        text = encode_bytes(data, Alphabet.Z85G)
        assert decode_text(text) == (data, Alphabet.Z85G)
        assert len(text) == 1 + (length // 4) * 5 + (length % 4 + 1 if length % 4 else 0)
