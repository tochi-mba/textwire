from __future__ import annotations

import base64

import pytest
from hypothesis import given
from hypothesis import strategies as st

from textwire.protocol.alphabets import Alphabet
from textwire.protocol.frames import (
    BODY_BYTES,
    FRAME_CHARS,
    MAX_BODY_BYTES,
    MAX_FRAMES,
    Frame,
    FrameError,
    FrameFault,
    FrameType,
    MissingFramesError,
    PayloadTooLargeError,
    body_bytes,
    crc8,
    decode_frame,
    encode_frame,
    join_frames,
    max_payload,
    split_payload,
)


def _text(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _raw(
    first: int, tag: int, seq: int, total: int, body: bytes = b"", crc: int | None = None
) -> str:
    header = bytes((first, tag >> 8, tag & 0xFF, seq, total))
    check = crc8(header + body) if crc is None else crc
    return _text(header + bytes((check,)) + body)


def test_crc8_matches_the_published_check_value() -> None:
    assert crc8(b"123456789") == 0xF4
    assert crc8(b"") == 0


@pytest.mark.parametrize("alphabet", list(Alphabet))
def test_a_full_frame_is_exactly_one_sms(alphabet: Alphabet) -> None:
    body = bytes(range(body_bytes(alphabet)))
    frame = Frame(tag=1295, seq=254, total=255, body=body)
    assert len(encode_frame(frame, alphabet)) == FRAME_CHARS
    assert decode_frame(encode_frame(frame, alphabet)) == frame


def test_body_sizes_per_alphabet() -> None:
    assert body_bytes(Alphabet.BASE64URL) == BODY_BYTES == 114
    assert body_bytes(Alphabet.Z85G) == MAX_BODY_BYTES == 121
    assert max_payload(Alphabet.Z85G) == 255 * 121


def test_a_body_too_big_for_its_alphabet_cannot_be_encoded() -> None:
    frame = Frame(tag=0, seq=0, total=1, body=bytes(MAX_BODY_BYTES))
    with pytest.raises(ValueError, match="at most 114"):
        encode_frame(frame, Alphabet.BASE64URL)
    assert len(encode_frame(frame, Alphabet.Z85G)) == FRAME_CHARS


def test_an_empty_frame_is_eight_characters() -> None:
    assert len(encode_frame(Frame(tag=0, seq=0, total=1, body=b""))) == 8


@given(
    tag=st.integers(0, 1295),
    total=st.integers(1, MAX_FRAMES),
    data=st.data(),
    body=st.binary(max_size=BODY_BYTES),
    alphabet=st.sampled_from(list(Alphabet)),
)
def test_every_frame_survives_a_round_trip(
    tag: int, total: int, data: st.DataObject, body: bytes, alphabet: Alphabet
) -> None:
    seq = data.draw(st.integers(0, total - 1))
    frame = Frame(tag=tag, seq=seq, total=total, body=body)
    text = encode_frame(frame, alphabet)
    assert len(text) <= FRAME_CHARS
    assert text.startswith(alphabet.marker)
    assert decode_frame(text) == frame


def test_surrounding_whitespace_is_ignored() -> None:
    frame = Frame(tag=7, seq=0, total=1, body=b"hi")
    assert decode_frame(f"  {encode_frame(frame)}\n") == frame


@pytest.mark.parametrize(
    ("text", "fault"),
    [
        ("AAAA*AAA", FrameFault.ENCODING),
        ("AAAAA", FrameFault.ENCODING),  # a remainder of one character cannot be base64
        ("AB", FrameFault.ENCODING),  # non-zero padding bits: not canonical
        ("AAAA=", FrameFault.ENCODING),  # padding is not allowed
        ("", FrameFault.LENGTH),
        (_text(b"\x11\x00\x00\x00\x01"), FrameFault.LENGTH),  # five bytes
        (_text(bytes(121)), FrameFault.LENGTH),
        (".~~~~~", FrameFault.ENCODING),
        ("." + "0" * 160, FrameFault.LENGTH),  # z85g: 128 bytes
        (_raw(0x21, 0, 0, 1), FrameFault.VERSION),
        (_raw(0x11, 0, 0, 1, b"x", crc=0), FrameFault.CRC),
        (_raw(0x12, 0, 0, 1), FrameFault.TYPE),
        (_raw(0x11, 1296, 0, 1), FrameFault.TAG),
        (_raw(0x11, 0, 0, 0), FrameFault.SEQUENCE),
        (_raw(0x11, 0, 3, 3), FrameFault.SEQUENCE),
    ],
)
def test_rejections_name_the_first_rule_broken(text: str, fault: FrameFault) -> None:
    with pytest.raises(FrameError) as caught:
        decode_frame(text)
    assert caught.value.fault is fault
    assert str(caught.value) == fault.value


def test_a_future_version_is_reported_before_its_crc() -> None:
    with pytest.raises(FrameError) as caught:
        decode_frame(_raw(0x21, 0, 0, 1, crc=0x55))
    assert caught.value.fault is FrameFault.VERSION


@pytest.mark.parametrize(
    ("tag", "seq", "total", "body"),
    [(-1, 0, 1, b""), (1296, 0, 1, b""), (0, 0, 0, b""), (0, 1, 1, b""), (0, 0, 256, b"")],
)
def test_impossible_frames_cannot_be_built(tag: int, seq: int, total: int, body: bytes) -> None:
    with pytest.raises(ValueError, match=r"outside|impossible"):
        Frame(tag=tag, seq=seq, total=total, body=body)


def test_a_body_larger_than_any_frame_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="at most 121"):
        Frame(tag=0, seq=0, total=1, body=bytes(MAX_BODY_BYTES + 1))


