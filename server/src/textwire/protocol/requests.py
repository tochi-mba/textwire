"""Requests: readable text from the phone (PROTOCOL.md section 6).

``parse_request`` accepts anything the grammar allows, including what a person types into a
messaging app; ``format_request`` writes the canonical form the phone app sends. The golden
vectors pin both, and ``parse_request(format_request(r)) == r`` for every valid request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum

from textwire.protocol.frames import MAX_FRAMES
from textwire.protocol.tags import decode_tag, encode_tag, is_tag

MAX_URL = 2000
MAX_WORDS = 300
MAX_NUMBER = 255
MAX_SEQ = MAX_FRAMES - 1

_VERB_TOKEN = re.compile(r"(?P<verb>[gsplrh?])(?P<size>\d{1,3})?(?P<plain>!)?", re.IGNORECASE)
_REF_NUMBER = re.compile(r"(?P<tag>\S+)\s+(?P<number>\d{1,3})")
_REF_SEQS = re.compile(r"(?P<tag>\S+)\s+(?P<seqs>\S+)")
_SEQ_ITEM = re.compile(r"(?P<first>\d{1,3})(?:-(?P<last>\d{1,3}))?")

# The messages a bad request gets back (PROTOCOL.md section 6.4).
EMPTY = "empty request"
UNKNOWN = "unknown request"
SIZE_RANGE = "size must be 1-255"
SIZE_NOT_ALLOWED = "size not allowed here"
PLAIN_NOT_ALLOWED = "plain not allowed here"
URL_MISSING = "url missing"
URL_SPACES = "url has spaces"
URL_TOO_LONG = "url too long"
URL_SCHEME = "only http and https"
WORDS_MISSING = "words missing"
WORDS_TOO_LONG = "words too long"
EXPECTED_REFERENCE = "expected tag and number"
NUMBER_RANGE = "number must be 1-255"
EXPECTED_FRAMES = "expected tag and frames"
BAD_FRAMES = "bad frame list"
NO_ARGUMENTS = "no arguments allowed"


class Verb(StrEnum):
    """What a request asks for."""

    GET = "g"
    SEARCH = "s"
    PAGE = "p"
    LINK = "l"
    RESEND = "r"
    STATUS = "?"
    HELP = "h"


#: Verbs whose replies are paged, and so accept a size.
SIZED_VERBS = frozenset({Verb.GET, Verb.SEARCH, Verb.PAGE, Verb.LINK})


class RequestError(ValueError):
    """A request that does not parse. The message is short enough to text back."""


@dataclass(frozen=True, slots=True)
class Request:
    """One parsed request. Which optional fields are set depends on the verb."""

    verb: Verb
    tag: int | None = None
    size: int | None = None
    plain: bool = False
    url: str | None = None
    words: str | None = None
    ref: int | None = None
    number: int | None = None
    seqs: tuple[int, ...] = ()


def _split(text: str) -> tuple[str | None, re.Match[str], str]:
    """The tag (if any), the verb token and the rest, by the tag rule in section 6.1."""
    words = text.split(None, 2)
    if len(words) >= 2 and is_tag(words[0]):  # noqa: PLR2004
        token = _VERB_TOKEN.fullmatch(words[1])
        if token is not None:
            return words[0], token, words[2] if len(words) == 3 else ""  # noqa: PLR2004
    head, *rest = text.split(None, 1)
    token = _VERB_TOKEN.fullmatch(head)
    if token is None:
        raise RequestError(UNKNOWN)
    return None, token, rest[0] if rest else ""


def parse_seqs(text: str) -> tuple[int, ...]:
    """``"3,5-7"`` becomes ``(3, 5, 6, 7)``: sorted, without duplicates."""
    seqs: set[int] = set()
    for item in text.split(","):
        match = _SEQ_ITEM.fullmatch(item)
        if match is None:
            raise RequestError(BAD_FRAMES)
        first = int(match["first"])
        last = int(match["last"]) if match["last"] is not None else first
        if first > last or last > MAX_SEQ:
            raise RequestError(BAD_FRAMES)
        seqs.update(range(first, last + 1))
    return tuple(sorted(seqs))


def format_seqs(seqs: tuple[int, ...]) -> str:
    """The shortest form of a set of frame numbers: ``(3, 5, 6, 7)`` becomes ``"3,5-7"``."""
    ordered = sorted(set(seqs))
    if not ordered:
        msg = "no frame numbers"
        raise ValueError(msg)
    runs: list[list[int]] = [[ordered[0], ordered[0]]]
    for seq in ordered[1:]:
        if seq == runs[-1][1] + 1:
            runs[-1][1] = seq
        else:
            runs.append([seq, seq])
    return ",".join(str(first) if first == last else f"{first}-{last}" for first, last in runs)


def _ref_and_number(arguments: str) -> tuple[int, int]:
    match = _REF_NUMBER.fullmatch(arguments)
    if match is None or not is_tag(match["tag"]):
        raise RequestError(EXPECTED_REFERENCE)
    number = int(match["number"])
    if not 1 <= number <= MAX_NUMBER:
        raise RequestError(NUMBER_RANGE)
    return decode_tag(match["tag"]), number


def _ref_and_seqs(arguments: str) -> tuple[int, tuple[int, ...]]:
    match = _REF_SEQS.fullmatch(arguments)
    if match is None or not is_tag(match["tag"]):
        raise RequestError(EXPECTED_FRAMES)
    return decode_tag(match["tag"]), parse_seqs(match["seqs"])


def _url(arguments: str) -> str:
    if not arguments:
        raise RequestError(URL_MISSING)
    if any(char.isspace() for char in arguments):
        raise RequestError(URL_SPACES)
    url = arguments if "://" in arguments else "https://" + arguments
    if len(url) > MAX_URL:
        raise RequestError(URL_TOO_LONG)
    if not url.lower().startswith(("http://", "https://")):
        raise RequestError(URL_SCHEME)
    return url


def _words(arguments: str) -> str:
    words = " ".join(arguments.split())
    if not words:
        raise RequestError(WORDS_MISSING)
    if len(words) > MAX_WORDS:
        raise RequestError(WORDS_TOO_LONG)
    return words


def _size(verb: Verb, digits: str | None) -> int | None:
    if digits is None:
        return None
    if verb not in SIZED_VERBS:
        raise RequestError(SIZE_NOT_ALLOWED)
    size = int(digits)
    if not 1 <= size <= MAX_NUMBER:
        raise RequestError(SIZE_RANGE)
    return size


def parse_request(text: str) -> Request:
    """The request in ``text``, or :class:`RequestError` with a message to text back."""
    stripped = text.strip()
    if not stripped:
        raise RequestError(EMPTY)
    tag_text, token, arguments = _split(stripped)
    verb = Verb(token["verb"].lower())
    request = Request(
        verb=verb,
        tag=decode_tag(tag_text) if tag_text is not None else None,
        size=_size(verb, token["size"]),
        plain=token["plain"] is not None,
    )
    arguments = arguments.strip()
    match verb:
        case Verb.GET:
            return replace(request, url=_url(arguments))
        case Verb.SEARCH:
            return replace(request, words=_words(arguments))
        case Verb.PAGE | Verb.LINK:
            ref, number = _ref_and_number(arguments)
            return replace(request, ref=ref, number=number)
        case Verb.RESEND:
            if request.plain:
                raise RequestError(PLAIN_NOT_ALLOWED)
            ref, seqs = _ref_and_seqs(arguments)
            return replace(request, ref=ref, seqs=seqs)
        case _:
            if arguments:
                raise RequestError(NO_ARGUMENTS)
            return request


def _ref(request: Request) -> str:
    if request.ref is None:
        msg = f"a {request.verb.value!r} request needs a referenced tag"
        raise ValueError(msg)
    return encode_tag(request.ref)


def format_request(request: Request) -> str:
    """The canonical text of ``request``: what the phone app sends."""
    head = request.verb.value
    if request.size is not None:
        head += str(request.size)
    if request.plain:
        head += "!"
    words = [encode_tag(request.tag)] if request.tag is not None else []
    words.append(head)
    match request.verb:
        case Verb.GET:
            words.append(str(request.url))
        case Verb.SEARCH:
            words.append(str(request.words))
        case Verb.PAGE | Verb.LINK:
            words += [_ref(request), str(request.number)]
        case Verb.RESEND:
            words += [_ref(request), format_seqs(request.seqs)]
        case _:
            pass
    return " ".join(words)
