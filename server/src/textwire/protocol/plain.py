"""Plain replies: readable SMS for any messaging app (PROTOCOL.md section 7).

A document is converted to GSM-7 and cut into message bodies, a page at a time. Each message
gets a ``[tag i/n]`` prefix; the last message of a page that has a successor gets a footer
saying what to send for the next page. Every message fits one 160-septet SMS.
"""

from __future__ import annotations

from textwire.protocol.gsm7 import sanitize, septets

MESSAGE_SEPTETS = 160
#: ``[a7 1/4] ``: nine characters, but the brackets are GSM-7 extension characters that cost
#: two septets each, so eleven septets. A message count is at most 9, so it never grows.
PREFIX_SEPTETS = 11
#: ``\n>> p! a7 255``: the longest footer.
FOOTER_SEPTETS = 13
MAX_MESSAGES = 9
_BREAKS = ("\n\n", "\n", " ")


def _fit(text: str, capacity: int) -> int:
    """How many leading characters of ``text`` fit in ``capacity`` septets."""
    used = 0
    for index, char in enumerate(text):
        used += septets(char)
        if used > capacity:
            return index
    return len(text)


def _take(text: str, capacity: int) -> tuple[str, str]:
    """One message body from the front of ``text``, broken at the best whitespace."""
    fits = _fit(text, capacity)
    if fits == len(text):
        return text, ""
    window = text[: fits + 1]  # a break right after the last fitting character is fine too
    for mark in _BREAKS:
        cut = window.rfind(mark)
        if cut >= fits // 2:
            return text[:cut].rstrip(), text[cut:].lstrip()
    return text[:fits], text[fits:].lstrip()


def plain_pages(text: str, max_messages: int) -> list[list[str]]:
    """The message bodies of every plain page of ``text``, before prefixes and footers."""
    if not 1 <= max_messages <= MAX_MESSAGES:
        msg = f"a plain page has 1 to {MAX_MESSAGES} messages, not {max_messages}"
        raise ValueError(msg)
    capacity = MESSAGE_SEPTETS - PREFIX_SEPTETS
    rest = sanitize(text).strip()
    pages: list[list[str]] = []
    while rest:
        page: list[str] = []
        while rest and len(page) < max_messages:
            last_slot = len(page) == max_messages - 1
            body, rest = _take(rest, capacity - FOOTER_SEPTETS if last_slot else capacity)
            page.append(body)
        pages.append(page)
    return pages or [[""]]


def format_plain_page(bodies: list[str], tag: str, next_page: int | None) -> list[str]:
    """The SMS texts of one plain page: prefixed, with a footer when a next page exists."""
    count = len(bodies)
    messages = [f"[{tag} {index}/{count}] {body}".rstrip() for index, body in enumerate(bodies, 1)]
    if next_page is not None:
        messages[-1] += f"\n>> p! {tag} {next_page}"
    return messages
