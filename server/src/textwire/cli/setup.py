"""``textwire setup``: a guided walk from no Twilio account to a working ``server/.env``.

It says what to get and where, with links it can open, asks for each value (the auth token
without echoing it), checks every value as it is typed, asks Twilio whether the account and
number will work, and writes the four settings into ``server/.env``, keeping every other line.
Run it again at any time: what is already set is offered back, and Enter keeps it.
"""

from __future__ import annotations

import asyncio
import ctypes
import getpass
import os
import re
import sys
import webbrowser
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from textwire.config import E164
from textwire.transport.base import TransportError
from textwire.transport.twilio import TwilioClient

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from pathlib import Path

    import httpx

SIGN_UP = "https://www.twilio.com/try-twilio"
UPGRADE = "https://console.twilio.com/us1/billing/manage-billing/billing-overview"
BUY_NUMBER = "https://console.twilio.com/us1/develop/phone-numbers/manage/search"
BUNDLES = "https://console.twilio.com/us1/develop/phone-numbers/regulatory-compliance/bundles"
ACCOUNT_INFO = "https://console.twilio.com/"
PRICING = "https://www.twilio.com/en-us/sms/pricing/gb"

_SID = re.compile(r"AC[0-9a-f]{32}")
_TOKEN = re.compile(r"[0-9a-f]{32}")
_UK_MOBILE = re.compile(r"\+447\d{9}")
_KEYS = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_NUMBER", "ALLOWED_NUMBERS")
TICK = "\N{CHECK MARK}"
CROSS = "\N{BALLOT X}"


class Terminal(Protocol):
    """Where the wizard talks: a real console, or a script of answers in the tests."""

    def say(self, text: str = "") -> None:
        """Print one line."""

    def ask(self, prompt: str) -> str:
        """Read one answer."""

    def ask_secret(self, prompt: str) -> str:
        """Read one answer without echoing it."""

    def open(self, url: str) -> bool:
        """Open a link in the browser; whether it opened."""


def enable_colour() -> bool:
    """Turn on colour where the console understands it. Windows needs asking; POSIX does not."""
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return True
    kernel32 = windll.kernel32
    handle = kernel32.GetStdHandle(-11)  # the standard output
    mode = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return False
    return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))  # virtual terminal


class Console:
    """The real terminal: colour when it is a console that shows it, plain text otherwise."""

    def __init__(self, *, colour: bool | None = None) -> None:
        """Decide on colour once: ``NO_COLOR`` and redirected output switch it off."""
        if colour is None:
            colour = sys.stdout.isatty() and "NO_COLOR" not in os.environ and enable_colour()
        self.colour = colour

    def paint(self, text: str, code: str) -> str:
        """``text`` in an ANSI style when colour is on."""
        return f"\033[{code}m{text}\033[0m" if self.colour else text

    def say(self, text: str = "") -> None:
        """Print one line; a character the console cannot show becomes ``?`` rather than a crash."""
        encoding = sys.stdout.encoding or "utf-8"
        print(text.encode(encoding, "replace").decode(encoding))

    def ask(self, prompt: str) -> str:
        """Read one answer."""
        return input(prompt)

    def ask_secret(self, prompt: str) -> str:
        """Read one answer without echoing it."""
        return getpass.getpass(prompt)

    def open(self, url: str) -> bool:
        """Open a link in the default browser."""
        return webbrowser.open(url)


@dataclass(frozen=True)
class Check:
    """What Twilio said about the values: problems stop the setup, warnings do not."""

    lines: list[str]
    problems: list[str]
    warnings: list[str]


async def check_twilio(
    sid: str,
    token: str,
    number: str,
    *,
    base_url: str = "https://api.twilio.com",
    transport: httpx.AsyncBaseTransport | None = None,
) -> Check:
    """Ask Twilio whether the SID and token work, the account is upgraded and the number is its."""
    client = TwilioClient(
        account_sid=sid,
        auth_token=token,
        base_url=base_url,
        transport=transport,
        timeout_seconds=15,
    )
    lines: list[str] = []
    problems: list[str] = []
    warnings: list[str] = []
    try:
        account = await client.account()
        lines.append(f"Twilio accepted the SID and token (account '{account.name}').")
        if account.type.lower() == "trial":
            problems.append(
                "The account is still a trial. Twilio adds 'Sent from a Twilio trial account'"
                f" to every SMS, which breaks every page. Upgrade it: {UPGRADE}"
            )
        elif account.status and account.status != "active":
            problems.append(f"The account is {account.status}, not active.")
        else:
            lines.append("The account is upgraded, so texts go out unchanged.")
        owned = await client.number(number)
        if owned is None:
            problems.append(
                f"{number} is not a number on this account. Buy one or check it: {BUY_NUMBER}"
            )
        elif not owned.sms:
            problems.append(f"{number} cannot send or receive SMS. Buy an SMS mobile number.")
        else:
            lines.append(f"{number} is on the account and can send and receive SMS.")
    except TransportError as error:
        if "401" in str(error) or "403" in str(error):
            problems.append("Twilio did not accept that SID and token. Copy both again.")
        else:
            warnings.append(f"Could not reach Twilio to check ({error}). The values were kept.")
    finally:
        await client.aclose()
    return Check(lines, problems, warnings)


