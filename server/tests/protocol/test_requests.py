from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from textwire.protocol.requests import (
    MAX_URL,
    MAX_WORDS,
    SIZED_VERBS,
    Request,
    RequestError,
    Verb,
    format_request,
    format_seqs,
    parse_request,
    parse_seqs,
)
from textwire.protocol.tags import decode_tag as decode

A7 = 367
B0 = 396


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a7 g https://example.com", Request(Verb.GET, tag=A7, url="https://example.com")),
        ("a7 g example.com/x?y=1", Request(Verb.GET, tag=A7, url="https://example.com/x?y=1")),
        ("A7 G8! HTTP://Example.com", Request(Verb.GET, A7, 8, True, url="HTTP://Example.com")),
        ("a7 s  weather   in london ", Request(Verb.SEARCH, tag=A7, words="weather in london")),
        ("s! weather", Request(Verb.SEARCH, plain=True, words="weather")),
        ("s1 weather", Request(Verb.SEARCH, size=1, words="weather")),
        ("s1 s weather", Request(Verb.SEARCH, tag=decode("s1"), words="weather")),
        ("b0 p a7 2", Request(Verb.PAGE, tag=B0, ref=A7, number=2)),
        ("p! A7 3", Request(Verb.PAGE, plain=True, ref=A7, number=3)),
        ("b0 l4 a7 12", Request(Verb.LINK, tag=B0, size=4, ref=A7, number=12)),
        ("b0 r a7 3,5-7,5", Request(Verb.RESEND, tag=B0, ref=A7, seqs=(3, 5, 6, 7))),
        ("?", Request(Verb.STATUS)),
        ("a7 ?!", Request(Verb.STATUS, tag=A7, plain=True)),
        ("h", Request(Verb.HELP)),
        ("  H  ", Request(Verb.HELP)),
        ("g8 h", Request(Verb.HELP, tag=decode("g8"))),
    ],
)
def test_requests_parse(text: str, expected: Request) -> None:
    assert parse_request(text) == expected


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "empty request"),
        ("   \n ", "empty request"),
        ("hello there", "unknown request"),
        ("hi there", "unknown request"),
        ("x", "unknown request"),
        ("a7", "unknown request"),
        ("g0 example.com", "size must be 1-255"),
        ("g256 example.com", "size must be 1-255"),
        ("r3 a7 1", "size not allowed here"),
        ("?2", "size not allowed here"),
        ("h9", "size not allowed here"),
        ("r! a7 1", "plain not allowed here"),
        ("g", "url missing"),
        ("a7 g", "url missing"),
        ("g exa mple.com", "url has spaces"),
        ("g ftp://example.com", "only http and https"),
        ("g " + "x" * MAX_URL, "url too long"),
        ("s", "words missing"),
        ("s " + "x" * (MAX_WORDS + 1), "words too long"),
        ("p a7", "expected tag and number"),
        ("p a!7 2", "expected tag and number"),
        ("p a7 x", "expected tag and number"),
        ("l a7 0", "number must be 1-255"),
        ("l a7 256", "number must be 1-255"),
        ("r a7", "expected tag and frames"),
        ("r a!7 1", "expected tag and frames"),
        ("r a7 x", "bad frame list"),
        ("r a7 1,", "bad frame list"),
        ("r a7 5-3", "bad frame list"),
        ("r a7 255", "bad frame list"),
        ("? now", "no arguments allowed"),
        ("h me", "no arguments allowed"),
    ],
)
def test_bad_requests_say_why_in_a_few_words(text: str, message: str) -> None:
    with pytest.raises(RequestError) as caught:
        parse_request(text)
    assert str(caught.value) == message
    assert len(message) <= 30


@pytest.mark.parametrize(
    ("seqs", "text"),
    [
        ((3,), "3"),
        ((3, 5, 6, 7), "3,5-7"),
        ((0, 1, 2, 9, 11, 12), "0-2,9,11-12"),
        ((4, 4, 2), "2,4"),
    ],
)
def test_frame_lists_use_the_shortest_ranges(seqs: tuple[int, ...], text: str) -> None:
    assert format_seqs(seqs) == text


def test_an_empty_frame_list_cannot_be_written() -> None:
    with pytest.raises(ValueError, match="no frame numbers"):
        format_seqs(())


def test_frame_lists_parse_sorted_and_deduplicated() -> None:
    assert parse_seqs("7,3,5-6,3") == (3, 5, 6, 7)


@pytest.mark.parametrize(
    ("request_", "text"),
    [
        (Request(Verb.GET, A7, 8, True, url="https://x.org"), "a7 g8! https://x.org"),
        (Request(Verb.SEARCH, words="a b"), "s a b"),
        (Request(Verb.PAGE, B0, ref=A7, number=2), "b0 p a7 2"),
        (Request(Verb.LINK, B0, 3, ref=A7, number=9), "b0 l3 a7 9"),
        (Request(Verb.RESEND, B0, ref=A7, seqs=(0, 1, 2, 5)), "b0 r a7 0-2,5"),
        (Request(Verb.STATUS, A7, plain=True), "a7 ?!"),
        (Request(Verb.HELP), "h"),
    ],
)
def test_requests_format_canonically(request_: Request, text: str) -> None:
    assert format_request(request_) == text


@pytest.mark.parametrize("verb", [Verb.PAGE, Verb.LINK, Verb.RESEND])
def test_a_reference_verb_without_its_reference_cannot_be_written(verb: Verb) -> None:
    with pytest.raises(ValueError, match="needs a referenced tag"):
        format_request(Request(verb, number=1, seqs=(1,)))


_TAGS = st.none() | st.integers(0, 1295)
_SIZES = st.none() | st.integers(1, 255)
_URLS = st.from_regex(r"https?://[a-z0-9.-]{1,40}(/[A-Za-z0-9._~%/?=&-]{0,60})?", fullmatch=True)
_WORDS = st.from_regex(r"[A-Za-z0-9é'?-]{1,20}( [A-Za-z0-9é'?-]{1,20}){0,5}", fullmatch=True)


@st.composite
def _requests(draw: st.DrawFn) -> Request:
    verb = draw(st.sampled_from(list(Verb)))
    tag = draw(_TAGS)
    size = draw(_SIZES) if verb in SIZED_VERBS else None
    plain = draw(st.booleans()) if verb is not Verb.RESEND else False
    base = Request(verb, tag=tag, size=size, plain=plain)
    match verb:
        case Verb.GET:
            return Request(verb, tag, size, plain, url=draw(_URLS))
        case Verb.SEARCH:
            return Request(verb, tag, size, plain, words=draw(_WORDS))
        case Verb.PAGE | Verb.LINK:
            return Request(
                verb,
                tag,
                size,
                plain,
                ref=draw(st.integers(0, 1295)),
                number=draw(st.integers(1, 255)),
            )
        case Verb.RESEND:
            seqs = draw(st.lists(st.integers(0, 254), min_size=1, max_size=40))
            return Request(verb, tag, ref=draw(st.integers(0, 1295)), seqs=tuple(sorted(set(seqs))))
        case _:
            return base


@given(_requests())
def test_every_canonical_request_parses_back_to_itself(request_: Request) -> None:
    assert parse_request(format_request(request_)) == request_
