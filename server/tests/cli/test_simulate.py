from __future__ import annotations

import pytest

from tests.conftest import build_settings
from textwire.cli.main import main
from textwire.cli.simulate import _terminal_input, scripted, simulate, simulator_settings
from textwire.simulate.session import PHONE_NUMBER


def test_cli_offline_script_runs_to_completion(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["simulate", "--offline", "-c", "?", "-c", "q"]) == 0
    assert "sms" in capsys.readouterr().out


def test_cli_parses_loss_and_page_size_controls(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "simulate",
                "--offline",
                "--drop",
                "1, 2",
                "--page-frames",
                "2",
                "--nak",
                "0.01",
                "-c",
                "help",
            ]
        )
        == 0
    )
    assert "Commands" in capsys.readouterr().out


def test_simulator_settings_preserve_operator_budget() -> None:
    settings = simulator_settings(build_settings(daily_segment_budget=7), drop=(2,), page_frames=50)
    assert settings.allowed_numbers == (PHONE_NUMBER,)
    assert settings.debug_drop_once == (2,)
    assert settings.page_frames == settings.max_page_frames == 50
    assert settings.daily_segment_budget == 7


async def test_scripted_reader_echoes_then_reaches_eof() -> None:
    output: list[str] = []
    read = scripted(["help"], output.append)
    assert await read("> ") == "help"
    assert await read("> ") is None
    assert output == ["> help"]


async def test_terminal_reader_returns_input_and_handles_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def answer(prompt: str) -> str:
        assert prompt == "> "
        return "help"

    monkeypatch.setattr("builtins.input", answer)
    assert await _terminal_input("> ") == "help"

    def eof(prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert await _terminal_input("> ") is None


@pytest.mark.parametrize("offline", [True, False])
async def test_simulation_accepts_a_reader_without_fetching_any_network(offline: bool) -> None:
    async def quit_now(prompt: str) -> str:
        return "q"

    output: list[str] = []
    assert await simulate(offline=offline, read=quit_now, write=output.append) == 0
    assert "simulator" in output[-1]