type Checker = Callable[[str, str, str], Coroutine[None, None, Check]]


def read_env(path: Path) -> dict[str, str]:
    """The ``TEXTWIRE_`` settings in a ``.env`` file, by name without the prefix."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key.startswith("TEXTWIRE_"):
            values[key.removeprefix("TEXTWIRE_")] = value.strip()
    return values


def write_env(path: Path, example: Path, values: dict[str, str]) -> None:
    """Set ``values`` in ``path``, starting from ``example`` if it does not exist yet.

    Each setting replaces its line, commented out or not, so the file keeps its comments,
    order and every other setting. A setting the file does not mention is added at the end.
    """
    text = path.read_text(encoding="utf-8") if path.is_file() else example.read_text("utf-8")
    lines = text.splitlines()
    for name, value in values.items():
        pattern = re.compile(rf"^\s*#?\s*TEXTWIRE_{name}=")
        for index, line in enumerate(lines):
            if pattern.match(line):
                lines[index] = f"TEXTWIRE_{name}={value}"
                break
        else:
            lines.append(f"TEXTWIRE_{name}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def mask(value: str, keep: int = 4) -> str:
    """``AC1234...cdef``: enough to recognise, not enough to use."""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]}"


class Wizard:
    """The conversation, step by step. Each step can be skipped by someone who has done it."""

    def __init__(self, term: Terminal, paint: Callable[[str, str], str]) -> None:
        """Talk through ``term``, styling with ``paint`` (identity when colour is off)."""
        self.term = term
        self.paint = paint

    def title(self, text: str) -> None:
        """A step's heading."""
        self.term.say()
        self.term.say(self.paint(text, "1;38;5;191"))

    def note(self, text: str) -> None:
        """A muted explanation."""
        self.term.say(self.paint(f"  {text}", "38;5;246"))

    def good(self, text: str) -> None:
        """Something that worked."""
        self.term.say(self.paint(f"  {TICK} {text}", "32"))

    def bad(self, text: str) -> None:
        """Something that needs fixing."""
        self.term.say(self.paint(f"  {CROSS} {text}", "31"))

    def link(self, label: str, url: str) -> None:
        """A link, underlined, on its own line so a terminal can make it clickable."""
        self.term.say(f"  {label}: {self.paint(url, '4;38;5;191')}")

    def yes(self, question: str, *, default: bool) -> bool:
        """A yes or no answer; Enter takes the default."""
        hint = "Y/n" if default else "y/N"
        while True:
            answer = self.term.ask(f"  {question} [{hint}] ").strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self.note("Type y or n.")

    def offer(self, question: str, explain: list[str], links: list[tuple[str, str]]) -> None:
        """A thing to have done in the Twilio console: skip it, or be walked through it."""
        if self.yes(question, default=False):
            return
        for line in explain:
            self.note(line)
        for label, url in links:
            self.link(label, url)
        if self.yes("Open the first link in your browser?", default=True) and not self.term.open(
            links[0][1]
        ):
            self.note("Could not open a browser; copy the link instead.")
        self.term.ask("  Press Enter when it is done. ")

    def value(
        self,
        prompt: str,
        current: str,
        valid: Callable[[str], str | None],
        *,
        secret: bool = False,
        clean: Callable[[str], str] = str.strip,
    ) -> str:
        """Ask until the answer is valid; Enter keeps ``current`` when there is one."""
        shown = mask(current) if secret else current
        suffix = f" [Enter keeps {shown}]" if current else ""
        while True:
            ask = self.term.ask_secret if secret else self.term.ask
            answer = clean(ask(f"  {prompt}{suffix}: "))
            if not answer and current:
                return current
            problem = valid(answer)
            if problem is None:
                return answer
            self.bad(problem)


def _sid_problem(value: str) -> str | None:
    return (
        None if _SID.fullmatch(value) else "An Account SID is AC followed by 32 letters and digits."
    )


def _token_problem(value: str) -> str | None:
    return None if _TOKEN.fullmatch(value) else "An Auth Token is 32 letters and digits."


def _number_problem(value: str) -> str | None:
    if E164.fullmatch(value):
        return None
    return "Write it with the country code and no spaces, like +447700900123."


def _numbers_problem(value: str) -> str | None:
    numbers = [part.strip() for part in value.split(",") if part.strip()]
    if not numbers:
        return "At least one phone has to be allowed, or the server answers nobody."
    wrong = [number for number in numbers if not E164.fullmatch(number)]
    if wrong:
        return f"{', '.join(wrong)}: write each with the country code, like +447700900123."
    return None


def _phone(value: str) -> str:
    """A number as typed, without the spaces, dashes and brackets people put in."""
    cleaned = re.sub(r"[\s\-()]", "", value)
    return "+44" + cleaned[1:] if cleaned.startswith("07") else cleaned


