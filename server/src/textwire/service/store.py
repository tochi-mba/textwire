"""SQLite storage: what has been handled, what was sent, and what can still be paged or resent.

One file (``TEXTWIRE_DATA_DIR/textwire.db``), one connection, used from the event loop's
thread. Every row carries a UTC timestamp, and :meth:`Store.purge` drops what is older than
the retention period.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from textwire.content.document import Document
from textwire.protocol.envelope import Kind

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from textwire.transport.base import DeliveryStatus, InboundMessage, SentMessage

SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS inbound (
    id TEXT PRIMARY KEY,
    number TEXT NOT NULL,
    body TEXT NOT NULL,
    received_at TEXT NOT NULL,
    handled_at TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT NOT NULL,
    kind INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    links TEXT NOT NULL,
    source TEXT NOT NULL,
    page_size INTEGER NOT NULL,
    plain INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS responses (
    number TEXT NOT NULL,
    tag INTEGER NOT NULL,
    document_id INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (number, tag)
);
CREATE TABLE IF NOT EXISTS frames (
    number TEXT NOT NULL,
    tag INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (number, tag, seq)
);
CREATE TABLE IF NOT EXISTS outbound (
    id TEXT PRIMARY KEY,
    number TEXT NOT NULL,
    tag INTEGER,
    seq INTEGER,
    body TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    status TEXT NOT NULL,
    price REAL,
    price_unit TEXT,
    retried INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS budget_days (
    day TEXT PRIMARY KEY,
    segments INTEGER NOT NULL,
    estimated_cost REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


@dataclass(frozen=True, slots=True)
class StoredDocument:
    """A document as stored, with the page size and mode it was first sent in."""

    id: int
    document: Document
    page_size: int
    plain: bool


@dataclass(frozen=True, slots=True)
class OutboundRow:
    """A sent message whose delivery is still being followed."""

    id: str
    number: str
    tag: int | None
    seq: int | None
    body: str
    status: str
    retried: bool


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


class Store:
    """The server's database."""

    def __init__(self, path: Path | str) -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        if str(path) != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)
        if self._db.execute("SELECT count(*) FROM schema_version").fetchone()[0] == 0:
            self._db.execute("INSERT INTO schema_version VALUES (?)", (SCHEMA_VERSION,))

    def close(self) -> None:
        """Close the database."""
        self._db.close()

    @property
    def schema_version(self) -> int:
        """The schema version the database is at."""
        return int(self._db.execute("SELECT version FROM schema_version").fetchone()[0])

    def ping(self) -> bool:
        """Whether the database answers a trivial query."""
        return bool(self._db.execute("SELECT 1").fetchone()[0])

    # Inbound ------------------------------------------------------------------------------

    def seen_inbound(self, message_id: str) -> bool:
        """Whether a message with this provider id was already recorded."""
        row = self._db.execute("SELECT 1 FROM inbound WHERE id = ?", (message_id,)).fetchone()
        return row is not None

    def record_inbound(self, message: InboundMessage) -> None:
        """Remember an inbound message so it is never handled twice."""
        self._db.execute(
            "INSERT OR IGNORE INTO inbound (id, number, body, received_at) VALUES (?, ?, ?, ?)",
            (message.id, message.sender, message.text, _stamp(message.received_at)),
        )

    def mark_handled(self, message_id: str, at: datetime) -> None:
        """Record that the replies to a message were sent."""
        self._db.execute("UPDATE inbound SET handled_at = ? WHERE id = ?", (_stamp(at), message_id))

    def unhandled(self) -> list[str]:
        """Ids of recorded messages whose replies were never all sent."""
        rows = self._db.execute("SELECT id FROM inbound WHERE handled_at IS NULL ORDER BY id")
        return [row["id"] for row in rows]

    # Documents and responses --------------------------------------------------------------

    def save_document(
        self, number: str, document: Document, *, page_size: int, plain: bool, at: datetime
    ) -> int:
        """Store a document; return its id."""
        cursor = self._db.execute(
            "INSERT INTO documents (number, kind, title, body, links, source, page_size, plain,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                number,
                int(document.kind),
                document.title,
                document.body,
                json.dumps(list(document.links)),
                document.source,
                page_size,
                int(plain),
                _stamp(at),
            ),
        )
        return int(cursor.lastrowid or 0)

    def link_response(self, number: str, tag: int, document_id: int | None, at: datetime) -> None:
        """Record a response under its tag, superseding whatever that tag meant before."""
        self._db.execute("DELETE FROM frames WHERE number = ? AND tag = ?", (number, tag))
        self._db.execute(
            "INSERT OR REPLACE INTO responses (number, tag, document_id, created_at)"
            " VALUES (?, ?, ?, ?)",
            (number, tag, document_id, _stamp(at)),
        )

    def document_for(self, number: str, tag: int) -> StoredDocument | None:
        """The document a response belongs to, if it had one and it is still kept."""
        row = self._db.execute(
            "SELECT d.* FROM responses r JOIN documents d ON d.id = r.document_id"
            " WHERE r.number = ? AND r.tag = ?",
            (number, tag),
        ).fetchone()
        if row is None:
            return None
        document = Document(
            kind=Kind(row["kind"]),
            title=row["title"],
            body=row["body"],
            links=tuple(json.loads(row["links"])),
            source=row["source"],
        )
        return StoredDocument(row["id"], document, row["page_size"], bool(row["plain"]))

    # Frames ---------------------------------------------------------------------------------

    def save_frames(self, number: str, tag: int, frames: dict[int, str], at: datetime) -> None:
        """Keep a response's frame texts for resends."""
        self._db.executemany(
            "INSERT OR REPLACE INTO frames (number, tag, seq, body, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            [(number, tag, seq, body, _stamp(at)) for seq, body in frames.items()],
        )

    def load_frames(self, number: str, tag: int, seqs: Iterable[int]) -> dict[int, str]:
        """The stored texts of the requested frames that are still kept."""
        wanted = set(seqs)
        rows = self._db.execute(
            "SELECT seq, body FROM frames WHERE number = ? AND tag = ? ORDER BY seq",
            (number, tag),
        )
        return {row["seq"]: row["body"] for row in rows if row["seq"] in wanted}

    # Outbound -------------------------------------------------------------------------------

    def record_outbound(
        self, sent: SentMessage, *, tag: int | None, seq: int | None, at: datetime
    ) -> None:
        """Remember a sent message so its delivery and price can be followed."""
        self._db.execute(
            "INSERT OR REPLACE INTO outbound (id, number, tag, seq, body, sent_at, status)"
            " VALUES (?, ?, ?, ?, ?, ?, 'queued')",
            (sent.id, sent.recipient, tag, seq, sent.text, _stamp(at)),
        )

    def pending_outbound(self, since: datetime) -> list[OutboundRow]:
        """Messages sent since ``since`` whose status can still change."""
        rows = self._db.execute(
            "SELECT id, number, tag, seq, body, status, retried FROM outbound"
            " WHERE sent_at >= ? AND status NOT IN"
            " ('delivered', 'undelivered', 'failed', 'received', 'canceled', 'read')"
            " ORDER BY sent_at, id",
            (_stamp(since),),
        )
        return [
            OutboundRow(
                row["id"],
                row["number"],
                row["tag"],
                row["seq"],
                row["body"],
                row["status"],
                bool(row["retried"]),
            )
            for row in rows
        ]

    def update_outbound(self, status: DeliveryStatus) -> None:
        """Record a message's latest status and, once known, its price."""
        self._db.execute(
            "UPDATE outbound SET status = ?, price = coalesce(?, price),"
            " price_unit = coalesce(?, price_unit) WHERE id = ?",
            (status.status, status.price, status.price_unit, status.id),
        )

    def mark_retried(self, message_id: str) -> None:
        """Record that a failed message was sent again, so it is never retried twice."""
        self._db.execute("UPDATE outbound SET retried = 1 WHERE id = ?", (message_id,))

    def actual_cost(self, day: date) -> tuple[float, str | None]:
        """What the provider charged for messages sent on ``day``, as far as it has said."""
        row = self._db.execute(
            "SELECT coalesce(sum(price), 0) AS total, max(price_unit) AS unit FROM outbound"
            " WHERE substr(sent_at, 1, 10) = ?",
            (day.isoformat(),),
        ).fetchone()
        return float(row["total"]), row["unit"]

    # Budget ---------------------------------------------------------------------------------

    def add_segments(self, day: date, segments: int, estimated_cost: float) -> None:
        """Charge segments to a day."""
        self._db.execute(
            "INSERT INTO budget_days (day, segments, estimated_cost) VALUES (?, ?, ?)"
            " ON CONFLICT(day) DO UPDATE SET segments = segments + excluded.segments,"
            " estimated_cost = estimated_cost + excluded.estimated_cost",
            (day.isoformat(), segments, estimated_cost),
        )

    def segments_on(self, day: date) -> tuple[int, float]:
        """Segments charged to ``day`` and their estimated cost."""
        row = self._db.execute(
            "SELECT segments, estimated_cost FROM budget_days WHERE day = ?", (day.isoformat(),)
        ).fetchone()
        return (0, 0.0) if row is None else (int(row["segments"]), float(row["estimated_cost"]))

    # State ----------------------------------------------------------------------------------

    def get_state(self, key: str) -> str | None:
        """A small piece of server state."""
        row = self._db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_state(self, key: str, value: str) -> None:
        """Set a small piece of server state."""
        self._db.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value))

    # Retention ------------------------------------------------------------------------------

    def purge(self, before: datetime) -> int:
        """Delete everything recorded before ``before``; return how many rows went."""
        cutoff = _stamp(before)
        removed = 0
        for table, column in (
            ("inbound", "received_at"),
            ("documents", "created_at"),
            ("responses", "created_at"),
            ("frames", "created_at"),
            ("outbound", "sent_at"),
        ):
            cursor = self._db.execute(f"DELETE FROM {table} WHERE {column} < ?", (cutoff,))  # noqa: S608 - fixed names
            removed += cursor.rowcount
        return removed  # budget days are one small row each and stay as the cost history
