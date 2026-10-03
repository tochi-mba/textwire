"""Frames: one single-segment SMS each (PROTOCOL.md section 2).

A frame is six header bytes and a body, written as SMS text in one of the alphabets of
:mod:`textwire.protocol.alphabets`: up to 114 body bytes in base64url, 121 in Z85G, both
inside 160 characters. Decoding checks the rules in a fixed order and reports the first one
broken by a stable reason code, which the vectors pin and the app shows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING

from textwire.protocol.alphabets import Alphabet, AlphabetError, decode_text, encode_bytes
from textwire.protocol.tags import TAG_COUNT

if TYPE_CHECKING:
    from collections.abc import Iterable

VERSION = 1
FRAME_CHARS = 160
HEADER_BYTES = 6
MAX_FRAMES = 255
#: The body size of the default alphabet, and the largest any alphabet allows.
BODY_BYTES = Alphabet.BASE64URL.frame_bytes - HEADER_BYTES
MAX_BODY_BYTES = max(alphabet.frame_bytes for alphabet in Alphabet) - HEADER_BYTES

_CRC_POLY = 0x07


def body_bytes(alphabet: Alphabet) -> int:
    """Payload bytes one frame carries in ``alphabet``."""
    return alphabet.frame_bytes - HEADER_BYTES


def max_payload(alphabet: Alphabet) -> int:
    """The largest payload 255 frames carry in ``alphabet``."""
    return MAX_FRAMES * body_bytes(alphabet)


class FrameType(IntEnum):
    """The low nibble of byte 0."""

    DATA = 1


class FrameFault(StrEnum):
    """Why a text is not a frame, in the order the checks run."""

    ENCODING = "encoding"
    LENGTH = "length"
    VERSION = "version"
    CRC = "crc"
    TYPE = "type"
    TAG = "tag"
    SEQUENCE = "sequence"


class FrameError(ValueError):
    """A received text is not a valid v1 frame."""

    def __init__(self, fault: FrameFault) -> None:
        super().__init__(fault.value)
        self.fault = fault


class PayloadTooLargeError(ValueError):
    """A payload needs more than 255 frames."""


class MissingFramesError(ValueError):
    """Some frames of a response have not arrived; ``missing`` lists their numbers."""

    def __init__(self, missing: list[int]) -> None:
        super().__init__("missing frames " + ",".join(str(seq) for seq in missing))
        self.missing = missing


@dataclass(frozen=True, slots=True)
class Frame:
    """One frame of a response."""

    tag: int
    seq: int
    total: int
    body: bytes
    type: FrameType = FrameType.DATA

    def __post_init__(self) -> None:
        if not 0 <= self.tag < TAG_COUNT:
            msg = f"tag {self.tag} is outside 0-{TAG_COUNT - 1}"
            raise ValueError(msg)
        if not 1 <= self.total <= MAX_FRAMES or not 0 <= self.seq < self.total:
            msg = f"frame {self.seq} of {self.total} is impossible"
            raise ValueError(msg)
        if len(self.body) > MAX_BODY_BYTES:
            msg = f"a body holds at most {MAX_BODY_BYTES} bytes, not {len(self.body)}"
            raise ValueError(msg)


def _crc_table() -> tuple[int, ...]:
    """The CRC of every single byte, so the checksum takes one lookup a byte, not eight steps."""
    table = []
    for byte in range(256):
        crc = byte
        for _ in range(8):
            crc = ((crc << 1) ^ _CRC_POLY) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        table.append(crc)
    return tuple(table)


_CRC_TABLE = _crc_table()


def crc8(data: bytes) -> int:
    """CRC-8/SMBUS: polynomial 0x07, initial 0x00, no reflection, no final XOR."""
    crc = 0
    for byte in data:
        crc = _CRC_TABLE[crc ^ byte]
    return crc


def encode_frame(frame: Frame, alphabet: Alphabet = Alphabet.BASE64URL) -> str:
    """The SMS text of ``frame`` in ``alphabet``."""
    if len(frame.body) > body_bytes(alphabet):
        msg = f"a {alphabet} frame holds at most {body_bytes(alphabet)} body bytes"
        raise ValueError(msg)
    header = bytes(
        (
            (VERSION << 4) | frame.type,
            frame.tag >> 8,
            frame.tag & 0xFF,
            frame.seq,
            frame.total,
        )
    )
    return encode_bytes(header + bytes((crc8(header + frame.body),)) + frame.body, alphabet)


def decode_frame(text: str) -> Frame:
    """The frame in an SMS text, or :class:`FrameError` naming the first rule it breaks."""
    try:
        data, alphabet = decode_text(text.strip())
    except AlphabetError as error:
        raise FrameError(FrameFault.ENCODING) from error
    if not HEADER_BYTES <= len(data) <= alphabet.frame_bytes:
        raise FrameError(FrameFault.LENGTH)
    if data[0] >> 4 != VERSION:
        raise FrameError(FrameFault.VERSION)
    body = data[HEADER_BYTES:]
    if crc8(data[:5] + body) != data[5]:
        raise FrameError(FrameFault.CRC)
    if data[0] & 0x0F not in set(FrameType):
        raise FrameError(FrameFault.TYPE)
    tag = (data[1] << 8) | data[2]
    if tag >= TAG_COUNT:
        raise FrameError(FrameFault.TAG)
    seq, total = data[3], data[4]
    if total == 0 or seq >= total:
        raise FrameError(FrameFault.SEQUENCE)
    return Frame(tag=tag, seq=seq, total=total, body=body, type=FrameType(data[0] & 0x0F))


def split_payload(tag: int, payload: bytes, alphabet: Alphabet = Alphabet.BASE64URL) -> list[Frame]:
    """Cut ``payload`` into as few frames as it needs in ``alphabet``, in order."""
    size = body_bytes(alphabet)
    if len(payload) > max_payload(alphabet):
        msg = f"{len(payload)} bytes need more than {MAX_FRAMES} frames"
        raise PayloadTooLargeError(msg)
    bodies = [payload[i : i + size] for i in range(0, len(payload), size)] or [b""]
    return [
        Frame(tag=tag, seq=seq, total=len(bodies), body=body) for seq, body in enumerate(bodies)
    ]


def join_frames(frames: Iterable[Frame]) -> bytes:
    """The payload a complete set of one response's frames carries, whatever their order.

    Duplicates with identical bodies are ignored. Raises :class:`MissingFramesError` when any
    frame is absent, and ``ValueError`` when the frames do not belong to one response or two
    copies of one frame disagree.
    """
    bodies: dict[int, bytes] = {}
    identity: tuple[int, int] | None = None
    for frame in frames:
        if identity is None:
            identity = (frame.tag, frame.total)
        elif (frame.tag, frame.total) != identity:
            msg = "frames from different responses"
            raise ValueError(msg)
        if bodies.setdefault(frame.seq, frame.body) != frame.body:
            msg = f"two different copies of frame {frame.seq}"
            raise ValueError(msg)
    if identity is None:
        msg = "no frames"
        raise ValueError(msg)
    missing = [seq for seq in range(identity[1]) if seq not in bodies]
    if missing:
        raise MissingFramesError(missing)
    return b"".join(bodies[seq] for seq in range(identity[1]))
