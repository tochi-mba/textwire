"""Documents the server writes itself: search results and help."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from textwire.content.document import Document
from textwire.protocol.envelope import Kind
from textwire.protocol.gsm7 import simplify_typography

if TYPE_CHECKING:
    from collections.abc import Sequence

    from textwire.content.search import Hit

SNIPPET_CHARS = 160
_BRACKETS = str.maketrans("[]", "()")
_JUNK = dict.fromkeys(map(ord, "\N{REPLACEMENT CHARACTER}\N{ZERO WIDTH SPACE}\N{BYTE ORDER MARK}"))
_SPACE = re.compile(r"\s+")

HELP_BODY = """g <address> - open a page
s <words> - search the web
p <tag> <n> - page n of a reply
l <tag> <n> - follow link n
? - usage and cost today

The app does this for you. From any messaging app, add ! for readable replies: s! weather london

Add a number to choose the page size in SMS: g8 bbc.co.uk"""


def _clean(text: str) -> str:
    """One line, plain typography, and no square brackets that could pose as link chips."""
    text = simplify_typography(text.translate(_JUNK)).translate(_BRACKETS)
    return _SPACE.sub(" ", text).strip()


def _snippet(text: str, limit: int) -> str:
    """At most ``limit`` characters of ``text``, cut at a word; nothing when ``limit`` is 0."""
    if limit == 0:
        return ""
    text = _clean(text)
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit - 3)
    return text[: cut if cut > 0 else limit - 3].rstrip(" ,.;:") + "..."


def _domain(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


def search_document(
    query: str, hits: Sequence[Hit], *, snippet_chars: int = SNIPPET_CHARS
) -> Document:
    """A SEARCH document: a numbered list whose items link to the results."""
    blocks = []
    for number, hit in enumerate(hits, 1):
        title = _clean(hit.title) or _domain(hit.url)
        item = f"{number}. {title}[{number}] ({_domain(hit.url)})"
        snippet = _snippet(hit.snippet, snippet_chars)
        blocks.append(f"{item}\n{snippet}" if snippet else item)
    return Document(
        kind=Kind.SEARCH,
        title=f"Search: {_clean(query)}",
        body="\n\n".join(blocks) if blocks else "No results.",
        links=tuple(hit.url for hit in hits),
        source=query,
    )


def help_document() -> Document:
    """The HELP document."""
    return Document(kind=Kind.HELP, title="textwire help", body=HELP_BODY)
