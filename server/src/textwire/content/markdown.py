"""From an extractor's Markdown to document text (PROTOCOL.md sections 5 and 9.4).

Links become numbered chips, citations and images disappear, headings flatten to ``##``,
list markers normalise, typography becomes ASCII where it has an equivalent, and lines that
repeat like boilerplate go. The result is the small Markdown subset the phone renders.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from urllib.parse import urljoin, urlsplit

from textwire.content.document import MAX_LINKS
from textwire.protocol.gsm7 import simplify_typography

_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff\ufffd"))
_TAGS = re.compile(
    r"</?(?:sup|sub|span|small|b|i|u|em|strong|mark|abbr|cite|kbd|code|br|wbr|font)\b[^>]*>",
    re.IGNORECASE,
)
_IMAGE = re.compile(r"!\[(?:\\.|[^\[\]\\])*\]\([^)]*\)")
_LINK = re.compile(
    r"\[(?P<text>(?:\\.|[^\[\]\\])*)\]"
    r"\(\s*(?P<url><[^>]*>|(?:[^()\s]|\([^()\s]*\))+)(?:\s+\"[^\"]*\")?\s*\)"
)
_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>~<])")
_MARKER = r"\d{1,3}|[a-z]|citation needed|edit|note \d{1,3}"
#: A citation marker left in the text: ``[12]``, ``[a]``, ``[citation needed]``.
_CITATION = re.compile(rf"\[(?:{_MARKER})\]", re.IGNORECASE)
#: The text of a link that is only a citation marker: ``[12]``, ``[a]``, or a bare ``12``.
_CITATION_TEXT = re.compile(rf"\[(?:{_MARKER})\]|\d{{1,3}}", re.IGNORECASE)
#: A citation marker wrapped in a link without escaping: ``[[12]](#cite_note-12)``.
_NESTED_CITATION = re.compile(rf"\[\[(?:{_MARKER})\]\]\([^)]*\)", re.IGNORECASE)
_CHIP_MARK = "\x00"
_PLACEHOLDER = re.compile(r"\x00(\d+)\x00")
_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_BULLET = re.compile(r"^\s*[*+-]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*(\d{1,3})[.)]\s+(.*)$")
_RULE = re.compile(r"^\s*(?:[-*_]\s*){3,}$")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
_SPACES = re.compile(r" {2,}")
_UNSAFE_SCHEMES = ("mailto:", "javascript:", "tel:", "data:", "sms:", "ftp:")
#: A short line seen this often in one page is navigation or boilerplate, not content.
_REPEATS = 3
_SHORT_LINE = 40


class LinkTable:
    """Numbers links in reading order; a repeated URL keeps its first number."""

    def __init__(self, base_url: str, limit: int = MAX_LINKS) -> None:
        self._base = base_url
        self._limit = limit
        self._numbers: dict[str, int] = {}

    @property
    def urls(self) -> tuple[str, ...]:
        """The table, in number order."""
        return tuple(self._numbers)

    def _is_same_page(self, url: str) -> bool:
        """A link back to this page, or to a fragment of the site root (a mangled anchor)."""
        target, base = urlsplit(url), urlsplit(self._base)
        if target.netloc != base.netloc:
            return False
        if (target.path.rstrip("/"), target.query) == (base.path.rstrip("/"), base.query):
            return True
        return bool(target.fragment) and target.path in ("", "/")

    def replace(self, match: re.Match[str]) -> str:
        """The replacement for one Markdown link: chipped text, plain text, or nothing."""
        text = " ".join(_unescape(match["text"]).split())
        raw_url = match["url"].strip("<>")
        if not text or _CITATION_TEXT.fullmatch(text):
            return ""
        if raw_url.lower().startswith(_UNSAFE_SCHEMES) or raw_url.startswith("#"):
            return text
        url = urljoin(self._base, raw_url)
        if self._is_same_page(url) or not url.lower().startswith(("http://", "https://")):
            return text
        number = self._numbers.get(url)
        if number is None:
            if len(self._numbers) >= self._limit:
                return text
            number = self._numbers[url] = len(self._numbers) + 1
        return f"{text}{_CHIP_MARK}{number}{_CHIP_MARK}"


def _unescape(text: str) -> str:
    return _ESCAPE.sub(r"\1", text)


def _clean_line(line: str) -> str:
    line = _SPACES.sub(" ", line)
    stripped = line.strip()
    if heading := _HEADING.match(stripped):
        return f"## {heading[1].strip().rstrip('#').strip()}"
    if bullet := _BULLET.match(line):
        return f"- {bullet[1].strip()}"
    if numbered := _NUMBERED.match(line):
        return f"{numbered[1]}. {numbered[2].strip()}"
    return stripped


def _is_noise(line: str) -> bool:
    return bool(_RULE.match(line) or _TABLE_RULE.match(line) or _FENCE.match(line))


def _drop_boilerplate(lines: list[str]) -> list[str]:
    counts = Counter(line for line in lines if line and not line.startswith("## "))
    return [
        line
        for line in lines
        if not (line and counts[line] >= _REPEATS and len(line) < _SHORT_LINE)
    ]


def _blocks(lines: list[str]) -> str:
    """Join lines into blank-line-separated blocks, headings always standing alone."""
    blocks: list[list[str]] = [[]]
    for line in lines:
        if not line or line.startswith("## "):
            if blocks[-1]:
                blocks.append([])
            if line:
                blocks[-1].append(line)
                blocks.append([])
            continue
        blocks[-1].append(line)
    return "\n\n".join("\n".join(block) for block in blocks if block)


def to_document_text(markdown: str, base_url: str) -> tuple[str, tuple[str, ...]]:
    """Document text and its link table from an extractor's Markdown."""
    text = unicodedata.normalize("NFC", markdown).replace("\r\n", "\n").replace("\r", "\n")
    text = simplify_typography(text.translate(_INVISIBLE))
    text = _TAGS.sub("", text)
    text = _IMAGE.sub("", text)
    text = _NESTED_CITATION.sub("", text)
    table = LinkTable(base_url)
    text = _LINK.sub(table.replace, text)
    text = _unescape(text)
    text = _CITATION.sub("", text)
    text = text.replace("**", "").replace("__", "")
    lines = [_clean_line(line) for line in text.split("\n") if not _is_noise(line)]
    body = _blocks(_drop_boilerplate(lines))
    body = _PLACEHOLDER.sub(r"[\1]", body)
    return body, table.urls


def split_title(body: str) -> tuple[str | None, str]:
    """A leading ``## Heading`` block (the page's own h1) as the title, and the rest."""
    first, _, rest = body.partition("\n\n")
    if first.startswith("## ") and "\n" not in first:
        return first[3:].strip(), rest
    return None, body
