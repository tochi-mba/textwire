"""``textwire setup``: the guided walk to a working ``server/.env``, driven by scripted answers."""

from __future__ import annotations

import ctypes
import io
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from tests.conftest import REPO_ROOT
from textwire.cli import setup as wizard
from textwire.cli.main import main
from textwire.cli.setup import (
    BUY_NUMBER,
    SIGN_UP,
    UPGRADE,
    Check,
    Console,
    check_twilio,
    enable_colour,
    mask,
    read_env,
    run_setup,
    setup,
    write_env,
)

SID = "AC" + "0123456789abcdef" * 2
TOKEN = "fedcba9876543210" * 2
NUMBER = "+447700900000"
PHONE = "+447700900123"
API = f"https://api.twilio.com/2010-04-01/Accounts/{SID}"


class Script:
    """A terminal that answers from a list and remembers everything it was shown."""

    def __init__(self, *answers: str, opens: bool = True) -> None:
        self.answers = list(answers)
        self.opens = opens
        self.lines: list[str] = []
        self.prompts: list[str] = []
        self.secret_prompts: list[str] = []
        self.opened: list[str] = []

    def say(self, text: str = "") -> None:
        self.lines.append(text)

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answers.pop(0)

    def ask_secret(self, prompt: str) -> str:
        self.secret_prompts.append(prompt)
        return self.answers.pop(0)

    def open(self, url: str) -> bool:
        self.opened.append(url)
        return self.opens

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def plain(text: str, _code: str) -> str:
    return text


async def accepted(_sid: str, _token: str, _number: str) -> Check:
    return Check(["Twilio accepted the SID and token."], [], ["a note"])


async def trial(_sid: str, _token: str, _number: str) -> Check:
    return Check([], ["The account is still a trial."], [])


