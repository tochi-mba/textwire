"""A virtual phone: the app's receiving logic, in Python, on the fake transport.

It sends requests the way the app does (a fresh tag each time, canonical text), collects the
frames of the reply in any order, asks for missing frames after a quiet spell, and returns
the page. The simulator and the end-to-end tests drive the real server through it.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from textwire.protocol.envelope import unpack_envelope
from textwire.protocol.frames import FrameError, decode_frame, join_frames
from textwire.protocol.requests import format_seqs
from textwire.protocol.tags import SERVER_TAG_FIRST, encode_tag

if TYPE_CHECKING:
    from textwire.clock import Clock
    from textwire.protocol.compress import Dictionary
    from textwire.protocol.envelope import Envelope
    from textwire.protocol.frames import Frame
    from textwire.transport.fake import FakeTransport

_PLAIN_PREFIX = re.compile(r"\[(?P<tag>[0-9a-z]{2}) (?P<index>\d)/(?P<count>\d)\]")
#: Frame numbers a resend request lists at most, so it stays one SMS.
MAX_RESEND_LIST = 40


@dataclass(frozen=True, slots=True)
class Page:
    """A complete encoded reply."""

    tag: int
    envelope: Envelope
    frames: int
    resends: int
    seconds: float


@dataclass(frozen=True, slots=True)
class PlainReply:
    """A complete plain reply: readable messages."""

    tag: int
    messages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Incomplete:
    """A reply that stopped arriving; ``missing`` lists the frames that never came."""

    tag: int
    received: int
    total: int | None
    missing: tuple[int, ...]


type Outcome = Page | PlainReply | Incomplete


@dataclass
class _Collector:
    tag: int
    frames: dict[int, Frame] = field(default_factory=dict)
    plain: dict[int, str] = field(default_factory=dict)
    plain_count: int | None = None
    total: int | None = None


class VirtualPhone:
    """The receiving half of the app, in memory."""

    def __init__(
        self,
        *,
        transport: FakeTransport,
        number: str,
        dictionary: Dictionary,
        clock: Clock,
        nak_after: float = 60.0,
        nak_rounds: int = 3,
    ) -> None:
        self._transport = transport
        self.number = number
        self._dictionary = dictionary
        self._clock = clock
        self._nak_after = nak_after
        self._nak_rounds = nak_rounds
        self._next = 0
        self.sent: list[str] = []
        self.rejected: list[str] = []

    def _tag(self) -> int:
        tag = self._next
        self._next = (self._next + 1) % SERVER_TAG_FIRST
        return tag

    def send(self, text: str) -> int:
        """Send ``text`` as a request under a fresh tag; return the tag."""
        tag = self._tag()
        request = f"{encode_tag(tag)} {text}"
        self.sent.append(request)
        self._transport.deliver(self.number, request)
        return tag

    async def ask(self, text: str) -> Outcome:
        """Send a request and wait for its reply."""
        return await self.collect(self.send(text))

    def _accept(self, collector: _Collector, text: str) -> None:
        try:
            frame = decode_frame(text)
        except FrameError:
            match = _PLAIN_PREFIX.match(text)
            if match is None or match["tag"] != encode_tag(collector.tag):
                self.rejected.append(text)
                return
            collector.plain[int(match["index"])] = text
            collector.plain_count = int(match["count"])
            return
        if frame.tag != collector.tag:
            self.rejected.append(text)
            return
        collector.frames.setdefault(frame.seq, frame)
        collector.total = frame.total

    def _finished(self, collector: _Collector, started: float, resends: int) -> Outcome | None:
        if collector.plain_count is not None and len(collector.plain) == collector.plain_count:
            messages = tuple(collector.plain[index] for index in sorted(collector.plain))
            return PlainReply(collector.tag, messages)
        if collector.total is not None and len(collector.frames) == collector.total:
            payload = join_frames(collector.frames.values())
            envelope = unpack_envelope(payload, self._dictionary)
            seconds = self._clock.now().timestamp() - started
            return Page(collector.tag, envelope, collector.total, resends, seconds)
        return None

    async def collect(self, tag: int) -> Outcome:
        """Wait for the reply tagged ``tag``, asking again for missing frames when it stalls."""
        collector = _Collector(tag)
        started = self._clock.now().timestamp()
        resends = 0
        while True:
            try:
                message = await asyncio.wait_for(self._transport.outbox.get(), self._nak_after)
            except TimeoutError:
                missing = tuple(
                    seq for seq in range(collector.total or 0) if seq not in collector.frames
                )
                if not missing or resends >= self._nak_rounds:
                    return Incomplete(tag, len(collector.frames), collector.total, missing)
                resends += 1
                self.send(f"r {encode_tag(tag)} {format_seqs(missing[:MAX_RESEND_LIST])}")
                continue
            if message.recipient == self.number:
                self._accept(collector, message.text)
            outcome = self._finished(collector, started, resends)
            if outcome is not None:
                return outcome
