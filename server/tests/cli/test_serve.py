from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from tests.conftest import PHONE, SERVER, build_settings
from tests.service.conftest import memory_store
from textwire.cli.main import main
from textwire.cli.serve import (
    PROBE_TAG,
    ConfigurationError,
    build_transport,
    probe,
    probe_frame,
    serve,
)
from textwire.clock import FakeClock
from textwire.config import TransportKind
from textwire.protocol.alphabets import Alphabet
from textwire.protocol.frames import body_bytes, decode_frame
from textwire.transport.twilio import TwilioTransport

SID = "AC" + "0" * 32
BASE = f"https://api.twilio.com/2010-04-01/Accounts/{SID}"


def test_the_transport_is_built_from_complete_settings(clock: FakeClock) -> None:
    transport = build_transport(build_settings(), memory_store(), clock)
    assert isinstance(transport, TwilioTransport)
    assert transport.number == SERVER


def test_missing_settings_are_a_configuration_error(clock: FakeClock) -> None:
    with pytest.raises(ConfigurationError, match="TEXTWIRE_TWILIO_NUMBER is not set"):
        build_transport(build_settings(twilio_number=""), memory_store(), clock)


def test_the_gateway_transport_is_not_built_yet(clock: FakeClock) -> None:
    settings = build_settings(
        transport=TransportKind.GATEWAY,
        gateway_url="http://192.0.2.10:8080",
        gateway_username="u",
        gateway_password="p",
    )
    with pytest.raises(ConfigurationError, match="not built yet"):
        build_transport(settings, memory_store(), clock)


@pytest.mark.parametrize("alphabet", list(Alphabet))
def test_the_probe_frame_fills_a_whole_sms_with_varied_bytes(alphabet: Alphabet) -> None:
    text = probe_frame(build_settings(frame_alphabet=alphabet))
    assert len(text) == 160
    frame = decode_frame(text)
    assert frame.tag == PROBE_TAG
    assert len(frame.body) == body_bytes(alphabet)
    assert len(set(frame.body)) > 100


@respx.mock
async def test_probe_sends_one_frame_and_prints_it(capsys: pytest.CaptureFixture[str]) -> None:
    route = respx.post(f"{BASE}/Messages.json").mock(
        return_value=httpx.Response(201, json={"sid": "SM9", "date_created": "", "date_sent": None})
    )
    assert await probe(PHONE, build_settings()) == 0
    out = capsys.readouterr().out
    assert "sent probe SM9 to +44...0123 (160 characters)" in out
    assert route.called


async def test_probe_refuses_incomplete_settings(capsys: pytest.CaptureFixture[str]) -> None:
    assert await probe(PHONE, build_settings(twilio_account_sid="")) == 2
    assert "cannot probe: TEXTWIRE_TWILIO_ACCOUNT_SID is not set" in capsys.readouterr().out


async def test_serve_refuses_incomplete_settings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await serve(build_settings(data_dir=tmp_path, allowed_numbers=())) == 2
    assert "cannot start" in capsys.readouterr().out


@respx.mock
async def test_serve_runs_until_stopped(tmp_path: Path) -> None:
    respx.get(f"{BASE}/Messages.json").mock(
        return_value=httpx.Response(200, json={"messages": [], "next_page_uri": None})
    )
    stop = asyncio.Event()
    settings = build_settings(data_dir=tmp_path, poll_seconds=0.01, status_interval_seconds=0.01)
    task = asyncio.create_task(serve(settings, stop))
    await asyncio.sleep(0.05)
    stop.set()
    assert await task == 0
    assert (tmp_path / "textwire.db").exists()


def test_the_cli_exposes_serve_and_probe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["serve"]) == 2
    assert main(["probe", PHONE]) == 2
