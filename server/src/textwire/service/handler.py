"""The request handler: one inbound SMS in, its replies out (PROTOCOL.md sections 6 to 9).

Handling happens in three steps. *Resolve* turns the request into an outcome (a page of a
document, a status line, or frames to resend), doing any fetching or searching. *Render*
turns the outcome into SMS texts, encoded or plain. *Commit* checks the budget against the
exact count, stores what paging and resending will need, and charges the budget. Nothing is
stored or charged for a reply that is not going to be sent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from textwire.content.pages import page_count, page_payload, plain_document_pages
from textwire.logs import mask_number
from textwire.protocol.alphabets import Alphabet
from textwire.protocol.envelope import Envelope, Kind, pack_envelope
from textwire.protocol.frames import encode_frame, split_payload
from textwire.protocol.gsm7 import sanitize
from textwire.protocol.plain import MAX_MESSAGES, format_plain_page, plain_pages
from textwire.protocol.requests import Request, RequestError, Verb, parse_request
from textwire.protocol.tags import encode_tag, next_server_tag
from textwire.service.budget import BudgetExceededError
from textwire.service.library import Unavailable
from textwire.service.store import StoredDocument

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from textwire.clock import Clock
    from textwire.config import Settings
    from textwire.content.document import Document
    from textwire.protocol.compress import Dictionary
    from textwire.service.budget import Budget
    from textwire.service.library import Library
    from textwire.service.store import Store
    from textwire.transport.base import InboundMessage

log = logging.getLogger(__name__)

SERVER_TAG_KEY = "server_tag"
SMS_CHARS = 160


@dataclass(frozen=True, slots=True)
class Reply:
    """One SMS to send. ``seq`` is set for an encoded frame, ``None`` for plain text."""

    recipient: str
    text: str
    tag: int | None = None
    seq: int | None = None


@dataclass(frozen=True, slots=True)
class HandlerSettings:
    """The part of the configuration the handler uses."""

    allowed_numbers: frozenset[str]
    page_frames: int = 12
    max_page_frames: int = 40
    plain_messages: int = 4
    notice_interval: timedelta = timedelta(minutes=10)
    version: str = "0"
    alphabet: Alphabet = Alphabet.BASE64URL

    @classmethod
    def from_settings(cls, settings: Settings, version: str) -> HandlerSettings:
        """The handler's settings from the server's."""
        return cls(
            allowed_numbers=frozenset(settings.allowed_numbers),
            page_frames=settings.page_frames,
            max_page_frames=settings.max_page_frames,
            plain_messages=settings.plain_messages,
            notice_interval=timedelta(minutes=settings.notice_interval_minutes),
            version=version,
            alphabet=settings.frame_alphabet,
        )


@dataclass(frozen=True, slots=True)
class _Page:
    stored: StoredDocument
    number: int
    size: int


@dataclass(frozen=True, slots=True)
class _Status:
    text: str


@dataclass(frozen=True, slots=True)
class _Resend:
    ref: int
    frames: dict[int, str]


type _Outcome = _Page | _Status | _Resend


class Handler:
    """Answers requests from allowed numbers."""

    def __init__(
        self,
        *,
        library: Library,
        store: Store,
        budget: Budget,
        dictionary: Dictionary,
        clock: Clock,
        settings: HandlerSettings,
    ) -> None:
        self._library = library
        self._store = store
        self._budget = budget
        self._dictionary = dictionary
        self._clock = clock
        self._settings = settings

    async def handle(self, message: InboundMessage) -> list[Reply]:
        """The replies to one inbound SMS, already stored and charged."""
        number = message.sender
        if number not in self._settings.allowed_numbers:
            log.warning(
                "ignored a sender who is not allowed", extra={"sender": mask_number(number)}
            )
            return []
        try:
            request = parse_request(message.text)
        except RequestError as error:
            text = sanitize(f"E request {error}. Send h! for help.")[:SMS_CHARS]
            return self._notice(number, "request", [Reply(number, text)])
        tag = request.tag if request.tag is not None else self._next_server_tag()
        try:
            outcome = await self._resolve(number, request)
            replies, frames = self._render(number, tag, request.plain, outcome)
            self._budget.check(len(replies))
        except BudgetExceededError as exceeded:
            replies, frames = self._render(
                number, tag, request.plain, _Status(exceeded.status_text)
            )
            return self._notice(number, "budget", replies, tag, frames)
        self._commit(number, tag, outcome, replies, frames)
        log.info(
            "answered",
            extra={"verb": request.verb.value, "tag": encode_tag(tag), "sms": len(replies)},
        )
        return replies

    # Resolve ----------------------------------------------------------------------------------

    def _size(self, request: Request, fallback: int | None = None) -> int:
        if request.plain:
            return min(request.size or fallback or self._settings.plain_messages, MAX_MESSAGES)
        return min(
            request.size or fallback or self._settings.page_frames, self._settings.max_page_frames
        )

    async def _new_document(
        self, number: str, request: Request, source: Callable[[], Awaitable[Document]]
    ) -> _Outcome:
        size = self._size(request)
        self._budget.check(size)
        try:
            document = await source()
        except Unavailable as unavailable:
            return _Status(unavailable.status_text)
        stored = self._save(number, document, size, request.plain)
        return _Page(stored, 1, size)

    def _save(self, number: str, document: Document, size: int, plain: bool) -> StoredDocument:
        document_id = self._store.save_document(
            number, document, page_size=size, plain=plain, at=self._clock.now()
        )
        return StoredDocument(document_id, document, size, plain)

    def _pages_in(self, stored: StoredDocument, size: int, plain: bool) -> int:
        if plain:
            return len(plain_document_pages(stored.document, size))
        return page_count(stored.document, self._dictionary, size, self._settings.alphabet)

    async def _resolve(self, number: str, request: Request) -> _Outcome:
        match request.verb:
            case Verb.GET:
                url = str(request.url)
                return await self._new_document(number, request, lambda: self._library.page(url))
            case Verb.SEARCH:
                words = str(request.words)
                return await self._new_document(
                    number, request, lambda: self._library.search(words)
                )
            case Verb.LINK | Verb.PAGE:
                return await self._refer(number, request)
            case Verb.RESEND:
                ref = int(request.ref or 0)
                frames = self._store.load_frames(number, ref, request.seqs)
                if not frames:
                    return _Status(f"E resend unknown {encode_tag(ref)}")
                return _Resend(ref, frames)
            case Verb.HELP:
                size = self._size(request)
                return _Page(self._save(number, self._library.help(), size, request.plain), 1, size)
            case _:
                return _Status(self._usage())

    async def _refer(self, number: str, request: Request) -> _Outcome:
        ref, wanted = int(request.ref or 0), int(request.number or 0)
        area = "link" if request.verb is Verb.LINK else "page"
        stored = self._store.document_for(number, ref)
        if stored is None:
            return _Status(f"E {area} unknown {encode_tag(ref)}")
        if request.verb is Verb.LINK:
            links = stored.document.links
            if wanted > len(links):
                return _Status(f"E link range {wanted}/{len(links)}")
            url = links[wanted - 1]
            return await self._new_document(number, request, lambda: self._library.page(url))
        remembered = stored.page_size if stored.plain == request.plain else None
        size = self._size(request, remembered)
        count = self._pages_in(stored, size, request.plain)
        if wanted > count:
            return _Status(f"E page range {wanted}/{count}")
        return _Page(stored, wanted, size)

    def _usage(self) -> str:
        summary = self._budget.summary()
        return (
            f"I {summary.day.isoformat()} {summary.used}/{summary.limit} sms "
            f"~{summary.estimated_cost:.2f} {summary.currency} v{self._settings.version}"
        )

    # Render ------------------------------------------------------------------------------------

    def _encoded(self, number: str, tag: int, payload: bytes) -> tuple[list[Reply], dict[int, str]]:
        alphabet = self._settings.alphabet
        frames = split_payload(tag, payload, alphabet)
        texts = {frame.seq: encode_frame(frame, alphabet) for frame in frames}
        return [Reply(number, text, tag, seq) for seq, text in texts.items()], texts

    def _render(
        self, number: str, tag: int, plain: bool, outcome: _Outcome
    ) -> tuple[list[Reply], dict[int, str]]:
        match outcome:
            case _Resend(ref, frames):
                return [Reply(number, text, ref, seq) for seq, text in sorted(frames.items())], {}
            case _Page(stored, page, size) if plain:
                pages = plain_document_pages(stored.document, size)
                following = page + 1 if page < len(pages) else None
                texts = format_plain_page(pages[page - 1], encode_tag(tag), following)
                return [Reply(number, text, tag) for text in texts], {}
            case _Page(stored, page, size):
                payload = page_payload(
                    stored.document, self._dictionary, size, page, self._settings.alphabet
                )
                return self._encoded(number, tag, payload)
            case _Status(text) if plain:
                texts = format_plain_page(plain_pages(text, 1)[0], encode_tag(tag), None)
                return [Reply(number, text, tag) for text in texts], {}
        envelope = Envelope(kind=Kind.STATUS, page=1, pages=1, text=outcome.text)
        return self._encoded(number, tag, pack_envelope(envelope, self._dictionary))

    # Commit ------------------------------------------------------------------------------------

    def _commit(
        self,
        number: str,
        tag: int,
        outcome: _Outcome,
        replies: list[Reply],
        frames: dict[int, str],
    ) -> None:
        now = self._clock.now()
        if not isinstance(outcome, _Resend):
            document_id = outcome.stored.id if isinstance(outcome, _Page) else None
            self._store.link_response(number, tag, document_id, now)
            self._store.save_frames(number, tag, frames, now)
        self._budget.charge(len(replies))

    def _notice(
        self,
        number: str,
        kind: str,
        replies: list[Reply],
        tag: int | None = None,
        frames: dict[int, str] | None = None,
    ) -> list[Reply]:
        """A reply about a problem, sent at most once per sender per notice interval.

        Notices are charged but never refused: the budget notice exists because the budget
        is spent, and the rate limit is what bounds their cost.
        """
        key = f"notice:{kind}:{number}"
        now = self._clock.now()
        last = self._store.get_state(key)
        if last is not None and now - datetime.fromisoformat(last) < self._settings.notice_interval:
            log.info("notice suppressed", extra={"kind": kind})
            return []
        self._store.set_state(key, now.isoformat())
        if tag is not None:
            self._store.link_response(number, tag, None, now)
            self._store.save_frames(number, tag, frames or {}, now)
        self._budget.charge(len(replies))
        return replies

    def _next_server_tag(self) -> int:
        previous = self._store.get_state(SERVER_TAG_KEY)
        tag = next_server_tag(int(previous) if previous is not None else None)
        self._store.set_state(SERVER_TAG_KEY, str(tag))
        return tag