def test_an_empty_payload_is_one_empty_frame() -> None:
    assert split_payload(5, b"") == [Frame(tag=5, seq=0, total=1, body=b"")]


def test_payloads_are_cut_into_full_frames_and_a_remainder() -> None:
    frames = split_payload(9, bytes(BODY_BYTES * 2 + 1))
    assert [(frame.seq, frame.total, len(frame.body)) for frame in frames] == [
        (0, 3, BODY_BYTES),
        (1, 3, BODY_BYTES),
        (2, 3, 1),
    ]
    assert all(frame.type is FrameType.DATA for frame in frames)


@pytest.mark.parametrize("alphabet", list(Alphabet))
def test_the_largest_payload_fits_in_255_frames_and_one_more_byte_does_not(
    alphabet: Alphabet,
) -> None:
    assert len(split_payload(0, bytes(max_payload(alphabet)), alphabet)) == MAX_FRAMES
    with pytest.raises(PayloadTooLargeError):
        split_payload(0, bytes(max_payload(alphabet) + 1), alphabet)


def test_z85g_frames_carry_more_per_frame() -> None:
    payload = bytes(121 * 3)
    assert len(split_payload(0, payload, Alphabet.Z85G)) == 3
    assert len(split_payload(0, payload, Alphabet.BASE64URL)) == 4


@given(st.binary(max_size=2000), st.randoms(use_true_random=False))
def test_joining_frames_in_any_order_restores_the_payload(payload: bytes, rng: object) -> None:
    frames = split_payload(42, payload)
    shuffled = [*frames, *frames[:1]]  # a duplicate, too
    rng.shuffle(shuffled)  # type: ignore[attr-defined]
    assert join_frames(shuffled) == payload


def test_missing_frames_are_reported_in_order() -> None:
    frames = split_payload(1, bytes(BODY_BYTES * 5))
    with pytest.raises(MissingFramesError) as caught:
        join_frames([frames[4], frames[1]])
    assert caught.value.missing == [0, 2, 3]
    assert str(caught.value) == "missing frames 0,2,3"


def test_frames_from_two_responses_are_not_joined() -> None:
    first = split_payload(1, b"a")[0]
    second = split_payload(2, b"b")[0]
    with pytest.raises(ValueError, match="different responses"):
        join_frames([first, second])


def test_two_different_copies_of_one_frame_are_refused() -> None:
    with pytest.raises(ValueError, match="two different copies"):
        join_frames([Frame(1, 0, 1, b"a"), Frame(1, 0, 1, b"b")])


def test_nothing_to_join_is_an_error() -> None:
    with pytest.raises(ValueError, match="no frames"):
        join_frames([])
