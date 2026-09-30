"""Tags: two base-36 characters that name one response (PROTOCOL.md section 3)."""

from __future__ import annotations

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
TAG_COUNT = len(ALPHABET) ** 2
#: The first tag the server hands out, ``z0``; phones allocate everything below it.
SERVER_TAG_FIRST = 35 * len(ALPHABET)


class TagError(ValueError):
    """Text that is not a tag."""


def encode_tag(tag: int) -> str:
    """``367`` becomes ``"a7"``."""
    if not 0 <= tag < TAG_COUNT:
        msg = f"tag {tag} is outside 0-{TAG_COUNT - 1}"
        raise TagError(msg)
    high, low = divmod(tag, len(ALPHABET))
    return ALPHABET[high] + ALPHABET[low]


def decode_tag(text: str) -> int:
    """``"a7"`` (either case) becomes ``367``."""
    lowered = text.lower()
    if len(lowered) != 2 or any(char not in ALPHABET for char in lowered):  # noqa: PLR2004
        msg = f"{text!r} is not a tag"
        raise TagError(msg)
    return ALPHABET.index(lowered[0]) * len(ALPHABET) + ALPHABET.index(lowered[1])


def is_tag(text: str) -> bool:
    """Whether ``text`` is two characters from ``0-9a-z``, in either case."""
    try:
        decode_tag(text)
    except TagError:
        return False
    return True


def next_server_tag(previous: int | None) -> int:
    """The tag after ``previous`` in the server's range ``z0``-``zz``, wrapping around."""
    if previous is None or not SERVER_TAG_FIRST <= previous < TAG_COUNT - 1:
        return SERVER_TAG_FIRST
    return previous + 1
