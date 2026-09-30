"""Envelopes: the four bytes in front of every document page (PROTOCOL.md section 4)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from textwire.protocol.compress import CompressionError, Dictionary, compress, decompress

ENVELOPE_BYTES = 4
MAX_PAGES = 255
#: Compression is used only when it saves at least this many bytes.
MIN_SAVING = 8


class Kind(IntEnum):
    """What a document is."""

    PAGE = 1
    SEARCH = 2
    STATUS = 3
    HELP = 4


class Codec(IntEnum):
    """How the text after the envelope is encoded."""

    NONE = 0
    ZSTD = 1


class EnvelopeFault(StrEnum):
    """Why bytes are not an envelope, in the order the checks run."""

    SHORT = "short"
    KIND = "kind"
    CODEC = "codec"
    PAGE = "page"
    COMPRESSION = "compression"
    TEXT = "text"


class EnvelopeError(ValueError):
    """A reassembled payload is not a valid envelope."""

    def __init__(self, fault: EnvelopeFault) -> None:
        super().__init__(fault.value)
        self.fault = fault


@dataclass(frozen=True, slots=True)
class Envelope:
    """One page of a document, as the phone receives it."""

    kind: Kind
    page: int
    pages: int
    text: str

    def __post_init__(self) -> None:
        if not 1 <= self.page <= self.pages <= MAX_PAGES:
            msg = f"page {self.page} of {self.pages} is impossible"
            raise ValueError(msg)


def pack_envelope(envelope: Envelope, dictionary: Dictionary, codec: Codec | None = None) -> bytes:
    """The payload bytes of ``envelope``; the codec is chosen unless one is forced."""
    raw = envelope.text.encode("utf-8")
    body = raw
    if codec is not Codec.NONE:
        compressed = compress(raw, dictionary)
        if codec is Codec.ZSTD or len(compressed) + MIN_SAVING <= len(raw):
            codec, body = Codec.ZSTD, compressed
        else:
            codec = Codec.NONE
    return bytes((envelope.kind, codec, envelope.page, envelope.pages)) + body


def unpack_envelope(payload: bytes, dictionary: Dictionary) -> Envelope:
    """The envelope in ``payload``, or :class:`EnvelopeError` naming the first rule it breaks."""
    if len(payload) < ENVELOPE_BYTES:
        raise EnvelopeError(EnvelopeFault.SHORT)
    if payload[0] not in set(Kind):
        raise EnvelopeError(EnvelopeFault.KIND)
    if payload[1] not in set(Codec):
        raise EnvelopeError(EnvelopeFault.CODEC)
    page, pages = payload[2], payload[3]
    if not 1 <= page <= pages:
        raise EnvelopeError(EnvelopeFault.PAGE)
    body = payload[ENVELOPE_BYTES:]
    if payload[1] == Codec.ZSTD:
        try:
            body = decompress(body, dictionary)
        except CompressionError as error:
            raise EnvelopeError(EnvelopeFault.COMPRESSION) from error
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as error:
        raise EnvelopeError(EnvelopeFault.TEXT) from error
    return Envelope(kind=Kind(payload[0]), page=page, pages=pages, text=text)