def _phones(value: str) -> str:
    return ",".join(_phone(part) for part in value.split(",") if part.strip())


def run_setup(
    env: Path, example: Path, term: Terminal, check: Checker, paint: Callable[[str, str], str]
) -> int:
    """The whole setup; 0 when ``env`` was written with values Twilio accepted."""
    wizard = Wizard(term, paint)
    current = read_env(env)
    term.say(
        paint("textwire setup", "1;38;5;191")
        + paint(" - connect the server to a number", "38;5;246")
    )
    wizard.note(
        "Five steps. Anything already done can be skipped, and nothing is saved until the end."
    )
    wizard.note(f"Prices for UK texts: {PRICING}")

    wizard.title("1 of 5  A Twilio account")
    wizard.offer(
        "Do you already have a Twilio account?",
        ["Twilio owns the number your phone texts. Sign up with your email; it is free to start."],
        [("Sign up", SIGN_UP)],
    )

    wizard.title("2 of 5  Upgrade it")
    wizard.offer(
        "Is the account upgraded (a card added, not a trial)?",
        [
            "A trial account adds 'Sent from a Twilio trial account' to every SMS it sends,",
            "which breaks every page. Add a card and about $20 of credit to upgrade.",
        ],
        [("Billing", UPGRADE)],
    )

    wizard.title("3 of 5  A UK mobile number")
    wizard.offer(
        "Have you bought a UK mobile number on it?",
        [
            "Search country United Kingdom, type Mobile, capability SMS: a +44 7 number, about",
            "$2.50 a month. Only a mobile number is inside your phone's unlimited texts.",
            "If Twilio asks for a regulatory bundle (proof of address), complete it.",
            "Leave the number's messaging webhook empty: the server checks for texts itself.",
        ],
        [("Buy a number", BUY_NUMBER), ("Regulatory bundles", BUNDLES)],
    )

    wizard.title("4 of 5  The account's keys and the number")
    wizard.note("All three are on the console's home page, under Account Info.")
    wizard.link("Console", ACCOUNT_INFO)
    sid = wizard.value("Account SID", current.get("TWILIO_ACCOUNT_SID", ""), _sid_problem)
    wizard.note(
        "The token stays hidden: nothing shows while you paste or type it. Then press Enter."
    )
    token = wizard.value(
        "Auth Token (hidden as you type)",
        current.get("TWILIO_AUTH_TOKEN", ""),
        _token_problem,
        secret=True,
    )
    number = wizard.value(
        "The Twilio number", current.get("TWILIO_NUMBER", ""), _number_problem, clean=_phone
    )
    if not _UK_MOBILE.fullmatch(number) and not wizard.yes(
        f"{number} is not a UK mobile number (+44 7...). Use it anyway?", default=False
    ):
        number = wizard.value("The Twilio number", "", _number_problem, clean=_phone)

    wizard.title("5 of 5  The phones that may use it")
    wizard.note(
        "Your S21's own number. Separate more than one with commas; everyone else is ignored."
    )
    allowed = wizard.value(
        "Allowed phones", current.get("ALLOWED_NUMBERS", ""), _numbers_problem, clean=_phones
    )
    if number in allowed.split(","):
        wizard.bad("The Twilio number cannot also be an allowed phone: it would answer itself.")
        allowed = wizard.value("Allowed phones", "", _numbers_problem, clean=_phones)

    wizard.title("Checking with Twilio")
    result = asyncio.run(check(sid, token, number))
    for line in result.lines:
        wizard.good(line)
    for line in result.warnings:
        wizard.note(line)
    for line in result.problems:
        wizard.bad(line)

    values = dict(zip(_KEYS, (sid, token, number, allowed), strict=True))
    if result.problems and not wizard.yes("Save these values anyway, to fix later?", default=False):
        term.say()
        wizard.note("Nothing was saved. Fix what is above and run this again.")
        return 1
    write_env(env, example, values)

    wizard.title("Saved")
    wizard.note(f"{env}")
    for name, value in values.items():
        shown = mask(value) if name == "TWILIO_AUTH_TOKEN" else value
        term.say(f"  TEXTWIRE_{name:<20} {shown}")
    if result.problems:
        return 1
    wizard.title("Next")
    start = f'cd /d "{env.parent}" && uv run python -m textwire serve'
    term.say("  Start the server:      " + paint(start, "1"))
    term.say("  Its dashboard:         " + paint("http://127.0.0.1:8140/", "4;38;5;191"))
    term.say(f"  Then, from your phone, text  s! weather london  to {number}")
    wizard.note("The ! asks for a readable reply, so it works before the app is installed.")
    return 0


def setup(
    env: Path, example: Path, term: Console | None = None, check: Checker | None = None
) -> int:
    """``textwire setup`` against ``env``, through the real console unless told otherwise."""
    console = term if term is not None else Console()
    return run_setup(env, example, console, check or check_twilio, console.paint)
