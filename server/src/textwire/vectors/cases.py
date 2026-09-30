"""The cases: fixed inputs for every rule, and what each one must produce."""

from __future__ import annotations

import base64
import dataclasses
from typing import TYPE_CHECKING, Any

import zstandard

from textwire.protocol.alphabets import Alphabet
from textwire.protocol.compress import (
    DICTIONARY_ID,
    MAX_TEXT_BYTES,
    Dictionary,
)
from textwire.protocol.envelope import (
    MIN_SAVING,
    Codec,
    Envelope,
    EnvelopeError,
    EnvelopeFault,
    Kind,
    pack_envelope,
    unpack_envelope,
)
from textwire.protocol.frames import (
    FRAME_CHARS,
    HEADER_BYTES,
    MAX_FRAMES,
    VERSION,
    Frame,
    FrameError,
    FrameFault,
    FrameType,
    body_bytes,
    crc8,
    decode_frame,
    encode_frame,
)
from textwire.protocol.requests import (
    MAX_URL,
    MAX_WORDS,
    Request,
    RequestError,
    Verb,
    format_request,
    parse_request,
)
from textwire.protocol.tags import SERVER_TAG_FIRST, TAG_COUNT

if TYPE_CHECKING:
    from collections.abc import Iterator

type Json = dict[str, Any]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _raw_frame(first: int, tag: int, seq: int, total: int, body: bytes, crc: int | None) -> str:
    header = bytes((first, tag >> 8, tag & 0xFF, seq, total))
    return _b64(header + bytes((crc8(header + body) if crc is None else crc,)) + body)


def _frame_json(frame: Frame) -> Json:
    return {
        "tag": frame.tag,
        "seq": frame.seq,
        "total": frame.total,
        "type": int(frame.type),
        "body_hex": frame.body.hex(),
    }


def frame_fault(text: str) -> str:
    """The reason ``text`` is rejected; a text that decodes is a mistake in the case list."""
    try:
        decode_frame(text)
    except FrameError as error:
        return error.fault.value
    msg = f"{text!r} decodes, so it cannot be a rejection case"
    raise AssertionError(msg)


def request_error(text: str) -> str:
    """The error ``text`` gets; a text that parses is a mistake in the case list."""
    try:
        parse_request(text)
    except RequestError as error:
        return str(error)
    msg = f"{text!r} parses, so it cannot be a rejection case"
    raise AssertionError(msg)


def envelope_fault(payload: bytes, dictionary: Dictionary) -> str:
    """The reason ``payload`` is rejected; one that unpacks is a mistake in the case list."""
    try:
        unpack_envelope(payload, dictionary)
    except EnvelopeError as error:
        return error.fault.value
    msg = f"{payload.hex()} unpacks, so it cannot be a rejection case"
    raise AssertionError(msg)


def frame_cases() -> Iterator[tuple[str, Json]]:
    """Frames that must encode and decode both ways, and texts each rejected for one reason."""
    valid = {
        "data-empty": Frame(tag=0, seq=0, total=1, body=b""),
        "data-full": Frame(
            tag=TAG_COUNT - 1,
            seq=MAX_FRAMES - 1,
            total=MAX_FRAMES,
            body=bytes(range(body_bytes(Alphabet.BASE64URL))),
        ),
        "data-typical": Frame(tag=367, seq=3, total=12, body=b"textwire frame body"),
        "data-server-tag": Frame(tag=SERVER_TAG_FIRST, seq=0, total=2, body=b"\x00\xff\x80"),
        "data-short-last": Frame(tag=1, seq=11, total=12, body=bytes(range(200, 237))),
    }
    for name, frame in valid.items():
        for alphabet in Alphabet:
            yield (
                f"frames/{alphabet.value}-{name}",
                {
                    "text": encode_frame(frame, alphabet),
                    "alphabet": alphabet.value,
                    "frame": _frame_json(frame),
                    "fault": None,
                },
            )
    widest = Frame(tag=2, seq=0, total=1, body=bytes(range(100, 100 + 121)))
    yield (
        "frames/z85g-data-widest",
        {
            "text": encode_frame(widest, Alphabet.Z85G),
            "alphabet": Alphabet.Z85G.value,
            "frame": _frame_json(widest),
            "fault": None,
        },
    )
    padded = Frame(tag=5, seq=1, total=2, body=b"ok")
    yield (
        "frames/accept-surrounding-whitespace",
        {
            "text": f"  {encode_frame(padded)}\n",
            "alphabet": Alphabet.BASE64URL.value,
            "frame": _frame_json(padded),
            "fault": None,
        },
    )
    rejections = {
        "reject-encoding-character": "AAAA*AAA",
        "reject-encoding-remainder": "AAAAA",
        "reject-encoding-noncanonical": "AB",
        "reject-encoding-padding": "AAAA=",
        "reject-encoding-reserved-prefix": "!" + encode_frame(padded)[1:],
        "reject-length-empty": "",
        "reject-length-short": _b64(bytes((0x11, 0, 0, 0, 1))),
        "reject-length-long": _b64(bytes(Alphabet.BASE64URL.frame_bytes + 1)),
        "reject-z85g-encoding-character": "." + "~" * 5,
        "reject-z85g-encoding-remainder": "." + "0" * 6,
        "reject-z85g-encoding-noncanonical": ".#1",
        "reject-z85g-encoding-overflow": ".#####",
        "reject-z85g-length-long": "." + "0" * 160,
        "reject-version": _raw_frame(0x21, 0, 0, 1, b"", crc=None),
        "reject-version-before-crc": _raw_frame(0x21, 0, 0, 1, b"", crc=0x55),
        "reject-crc": _raw_frame(0x11, 0, 0, 1, b"x", crc=0),
        "reject-type": _raw_frame(0x12, 0, 0, 1, b"", crc=None),
        "reject-tag": _raw_frame(0x11, TAG_COUNT, 0, 1, b"", crc=None),
        "reject-sequence-zero-total": _raw_frame(0x11, 0, 0, 0, b"", crc=None),
        "reject-sequence-past-total": _raw_frame(0x11, 0, 3, 3, b"", crc=None),
    }
    for name, text in rejections.items():
        yield (
            f"frames/{name}",
            {"text": text, "alphabet": None, "frame": None, "fault": frame_fault(text)},
        )


