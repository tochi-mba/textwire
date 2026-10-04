"""Pagination: cutting a document into pages that each fit a number of SMS (PROTOCOL.md 9.3).

A page's envelope and text, compressed or not, must fit in ``size x 114`` bytes. Blocks go
onto a page whole; a block too big for any page is split at line breaks, then sentence ends,
then spaces, then anywhere. Every page starts with the title line. The result depends only on
the document, the dictionary and the size, so page 3 is the same page every time it is asked
for.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

from textwire.protocol.alphabets import Alphabet
from textwire.protocol.envelope import (
    ENVELOPE_BYTES,
    MAX_PAGES,
    Envelope,
    pack_envelope,
)
from textwire.protocol.frames import body_bytes
from textwire.protocol.plain import plain_pages

if TYPE_CHECKING:
    from textwire.content.document import Document
    from textwire.protocol.compress import Dictionary

TITLE_CHARS = 60
_SPLITTERS = (
    (re.compile(r"\n"), "\n"),
    (re.compile(r"(?<=[.!?])\s+"), " "),
    (re.compile(r" +"), " "),
)


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def capacity(size: int, alphabet: Alphabet = Alphabet.BASE64URL) -> int:
    """Bytes of text (after the envelope) that fit in ``size`` frames of ``alphabet``."""
    return size * body_bytes(alphabet) - ENVELOPE_BYTES


def _cut(text: str, limit: int) -> str:
    """``text`` cut to at most ``limit`` UTF-8 bytes, with ``...`` when anything was cut."""
    if _size(text) <= limit:
        return text
    kept = text.encode("utf-8")[: max(0, limit - 3)].decode("utf-8", errors="ignore")
    return kept.rstrip() + "..."


def title_line(title: str, max_bytes: int) -> str:
    """``# Title``: one line, at most 60 characters and ``max_bytes`` bytes."""
    text = " ".join(title.split())
    if len(text) > TITLE_CHARS:
        text = text[: TITLE_CHARS - 3].rstrip() + "..."
    return "# " + _cut(text, max_bytes - 2)


def _hard_split(text: str, limit: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for char in text:
        if current and _size(current + char) > limit:
            chunks.append(current)
            current = ""
        current += char
    chunks.append(current)
    return chunks


def _merge(parts: list[str], joiner: str, limit: int, level: int) -> list[str]:
    """Rejoin ``parts`` greedily into chunks of at most ``limit`` bytes."""
    chunks: list[str] = []
    current = ""
    for part in parts:
        for piece in _split_block(part, limit, level):
            candidate = f"{current}{joiner}{piece}" if current else piece
            if _size(candidate) <= limit:
                current = candidate
            else:
                chunks.append(current)
                current = piece
    chunks.append(current)
    return chunks


def _split_block(block: str, limit: int, level: int = 0) -> list[str]:
    """Pieces of ``block``, each at most ``limit`` bytes, split as gently as possible.

    ``level`` is the first splitter still allowed: a sentence that is too long is split at
    spaces, never back at line breaks.
    """
    if _size(block) <= limit:
        return [block]
    for index in range(level, len(_SPLITTERS)):
        pattern, joiner = _SPLITTERS[index]
        parts = [part for part in pattern.split(block) if part]
        if len(parts) > 1:
            return _merge(parts, joiner, limit, index + 1)
    return _hard_split(block, limit)


def _paginate(
    document: Document, dictionary: Dictionary, size: int, alphabet: Alphabet
) -> tuple[str, ...]:
    room = capacity(size, alphabet)
    head = title_line(document.title, room // 2)
    limit = room - _size(head) - 2
    pieces = [
        piece
        for block in document.body.split("\n\n")
        if block.strip()
        for piece in _split_block(block, limit)
    ]

    def text(start: int, end: int) -> str:
        return head + "".join("\n\n" + piece for piece in pieces[start:end])

    def fits(start: int, end: int) -> bool:
        envelope = Envelope(kind=document.kind, page=1, pages=1, text=text(start, end))
        return len(pack_envelope(envelope, dictionary)) - ENVELOPE_BYTES <= room

    pages: list[str] = []
    start = 0
    while start < len(pieces) and len(pages) < MAX_PAGES:
        # Invariant: [start, good) fits, [start, bad) does not. One piece always fits.
        good, bad = start + 1, len(pieces) + 1
        if fits(start, len(pieces)):
            good = len(pieces)
        else:
            bad = len(pieces)
            while bad - good > 1:
                middle = (good + bad) // 2
                if fits(start, middle):
                    good = middle
                else:
                    bad = middle
        pages.append(text(start, good))
        start = good
    return tuple(pages) or (head,)


#: Pagination is pure, and ``p`` asks for the same document's pages again and again.
_cached = lru_cache(maxsize=128)(_paginate)


def clear_page_cache() -> None:
    """Forget every remembered pagination, so a benchmark times the work and not the cache."""
    _cached.cache_clear()


def paginate(
    document: Document,
    dictionary: Dictionary,
    size: int,
    alphabet: Alphabet = Alphabet.BASE64URL,
) -> tuple[str, ...]:
    """Every page's text for ``document`` at ``size`` frames of ``alphabet`` a page."""
    return _cached(document, dictionary, size, alphabet)


def page_payload(
    document: Document,
    dictionary: Dictionary,
    size: int,
    number: int,
    alphabet: Alphabet = Alphabet.BASE64URL,
) -> bytes:
    """The payload of page ``number`` (from 1) of ``document`` at ``size`` frames a page."""
    pages = paginate(document, dictionary, size, alphabet)
    if not 1 <= number <= len(pages):
        msg = f"page {number} of {len(pages)} does not exist"
        raise IndexError(msg)
    envelope = Envelope(kind=document.kind, page=number, pages=len(pages), text=pages[number - 1])
    return pack_envelope(envelope, dictionary)


def page_count(
    document: Document,
    dictionary: Dictionary,
    size: int,
    alphabet: Alphabet = Alphabet.BASE64URL,
) -> int:
    """How many pages ``document`` has at ``size`` frames a page."""
    return len(paginate(document, dictionary, size, alphabet))


def plain_document_pages(document: Document, messages: int) -> list[list[str]]:
    """The plain-reply pages of ``document``: message bodies, before prefixes and footers."""
    head = title_line(document.title, 160)
    text = f"{head}\n\n{document.body}" if document.body else head
    return plain_pages(text, messages)
