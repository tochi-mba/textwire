from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from textwire.protocol.gsm7 import (
    ALPHABET,
    BASIC_TABLE,
    EXTENSION,
    is_gsm7,
    sanitize,
    septets,
    simplify_typography,
)


def test_the_basic_table_has_128_codes_in_order() -> None:
    assert len(BASIC_TABLE) == 128
    assert BASIC_TABLE[0x00] == "@"
    assert BASIC_TABLE[0x02] == "$"
    assert BASIC_TABLE[0x10] == "\N{GREEK CAPITAL LETTER DELTA}"
    assert BASIC_TABLE[0x1B] == "\x1b"
    assert BASIC_TABLE[0x24] == "\N{CURRENCY SIGN}"
    assert BASIC_TABLE[0x40] == "\N{INVERTED EXCLAMATION MARK}"
    assert BASIC_TABLE[0x7F] == "\N{LATIN SMALL LETTER A WITH GRAVE}"


def test_every_base64url_character_is_one_septet() -> None:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    assert septets(alphabet) == len(alphabet)


def test_extension_characters_cost_two_septets() -> None:
    assert septets("a{b}") == 6
    assert septets("\N{EURO SIGN}") == 2


def test_characters_outside_the_alphabet_have_no_septet_count() -> None:
    with pytest.raises(ValueError, match="not in the GSM-7 alphabet"):
        septets("\N{GRINNING FACE}")


def test_membership() -> None:
    assert is_gsm7("Caf\N{LATIN SMALL LETTER E WITH ACUTE} [1] 100\N{EURO SIGN}")
    assert not is_gsm7("\N{LATIN SMALL LETTER E WITH CIRCUMFLEX}")
    assert "\x1b" not in ALPHABET
    assert EXTENSION <= ALPHABET


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("\N{LEFT DOUBLE QUOTATION MARK}hi\N{RIGHT DOUBLE QUOTATION MARK}", '"hi"'),
        ("it\N{RIGHT SINGLE QUOTATION MARK}s", "it's"),
        ("a\N{EM DASH}b\N{EN DASH}c", "a-b-c"),
        ("wait\N{HORIZONTAL ELLIPSIS}", "wait..."),
        ("a\N{NO-BREAK SPACE}b", "a b"),
        (
            "\N{LATIN SMALL LETTER E WITH CIRCUMFLEX}t\N{LATIN SMALL LETTER E WITH CIRCUMFLEX}",
            "ete",
        ),
        ("gar\N{LATIN SMALL LETTER C WITH CEDILLA}on", "garcon"),
        ("\N{LATIN CAPITAL LETTER C WITH CEDILLA}a", "\N{LATIN CAPITAL LETTER C WITH CEDILLA}a"),
        ("caf\N{LATIN SMALL LETTER E WITH ACUTE}", "caf\N{LATIN SMALL LETTER E WITH ACUTE}"),
        ("ok \N{THUMBS UP SIGN}", "ok "),
        ("x\N{ZERO WIDTH SPACE}y", "xy"),
        ("\N{CJK UNIFIED IDEOGRAPH-4E2D}", "?"),
        ("tab\there\r\n", "tab here\n"),
        ("2\N{MULTIPLICATION SIGN}3", "2x3"),
    ],
)
def test_sanitize_maps_typography_and_drops_what_has_no_equivalent(
    text: str, expected: str
) -> None:
    assert sanitize(text) == expected


@given(st.text())
def test_sanitized_text_is_always_gsm7(text: str) -> None:
    assert is_gsm7(sanitize(text))


def test_typography_is_simplified_without_touching_accents() -> None:
    text = (
        "\N{LEFT SINGLE QUOTATION MARK}caf\N{LATIN SMALL LETTER E WITH CIRCUMFLEX}"
        "\N{RIGHT SINGLE QUOTATION MARK}\N{NARROW NO-BREAK SPACE}\N{EM DASH}"
    )
    assert simplify_typography(text) == "'caf\N{LATIN SMALL LETTER E WITH CIRCUMFLEX}' -"
