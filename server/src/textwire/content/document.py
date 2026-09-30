"""The document: what every request that produces pages turns into."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textwire.protocol.envelope import Kind

#: Links a document keeps; later ones become plain text (PROTOCOL.md section 9.4).
MAX_LINKS = 60


@dataclass(frozen=True, slots=True)
class Document:
    """A title, a body in the document-text subset of Markdown, and its link table.

    ``body`` never contains the title line; pagination adds it to every page. Link chip
    ``[n]`` in the body refers to ``links[n - 1]``.
    """

    kind: Kind
    title: str
    body: str
    links: tuple[str, ...] = ()
    source: str = ""

    def __post_init__(self) -> None:
        if len(self.links) > MAX_LINKS:
            msg = f"a document keeps at most {MAX_LINKS} links, not {len(self.links)}"
            raise ValueError(msg)
