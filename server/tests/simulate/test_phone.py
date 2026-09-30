from __future__ import annotations

from tests.conftest import OTHER_PHONE, PHONE
from textwire.clock import FakeClock
from textwire.protocol.compress import load_dictionary
from textwire.protocol.envelope import Envelope, Kind, pack_envelope
from textwire.protocol.frames import encode_frame, split_payload
from textwire.protocol.tags import SERVER_TAG_FIRST
from textwire.simulate.phone import Incomplete, Page, PlainReply, VirtualPhone
from textwire.transport.fake import FakeTransport


def phone(transport: FakeTransport, rounds: int = 1) -> VirtualPhone:
    return VirtualPhone(
        transport=transport,
        number=PHONE,
        dictionary=load_dictionary(),
        clock=FakeClock(),
        nak_after=0.01,
        nak_rounds=rounds,
    )


def texts(tag: int = 0) -> list[str]:
    envelope = Envelope(Kind.PAGE, 1, 1, "hello " * 60)
    payload = pack_envelope(envelope, load_dictionary())
    return [encode_frame(frame) for frame in split_payload(tag, payload)]


async def test_reordered_duplicate_frames_reassemble_and_wrong_recipients_are_ignored() -> None:
    transport = FakeTransport()
    client = phone(transport)
    # An uncompressed envelope ensures multiple frames without depending on dictionary ratio.
    payload = bytes((1, 0, 1, 1)) + b"x" * 200
    frames = [encode_frame(frame) for frame in split_payload(0, payload)]
    await transport.send(OTHER_PHONE, frames[0])
    await transport.send(PHONE, "corrupt")
    await transport.send(PHONE, texts(1)[0])
    for text in [frames[1], frames[1], frames[0]]:
        await transport.send(PHONE, text)
    outcome = await client.ask("h")
    assert isinstance(outcome, Page)
    assert outcome.envelope.text == "x" * 200
    assert outcome.frames == 2
    assert client.rejected == ["corrupt", texts(1)[0]]


async def test_plain_messages_reassemble_in_index_order() -> None:
    transport = FakeTransport()
    client = phone(transport)
    for text in ["[01 1/1] wrong tag", "[00 2/2] second", "[00 1/2] first"]:
        await transport.send(PHONE, text)
    assert await client.collect(0) == PlainReply(0, ("[00 1/2] first", "[00 2/2] second"))
    assert client.rejected == ["[01 1/1] wrong tag"]


async def test_silence_returns_incomplete_without_an_unbounded_resend_loop() -> None:
    transport = FakeTransport()
    client = phone(transport)
    assert await client.ask("h") == Incomplete(0, 0, None, ())
    assert client.sent == ["00 h"]


async def test_missing_frames_are_requested_once_then_reported() -> None:
    transport = FakeTransport()
    client = phone(transport)
    frames = split_payload(0, bytes(300))
    await transport.send(PHONE, encode_frame(frames[0]))
    assert await client.ask("h") == Incomplete(0, 1, 3, (1, 2))
    assert client.sent == ["00 h", "01 r 00 1-2"]


def test_tags_wrap_before_the_server_owned_range() -> None:
    client = phone(FakeTransport())
    assert [client.send("?") for _ in range(SERVER_TAG_FIRST + 1)][-2:] == [
        SERVER_TAG_FIRST - 1,
        0,
    ]
