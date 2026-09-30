"""Frame text alphabets: how frame bytes become SMS characters (PROTOCOL.md section 2.1).

Two alphabets are defined. ``BASE64URL`` is the safe default: six bits per character, plain
letters, digits, ``-`` and ``_``, 120 bytes in a 160-character SMS. ``Z85G`` packs four bytes
into five characters drawn from all 85 printable ASCII characters that the GSM-7 basic table
holds, for 127 bytes in a 160-character SMS. It is marked by a leading full stop, which a
base64url frame can never start with, so a receiver can always tell the two apart.

``Z85G`` follows ZeroMQ's Z85 (RFC 32) with five characters swapped for ones GSM-7 carries
in one septet, and with a tail rule so any length can be encoded: ``n`` leftover bytes become
``n + 1`` characters, padded with zero bytes on the way in and with the highest symbol on the
way out. Both directions are canonical: text that does not re-encode to itself is rejected.
"""

from __future__ import annotations

import base64
import re
from enum import StrEnum

FRAME_CHARS = 160

_B64_PATTERN = re.compile(r"[A-Za-z0-9_-]*")
_Z85G_ALPHABET = (
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=\"!/*?&<>()',;@%$#_"
)
_Z85G_VALUE = {char: index for index, char in enumerate(_Z85G_ALPHABET)}
_Z85G_PATTERN = re.compile("[" + re.escape(_Z85G_ALPHABET) + "]*")
Z85G_MARKER = "."
_BASE = 85
_BLOCK_MAX = 0xFFFFFFFF


class Alphabet(StrEnum):
    """How frame bytes are written as SMS text."""

    BASE64URL = "b64"
    Z85G = "z85g"

    @property
    def frame_bytes(self) -> int:
        """The most bytes a 160-character SMS carries in this alphabet."""
        return 120 if self is Alphabet.BASE64URL else 127

    @property
    def marker(self) -> str:
        """The character every frame in this alphabet starts with; empty for base64url."""
        return "" if self is Alphabet.BASE64URL else Z85G_MARKER


class AlphabetError(ValueError):
    """Text that is not a canonical encoding in any alphabet."""


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64_decode(text: str) -> bytes:
    if not _B64_PATTERN.fullmatch(text) or len(text) % 4 == 1:
        raise AlphabetError
    data = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    if _b64_encode(data) != text:
        raise AlphabetError
    return data


def _z85g_encode(data: bytes) -> str:
    out: list[str] = []
    for start in range(0, len(data), 4):
        block = data[start : start + 4]
        value = int.from_bytes(block.ljust(4, b"\0"), "big")
        digits = ["", "", "", "", ""]
        for position in range(4, -1, -1):
            value, digit = divmod(value, _BASE)
            digits[position] = _Z85G_ALPHABET[digit]
        out.extend(digits[: len(block) + 1])
    return "".join(out)


def _z85g_decode(text: str) -> bytes:
    if not _Z85G_PATTERN.fullmatch(text) or len(text) % 5 == 1:
        raise AlphabetError
    out = bytearray()
    for start in range(0, len(text), 5):
        chunk = text[start : start + 5]
        padded = chunk + _Z85G_ALPHABET[-1] * (5 - len(chunk))
        value = 0
        for char in padded:
            value = value * _BASE + _Z85G_VALUE[char]
        if value > _BLOCK_MAX:
            raise AlphabetError
        out += value.to_bytes(4, "big")[: len(chunk) - 1]
    if _z85g_encode(bytes(out)) != text:
        raise AlphabetError
    return bytes(out)


def encode_bytes(data: bytes, alphabet: Alphabet) -> str:
    """The SMS text for ``data`` in ``alphabet``, marker included."""
    if alphabet is Alphabet.BASE64URL:
        return _b64_encode(data)
    return Z85G_MARKER + _z85g_encode(data)


def decode_text(text: str) -> tuple[bytes, Alphabet]:
    """The bytes in an SMS text and the alphabet it was written in."""
    if text.startswith(Z85G_MARKER):
        return _z85g_decode(text[1:]), Alphabet.Z85G
    return _b64_decode(text), Alphabet.BASE64URL