@pytest.fixture
def files(tmp_path: Path) -> tuple[Path, Path]:
    """A ``.env`` that does not exist yet, and the real example it starts from."""
    example = tmp_path / ".env.example"
    example.write_text(
        (REPO_ROOT / "server" / ".env.example").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path / ".env", example


#: Every step already done: the three console questions answered yes.
DONE = ("y", "y", "y")


def test_a_first_run_walks_through_every_step_and_writes_the_file(
    files: tuple[Path, Path],
) -> None:
    env, example = files
    term = Script(
        "n", "", "",  # no account: open sign-up (default yes), Enter when done
        "n", "n", "",  # not upgraded: do not open the link, Enter when done
        "y",  # the number is bought
        "abc", SID,  # a wrong SID is explained, then the right one
        "short", TOKEN,  # the same for the token, typed hidden
        "07700",  # too short to be a number
        "07700 900 000",  # the number as people write it
        "07700 900123",  # the phone allowed
    )  # fmt: skip
    assert run_setup(env, example, term, accepted, plain) == 0
    assert term.opened == [SIGN_UP]
    assert UPGRADE in term.text
    assert "An Account SID is AC followed by 32 letters and digits." in term.text
    assert "An Auth Token is 32 letters and digits." in term.text
    assert "Write it with the country code and no spaces, like +447700900123." in term.text
    assert len(term.secret_prompts) == 2
    assert TOKEN not in term.text
    assert "fedc...3210" in term.text
    assert "Twilio accepted the SID and token." in term.text
    assert f'cd /d "{env.parent}" && uv run python -m textwire serve' in term.text
    assert f"text  s! weather london  to {NUMBER}" in term.text
    saved = read_env(env)
    assert saved["TWILIO_ACCOUNT_SID"] == SID
    assert saved["TWILIO_AUTH_TOKEN"] == TOKEN
    assert saved["TWILIO_NUMBER"] == NUMBER
    assert saved["ALLOWED_NUMBERS"] == PHONE
    # Everything else the example says is still there, in its place.
    assert saved["DAILY_SEGMENT_BUDGET"] == "200"
    assert "# --- Transport" in env.read_text(encoding="utf-8")


def test_running_again_offers_every_saved_value_and_enter_keeps_it(
    files: tuple[Path, Path],
) -> None:
    env, example = files
    write_env(
        env,
        example,
        {
            "TWILIO_ACCOUNT_SID": SID,
            "TWILIO_AUTH_TOKEN": TOKEN,
            "TWILIO_NUMBER": NUMBER,
            "ALLOWED_NUMBERS": PHONE,
        },
    )
    term = Script(*DONE, "", "", "", "")
    assert run_setup(env, example, term, accepted, plain) == 0
    assert any(f"[Enter keeps {SID[:4]}...{SID[-4:]}]" not in p for p in term.prompts)
    assert any(f"[Enter keeps {SID}]" in p for p in term.prompts)
    assert any("[Enter keeps fedc...3210]" in p for p in term.secret_prompts)
    assert read_env(env)["TWILIO_AUTH_TOKEN"] == TOKEN


def test_a_number_outside_the_uk_is_questioned(files: tuple[Path, Path]) -> None:
    env, example = files
    term = Script(*DONE, SID, TOKEN, "+15551234567", "n", NUMBER, PHONE)
    assert run_setup(env, example, term, accepted, plain) == 0
    assert any("+15551234567 is not a UK mobile number" in p for p in term.prompts)
    assert read_env(env)["TWILIO_NUMBER"] == NUMBER
    term = Script(*DONE, "", "", "+15551234567", "y", "")
    assert run_setup(env, example, term, accepted, plain) == 0
    assert read_env(env)["TWILIO_NUMBER"] == "+15551234567"


def test_the_allowed_phones_are_checked_and_cannot_include_the_server(
    files: tuple[Path, Path],
) -> None:
    env, example = files
    term = Script(
        *DONE, SID, TOKEN, NUMBER, "", "+44 7700", f"{PHONE}, {NUMBER}", "07700900123, 07700900456"
    )
    assert run_setup(env, example, term, accepted, plain) == 0
    assert "At least one phone has to be allowed, or the server answers nobody." in term.text
    assert "+447700: write each with the country code" in term.text
    assert "The Twilio number cannot also be an allowed phone" in term.text
    assert read_env(env)["ALLOWED_NUMBERS"] == "+447700900123,+447700900456"


def test_a_problem_saves_nothing_unless_asked(files: tuple[Path, Path]) -> None:
    env, example = files
    term = Script(*DONE, SID, TOKEN, NUMBER, PHONE, "")
    assert run_setup(env, example, term, trial, plain) == 1
    assert not env.exists()
    assert "The account is still a trial." in term.text
    assert "Nothing was saved. Fix what is above and run this again." in term.text
    term = Script(*DONE, SID, TOKEN, NUMBER, PHONE, "y")
    assert run_setup(env, example, term, trial, plain) == 1
    assert read_env(env)["TWILIO_ACCOUNT_SID"] == SID
    assert "Next" not in term.lines


def test_a_browser_that_will_not_open_and_an_answer_that_is_not_yes_or_no(
    files: tuple[Path, Path],
) -> None:
    env, example = files
    term = Script("maybe", "n", "y", "", "y", "y", SID, TOKEN, NUMBER, PHONE, opens=False)
    assert run_setup(env, example, term, accepted, plain) == 0
    assert "Type y or n." in term.text
    assert "Could not open a browser; copy the link instead." in term.text


def test_the_number_step_lists_both_links(files: tuple[Path, Path]) -> None:
    env, example = files
    term = Script("y", "y", "n", "", "", SID, TOKEN, NUMBER, PHONE)
    assert run_setup(env, example, term, accepted, plain) == 0
    assert term.opened == [BUY_NUMBER]
    assert "regulatory-compliance/bundles" in term.text


def test_the_env_file_keeps_its_lines_and_gains_what_it_lacked(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\n# TEXTWIRE_TWILIO_NUMBER=\nOTHER=1\nTEXTWIRE_PORT=8140\n", "utf-8")
    write_env(env, tmp_path / "unused", {"TWILIO_NUMBER": NUMBER, "ALLOWED_NUMBERS": PHONE})
    assert env.read_bytes() == (
        b"# comment\nTEXTWIRE_TWILIO_NUMBER=+447700900000\nOTHER=1\nTEXTWIRE_PORT=8140\n"
        b"TEXTWIRE_ALLOWED_NUMBERS=+447700900123\n"
    )
    assert read_env(env) == {"TWILIO_NUMBER": NUMBER, "PORT": "8140", "ALLOWED_NUMBERS": PHONE}
    assert read_env(tmp_path / "missing") == {}


def test_a_secret_is_masked_to_its_ends() -> None:
    assert mask(TOKEN) == "fedc...3210"
    assert mask("12345678") == "********"
    assert mask("") == ""


def _api(account: dict[str, Any], numbers: list[dict[str, Any]]) -> None:
    respx.get(f"{API}.json").mock(return_value=httpx.Response(200, json=account))
    respx.get(f"{API}/IncomingPhoneNumbers.json").mock(
        return_value=httpx.Response(200, json={"incoming_phone_numbers": numbers})
    )


OWNED = [{"phone_number": NUMBER, "capabilities": {"sms": True}}]


@respx.mock
async def test_twilio_says_the_account_is_upgraded_and_the_number_is_its() -> None:
    _api({"friendly_name": "Tochi", "status": "active", "type": "Full"}, OWNED)
    result = await check_twilio(SID, TOKEN, NUMBER)
    assert result.problems == []
    assert result.warnings == []
    assert result.lines == [
        "Twilio accepted the SID and token (account 'Tochi').",
        "The account is upgraded, so texts go out unchanged.",
        f"{NUMBER} is on the account and can send and receive SMS.",
    ]


@pytest.mark.parametrize(
    ("account", "numbers", "said"),
    [
        ({"type": "Trial", "status": "active"}, OWNED, "The account is still a trial."),
        ({"type": "Full", "status": "suspended"}, OWNED, "The account is suspended, not active."),
        ({"type": "Full", "status": "active"}, [], f"{NUMBER} is not a number on this account."),
        (
            {"type": "Full", "status": "active"},
            [{"phone_number": NUMBER, "capabilities": {"sms": False}}],
            f"{NUMBER} cannot send or receive SMS.",
        ),
    ],
)
@respx.mock
async def test_twilio_names_what_will_not_work(
    account: dict[str, Any], numbers: list[dict[str, Any]], said: str
) -> None:
    _api(account, numbers)
    [problem] = (await check_twilio(SID, TOKEN, NUMBER)).problems
    assert problem.startswith(said)


@respx.mock
async def test_wrong_keys_are_a_problem_and_no_network_is_only_a_warning() -> None:
    route = respx.get(f"{API}.json")
    route.mock(return_value=httpx.Response(401, json={"message": "Authenticate", "code": 20003}))
    result = await check_twilio(SID, TOKEN, NUMBER)
    assert result.problems == ["Twilio did not accept that SID and token. Copy both again."]
    route.mock(side_effect=httpx.ConnectError("offline"))
    result = await check_twilio(SID, TOKEN, NUMBER)
    assert result.problems == []
    [warning] = result.warnings
    assert warning.startswith("Could not reach Twilio to check")


def test_the_console_paints_only_with_colour_and_never_crashes_on_a_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Console(colour=True).paint("hi", "1") == "\033[1mhi\033[0m"
    assert Console(colour=False).paint("hi", "1") == "hi"
    narrow = io.TextIOWrapper(io.BytesIO(), encoding="ascii", newline="\n")
    monkeypatch.setattr(sys, "stdout", narrow)
    Console(colour=False).say("\N{CHECK MARK} done")
    Console(colour=False).say()
    narrow.flush()
    assert narrow.buffer.getvalue() == b"? done\n\n"


def test_the_console_reads_answers_secrets_and_opens_links(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: f"typed after {prompt}")
    monkeypatch.setattr("getpass.getpass", lambda prompt: f"hidden after {prompt}")
    monkeypatch.setattr("webbrowser.open", lambda url: url == SIGN_UP)
    console = Console(colour=False)
    assert console.ask("? ") == "typed after ? "
    assert console.ask_secret("! ") == "hidden after ! "
    assert console.open(SIGN_UP)
    assert not console.open("nowhere")


def test_colour_is_on_only_for_a_console_that_shows_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(wizard, "enable_colour", lambda: True)
    assert Console().colour
    monkeypatch.setenv("NO_COLOR", "1")
    assert not Console().colour
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.delenv("NO_COLOR")
    assert not Console().colour


class _Kernel32:
    def __init__(self, *, console: bool) -> None:
        self.console = console
        self.set_to: int | None = None

    def GetStdHandle(self, which: int) -> int:  # noqa: N802 - the Windows API's name
        assert which == -11
        return 7

    def GetConsoleMode(self, handle: int, _mode: object) -> int:  # noqa: N802
        assert handle == 7
        return int(self.console)

    def SetConsoleMode(self, handle: int, mode: int) -> int:  # noqa: N802
        self.set_to = mode
        return 1


def test_windows_is_asked_for_colour_and_posix_has_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(ctypes, "windll", raising=False)
    assert enable_colour()
    kernel = _Kernel32(console=True)
    monkeypatch.setattr(ctypes, "windll", type("Windll", (), {"kernel32": kernel}), raising=False)
    assert enable_colour()
    assert kernel.set_to == 0x0004
    monkeypatch.setattr(
        ctypes, "windll", type("Windll", (), {"kernel32": _Kernel32(console=False)}), raising=False
    )
    assert not enable_colour()


def test_setup_uses_the_real_console_and_the_real_check_unless_given(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env, example = files
    answers = iter([*DONE, SID, NUMBER, PHONE])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: TOKEN)
    monkeypatch.setattr(wizard, "check_twilio", accepted)
    assert setup(env, example) == 0
    assert read_env(env)["TWILIO_AUTH_TOKEN"] == TOKEN
    answers = iter([*DONE, "", "", "", ""])  # the last declines saving after the problem
    assert setup(env, example, Console(colour=False), trial) == 1


def test_the_command_finds_the_server_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, Path]] = []

    def fake(env: Path, example: Path) -> int:
        calls.append((env, example))
        return 0

    monkeypatch.setattr("textwire.cli.main.setup", fake)
    assert main(["setup", "--root", str(tmp_path)]) == 0
    monkeypatch.chdir(REPO_ROOT / "server")
    assert main(["setup"]) == 0
    assert calls == [
        (tmp_path / "server" / ".env", tmp_path / "server" / ".env.example"),
        (REPO_ROOT / "server" / ".env", REPO_ROOT / "server" / ".env.example"),
    ]
