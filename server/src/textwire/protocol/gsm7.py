"""The GSM 03.38 default alphabet, and turning any text into it for plain replies.

A single character outside this alphabet switches a whole SMS to UCS-2 and cuts it from 160
characters to 70, so plain replies are converted before they are split (PROTOCOL.md
section 7). Frames never need this: base64url is plain ASCII inside the basic table.
"""

from __future__ import annotations

import unicodedata

#: The 128-entry basic table, in code order; index 0x1B is the escape to the extension table.
BASIC_TABLE = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ"
    " !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
#: Characters reached through the escape; each costs two septets.
EXTENSION = frozenset("\f^{}\\[~]|€")
BASIC = frozenset(BASIC_TABLE) - {"\x1b"}
ALPHABET = BASIC | EXTENSION

#: Common typography that has a close GSM-7 equivalent.
_REPLACEMENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2033": '"',
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2212": "-",
    "\u2026": "...",
    "\u2022": "-",
    "\u00b7": "-",
    "\u00d7": "x",
    "\u00f7": "/",
    "\u2122": "TM",
    "\u00a9": "(c)",
    "\u00ae": "(R)",
    "\t": " ",
    "\r": "",
}
_SPACES = frozenset(
    "\u00a0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
)


def simplify_typography(text: str) -> str:
    """``text`` with typographic characters that have a plain equivalent replaced.

    Used on every document, encoded or plain: a curly quote costs three UTF-8 bytes and a
    straight one costs one, and the reader loses nothing.
    """
    return "".join(_REPLACEMENTS.get(char, " " if char in _SPACES else char) for char in text)


def is_gsm7(text: str) -> bool:
    """Whether every character of ``text`` is in the default alphabet or its extension."""
    return all(char in ALPHABET for char in text)


def septets(text: str) -> int:
    """How many septets ``text`` takes in a GSM-7 SMS."""
    total = 0
    for char in text:
        if char in EXTENSION:
            total += 2
        elif char in BASIC:
            total += 1
        else:
            msg = f"{char!r} is not in the GSM-7 alphabet"
            raise ValueError(msg)
    return total


def _convert(char: str) -> str:
    if char in _REPLACEMENTS:  # first: a carriage return is GSM-7, but never wanted
        return _REPLACEMENTS[char]
    if char in ALPHABET:
        return char
    if char in _SPACES:
        return " "
    base = "".join(part for part in unicodedata.normalize("NFD", char) if part in ALPHABET)
    if base:
        return base
    category = unicodedata.category(char)
    if category[0] in "SMC":  # symbols (emoji included), combining marks, controls, format
        return ""
    return "?"


def sanitize(text: str) -> str:
    """``text`` in the GSM-7 alphabet: typography mapped, accents dropped, symbols removed."""
    return "".join(_convert(char) for char in unicodedata.normalize("NFC", text))