def _request_json(request: Request) -> Json:
    return {
        field.name: _plain(getattr(request, field.name)) for field in dataclasses.fields(request)
    }


def _plain(value: object) -> object:
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Verb):
        return value.value
    return value


REQUEST_TEXTS = {
    "get": "a7 g https://example.com/path?q=1",
    "get-no-scheme": "a7 g bbc.co.uk/news",
    "get-sized-plain": "A7 G8! http://Example.com",
    "get-untagged": "g https://example.com",
    "search": "b0 s weather in  london",
    "search-plain-untagged": "s! weather london",
    "search-tag-rule-untagged": "s1 weather",
    "search-tag-rule-tagged": "s1 s weather",
    "search-unicode": "c3 s caf\N{LATIN SMALL LETTER E WITH ACUTE} de flore",
    "page": "b1 p a7 2",
    "page-plain-sized": "b1 p4! a7 12",
    "link": "b2 l a7 7",
    "resend": "b3 r a7 3,5-7,5",
    "resend-single": "b3 r a7 0",
    "status": "?",
    "status-tagged-plain": "a8 ?!",
    "help": "h",
    "help-tag-rule": "g8 h",
}
REQUEST_ERRORS = {
    "empty": " ",
    "unknown": "hello there",
    "size-zero": "g0 example.com",
    "size-too-big": "g256 example.com",
    "size-not-allowed": "r3 a7 1",
    "plain-not-allowed": "r! a7 1",
    "url-missing": "a7 g",
    "url-spaces": "g exa mple.com",
    "url-scheme": "g ftp://example.com",
    "url-too-long": "g https://" + "x" * MAX_URL,
    "words-missing": "s",
    "words-too-long": "s " + "x" * (MAX_WORDS + 1),
    "reference-missing": "p a7",
    "reference-number-zero": "l a7 0",
    "resend-missing": "r a7",
    "resend-bad-list": "r a7 5-3",
    "arguments-not-allowed": "? now",
}


def request_cases() -> Iterator[tuple[str, Json]]:
    """Requests that parse, with their canonical text, and requests that do not, with why."""
    for name, text in REQUEST_TEXTS.items():
        request = parse_request(text)
        yield (
            f"requests/{name}",
            {
                "text": text,
                "request": _request_json(request),
                "canonical": format_request(request),
                "error": None,
            },
        )
    for name, text in REQUEST_ERRORS.items():
        yield (
            f"requests/reject-{name}",
            {"text": text, "request": None, "canonical": None, "error": request_error(text)},
        )


def _envelope_json(envelope: Envelope) -> Json:
    return {
        "kind": int(envelope.kind),
        "page": envelope.page,
        "pages": envelope.pages,
        "text": envelope.text,
    }


