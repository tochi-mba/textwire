from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from textwire.protocol.compress import Dictionary, compress, load_dictionary
from textwire.protocol.envelope import (
    ENVELOPE_BYTES,
    MIN_SAVING,
    Codec,
    Envelope,
    EnvelopeError,
    EnvelopeFault,
    Kind,
    pack_envelope,
    unpack_envelope,
)

LONG = "# A page\n\n" + "The same sentence about the weather in London. " * 20


@pytest.fixture(scope="module")
def dictionary() -> Dictionary:
    return load_dictionary()


def test_the_header_is_kind_codec_page_pages(dictionary: Dictionary) -> None:
    payload = pack_envelope(Envelope(Kind.SEARCH, 2, 7, LONG), dictionary)
    assert payload[:ENVELOPE_BYTES] == bytes((Kind.SEARCH, Codec.ZSTD, 2, 7))


def test_text_that_compresses_well_is_compressed(dictionary: Dictionary) -> None:
    payload = pack_envelope(Envelope(Kind.PAGE, 1, 1, LONG), dictionary)
    assert payload[1] == Codec.ZSTD
    assert len(payload) < len(LONG) // 4


def test_short_text_is_sent_as_it_is(dictionary: Dictionary) -> None:
    payload = pack_envelope(Envelope(Kind.STATUS, 1, 1, "E fetch status 404"), dictionary)
    assert payload == bytes((Kind.STATUS, Codec.NONE, 1, 1)) + b"E fetch status 404"


def test_compression_must_save_at_least_eight_bytes(dictionary: Dictionary) -> None:
    for length in range(1, 400):
        text = "".join(chr(0x41 + (n * 7919) % 26) for n in range(length))
        compressed = compress(text.encode(), dictionary)
        payload = pack_envelope(Envelope(Kind.PAGE, 1, 1, text), dictionary)
        expected = Codec.ZSTD if len(compressed) + MIN_SAVING <= len(text) else Codec.NONE
        assert payload[1] == expected


@pytest.mark.parametrize("codec", [Codec.NONE, Codec.ZSTD])
def test_a_codec_can_be_forced(dictionary: Dictionary, codec: Codec) -> None:
    payload = pack_envelope(Envelope(Kind.HELP, 1, 1, "hi"), dictionary, codec)
    assert payload[1] == codec
    assert unpack_envelope(payload, dictionary).text == "hi"


@settings(max_examples=40, deadline=None)
@given(
    kind=st.sampled_from(list(Kind)),
    pages=st.integers(1, 255),
    data=st.data(),
    text=st.text(max_size=2000),
)
def test_every_envelope_survives_a_round_trip(
    kind: Kind, pages: int, data: st.DataObject, text: str
) -> None:
    dictionary = load_dictionary()
    envelope = Envelope(kind, data.draw(st.integers(1, pages)), pages, text)
    assert unpack_envelope(pack_envelope(envelope, dictionary), dictionary) == envelope


@pytest.mark.parametrize(("page", "pages"), [(0, 1), (2, 1), (1, 256)])
def test_impossible_pages_cannot_be_built(page: int, pages: int) -> None:
    with pytest.raises(ValueError, match="impossible"):
        Envelope(Kind.PAGE, page, pages, "")


@pytest.mark.parametrize(
    ("payload", "fault"),
    [
        (b"\x01\x00\x01", EnvelopeFault.SHORT),
        (b"\x09\x00\x01\x01x", EnvelopeFault.KIND),
        (b"\x00\x00\x01\x01x", EnvelopeFault.KIND),
        (b"\x01\x07\x01\x01x", EnvelopeFault.CODEC),
        (b"\x01\x00\x00\x01x", EnvelopeFault.PAGE),
        (b"\x01\x00\x03\x02x", EnvelopeFault.PAGE),
        (b"\x01\x01\x01\x01garbage", EnvelopeFault.COMPRESSION),
        (b"\x01\x00\x01\x01\xff\xfe", EnvelopeFault.TEXT),
    ],
)
def test_rejections_name_the_first_rule_broken(
    dictionary: Dictionary, payload: bytes, fault: EnvelopeFault
) -> None:
    with pytest.raises(EnvelopeError) as caught:
        unpack_envelope(payload, dictionary)
    assert caught.value.fault is fault
    assert str(caught.value) == fault.value
