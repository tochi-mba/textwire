"""Reader mode: from a fetched response to a document.

HTML goes through trafilatura (the best-scoring maintained extractor in 2026) as Markdown
with links. When it finds nothing, a small standard-library walker collects headings,
paragraphs and list items instead, so a page that has text never comes back empty. Plain
text passes through. Anything else is refused.
"""

from __future__ import annotations

from enum import StrEnum
from html.parser import HTMLParser
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urlsplit

import trafilatura

from textwire.content.document import Document
from textwire.content.markdown import split_title, to_document_text
from textwire.protocol.envelope import Kind

if TYPE_CHECKING:
    from textwire.content.fetch import Fetched

HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
#: Documents longer than this are cut: nobody reads 60,000 characters over SMS.
MAX_BODY_CHARS = 60_000
TITLE_FALLBACK = "Untitled page"


class ExtractFault(StrEnum):
    """Why a response has no document; the value follows ``E extract``."""

    UNSUPPORTED = "unsupported"
    EMPTY = "empty"


class ExtractError(Exception):
    """A response that holds no readable text."""

    def __init__(self, fault: ExtractFault, detail: str = "") -> None:
        super().__init__(f"{fault.value} {detail}".strip())
        self.fault = fault

    @property
    def status_text(self) -> str:
        """The status line the phone is sent: ``E extract unsupported application/pdf``."""
        return f"E extract {self}"


class _Walker(HTMLParser):
    """The fallback: headings, paragraphs and list items, with their links, as Markdown."""

    _SKIP: ClassVar[frozenset[str]] = frozenset(
        {"script", "style", "noscript", "nav", "header", "footer", "aside", "form"}
    )
    _BLOCKS: ClassVar[dict[str, str]] = {
        "p": "",
        "li": "- ",
        "h1": "## ",
        "h2": "## ",
        "h3": "## ",
        "h4": "## ",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: list[str] = []
        self._skipping = 0
        self._current: list[str] | None = None
        self._prefix = ""
        self._in_title = False
        self._href: str | None = None
        self._anchor: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skipping += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._BLOCKS and not self._skipping:
            self._current, self._prefix = [], self._BLOCKS[tag]
        elif tag == "a" and self._current is not None:
            self._href = dict(attrs).get("href")
            self._anchor = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skipping = max(0, self._skipping - 1)
        elif tag == "title":
            self._in_title = False
        elif tag == "a" and self._current is not None and self._href is not None:
            text = " ".join("".join(self._anchor).split())
            self._current.append(f"[{text}]({self._href})")
            self._href = None
        elif tag in self._BLOCKS and self._current is not None:
            text = " ".join("".join(self._current).split())
            if text:
                self.blocks.append(self._prefix + text)
            self._current = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._skipping or self._current is None:
            return
        elif self._href is not None:
            self._anchor.append(data)
        else:
            self._current.append(data)


def _decode(fetched: Fetched) -> str:
    return fetched.body.decode(fetched.charset or "utf-8", errors="replace")


def _fallback(html: str) -> tuple[str, str]:
    walker = _Walker()
    walker.feed(html)
    walker.close()
    return " ".join(walker.title.split()), "\n\n".join(walker.blocks)


def _host_title(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.") or TITLE_FALLBACK


def _truncate(body: str) -> str:
    if len(body) <= MAX_BODY_CHARS:
        return body
    cut = body.rfind("\n\n", 0, MAX_BODY_CHARS)
    return (
        body[: cut if cut > 0 else MAX_BODY_CHARS].rstrip() + "\n\n(The rest of this page was cut.)"
    )


def _html_document(fetched: Fetched) -> Document:
    html = _decode(fetched)
    markdown = trafilatura.extract(
        html,
        url=fetched.final_url,
        output_format="markdown",
        include_links=True,
        include_images=False,
        include_tables=True,
        include_comments=False,
        favor_recall=True,
    )
    title = ""
    if markdown:
        metadata = trafilatura.extract_metadata(html, default_url=fetched.final_url)
        title = (metadata.title or "") if metadata is not None else ""
    else:
        title, markdown = _fallback(html)
    body, links = to_document_text(markdown, fetched.final_url)
    heading, rest = split_title(body)
    if heading:
        title, body = heading, rest
    if not body.strip():
        raise ExtractError(ExtractFault.EMPTY)
    return Document(
        kind=Kind.PAGE,
        title=" ".join(title.split()) or _host_title(fetched.final_url),
        body=_truncate(body),
        links=links,
        source=fetched.final_url,
    )


def _text_document(fetched: Fetched) -> Document:
    paragraphs = _decode(fetched).replace("\r\n", "\n").split("\n\n")
    text = "\n\n".join(" ".join(paragraph.split()) for paragraph in paragraphs)
    body, links = to_document_text(text, fetched.final_url)
    if not body.strip():
        raise ExtractError(ExtractFault.EMPTY)
    path = urlsplit(fetched.final_url).path.rstrip("/")
    title = path.rsplit("/", 1)[-1] or _host_title(fetched.final_url)
    return Document(
        kind=Kind.PAGE, title=title, body=_truncate(body), links=links, source=fetched.final_url
    )


def _sniff(fetched: Fetched) -> str:
    if fetched.media_type:
        return fetched.media_type
    head = fetched.body[:1024].lstrip().lower()
    return "text/html" if head.startswith((b"<!doctype html", b"<html")) else "text/plain"


def extract_document(fetched: Fetched) -> Document:
    """The document in ``fetched``, or :class:`ExtractError`."""
    media_type = _sniff(fetched)
    if media_type in HTML_TYPES:
        return _html_document(fetched)
    if media_type == "text/plain":
        return _text_document(fetched)
    raise ExtractError(ExtractFault.UNSUPPORTED, media_type)