ARTICLE_TEXT = (
    "# Village gets its first text-only library\n\n"
    "Residents of Dunmore, a hill village with no mobile data signal, can now borrow the news by "
    "text message. The scheme[1] answers any question sent to a single number with a short, "
    "readable page.\n\n## How it works\n\n- Search the web by texting a few words\n"
    "- Open any page by texting its address\n- Follow a link by texting its number[2]\n\n"
    "1. A search usually takes four messages.\n2. A news story usually takes twelve."
)


def envelope_cases(dictionary: Dictionary) -> Iterator[tuple[str, Json]]:
    """Envelopes and their payloads, and payloads each rejected for one reason."""
    valid: dict[str, tuple[Envelope, Codec | None]] = {
        "page-compressed": (Envelope(Kind.PAGE, 1, 1, ARTICLE_TEXT), None),
        "page-3-of-7": (Envelope(Kind.PAGE, 3, 7, ARTICLE_TEXT), None),
        "search-compressed": (
            Envelope(
                Kind.SEARCH,
                1,
                1,
                "# Search: weather\n\n1. London - BBC Weather[1] (bbc.co.uk)\n14-day forecast.",
            ),
            None,
        ),
        "status-uncompressed": (Envelope(Kind.STATUS, 1, 1, "E fetch status 404"), None),
        "help-uncompressed": (
            Envelope(Kind.HELP, 1, 1, "# textwire help\n\ng <address> - open a page"),
            Codec.NONE,
        ),
        "unicode-compressed": (
            Envelope(
                Kind.PAGE,
                1,
                1,
                "# Caf\N{LATIN SMALL LETTER E WITH ACUTE}\n\n\N{GRINNING FACE} " * 3,
            ),
            Codec.ZSTD,
        ),
        "unicode-uncompressed": (
            Envelope(Kind.PAGE, 1, 1, "\N{EURO SIGN}5 \N{SNOWMAN}"),
            Codec.NONE,
        ),
        "empty-text": (Envelope(Kind.STATUS, 1, 1, ""), None),
    }
    for name, (envelope, codec) in valid.items():
        payload = pack_envelope(envelope, dictionary, codec)
        yield (
            f"envelopes/{name}",
            {
                "envelope": _envelope_json(envelope),
                "codec": payload[1],
                "payload_hex": payload.hex(),
                "fault": None,
            },
        )
    unsized = zstandard.ZstdCompressor(write_content_size=False).compress(b"no size")
    oversized = zstandard.ZstdCompressor().compress(b" " * (MAX_TEXT_BYTES + 1))
    rejections = {
        "reject-short": bytes((1, 0, 1)),
        "reject-kind": bytes((9, 0, 1, 1)) + b"x",
        "reject-codec": bytes((1, 7, 1, 1)) + b"x",
        "reject-page-zero": bytes((1, 0, 0, 1)) + b"x",
        "reject-page-past": bytes((1, 0, 3, 2)) + b"x",
        "reject-compression-garbage": bytes((1, 1, 1, 1)) + b"not zstd",
        "reject-compression-no-size": bytes((1, 1, 1, 1)) + unsized,
        "reject-compression-too-large": bytes((1, 1, 1, 1)) + oversized,
        "reject-text": bytes((1, 0, 1, 1)) + b"\xff\xfe",
    }
    for name, payload in rejections.items():
        yield (
            f"envelopes/{name}",
            {
                "envelope": None,
                "codec": None,
                "payload_hex": payload.hex(),
                "fault": envelope_fault(payload, dictionary),
            },
        )


def ids(dictionary: Dictionary) -> Json:
    """Every numbered constant and reason code, for each implementation to compare with its own."""
    return {
        "frame": {
            "version": VERSION,
            "types": {member.name: int(member) for member in FrameType},
            "faults": [fault.value for fault in FrameFault],
            "chars": FRAME_CHARS,
            "header_bytes": HEADER_BYTES,
            "max_frames": MAX_FRAMES,
            "alphabets": {
                alphabet.value: {
                    "marker": alphabet.marker,
                    "frame_bytes": alphabet.frame_bytes,
                    "body_bytes": alphabet.frame_bytes - HEADER_BYTES,
                }
                for alphabet in Alphabet
            },
        },
        "tags": {"count": TAG_COUNT, "server_first": SERVER_TAG_FIRST},
        "envelope": {
            "kinds": {member.name: int(member) for member in Kind},
            "codecs": {member.name: int(member) for member in Codec},
            "faults": [fault.value for fault in EnvelopeFault],
            "max_text_bytes": MAX_TEXT_BYTES,
            "min_saving": MIN_SAVING,
        },
        "requests": {"verbs": {member.name: member.value for member in Verb}},
        "dictionary": {
            "id": DICTIONARY_ID,
            "sha256": dictionary.sha256,
            "size": len(dictionary.data),
        },
    }
