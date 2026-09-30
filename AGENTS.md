# AGENTS.md

Rules for everyone who changes this repository, people and coding agents alike. Read this
before your first change. [CONTRIBUTING.md](CONTRIBUTING.md) covers the workflow and
[docs/ONBOARDING.md](docs/ONBOARDING.md) covers setting up a machine.

## What textwire is

A text-mode web for a phone with no data connection. The phone sends a request as an SMS to
a number the server owns. The server fetches the page or runs the search on the real
internet, reduces it to text, compresses it, and sends it back as numbered SMS frames that
the Android app reassembles and renders. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) has
the full picture and [protocol/PROTOCOL.md](protocol/PROTOCOL.md) has the wire format.

## Layout

| Path | What lives there |
| --- | --- |
| `protocol/` | The language-neutral contract: `PROTOCOL.md`, golden vectors, the zstd dictionary, shared fixtures. |
| `server/` | The Python server: protocol reference implementation, content pipeline, transports, dispatcher, simulator, CLI. |
| `android/` | The Kotlin app: `:protocol` and `:core` (pure JVM) and `:app` (Android, Compose). |
| `docs/` | Onboarding, architecture, operations, testing, acceptance and the ADRs. |

## Commands

| Command | What it does |
| --- | --- |
| `make doctor` | Checks this machine for every tool the repository needs and says how to fix what is missing. |
| `make check` | Everything CI runs: server gates, vector drift, Android gates. |
| `make simulate` | Runs the whole system in the terminal with a virtual phone and recorded pages. No Twilio, no phone. |
| `make -C server check` | Server only: ruff, mypy strict, import contracts, tests at 100% branch coverage. |
| `make vectors` | Regenerates the golden vectors from the Python reference. |
| `cd android && ./gradlew check` | Android only: ktlint, unit tests, coverage floors. |

## Invariants

1. **Honesty about hardware.** Never claim a result on a real phone or a real Twilio number
   that was not observed. Device and network claims live only in
   [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md), each with a date and a cost.
2. **The wire format is a contract.** A change to frames, requests, envelopes, codecs or
   the dictionary regenerates the vectors (`make vectors`), edits `protocol/PROTOCOL.md`, and
   passes both languages' vector tests in the same pull request.
3. **No test sends a real SMS** unless it is marked `live`. `make check` passes with no
   network, no Twilio account and no phone.
4. **Every seam that touches the outside world is an interface with a hand-written fake**:
   `Transport`, `Fetcher`, `SearchProvider`, `Clock` on the server; `SmsGateway`, `Clock`
   and the stores on the phone. No mocking libraries on the server.
5. **Secrets come from the environment only.** `server/.env` is gitignored. Logs never carry
   an auth token and show phone numbers masked (`+44...1234`).
6. **Coverage floors are never lowered.** The server and the Kotlin `:protocol` and `:core`
   modules are held at 100% line and branch coverage. `pragma: no cover` fails review and a
   test.
7. **Money is an operator setting.** Never raise `TEXTWIRE_DAILY_SEGMENT_BUDGET` or the page
   size defaults in code to make something pass. Every outbound SMS is charged to the budget
   before it is sent.
8. **Files stay under 800 lines.** A test enforces it for Python; review enforces it for
   Kotlin.
9. **The Android app stays small**: no dependency-injection framework, no serialization
   library, no HTTP client. It never touches the network.
10. **Run the full test suites in the background** while you work and never edit source
    while coverage is being measured: coverage reports stale line numbers against the edited
    file.

## Where to put things

- A new request verb: `server/src/textwire/protocol/requests.py`, the handler, the Kotlin
  `RequestFormat`, the vectors, `PROTOCOL.md`, and the help text.
- A new error: a stable `E <area> <detail>` string in the handler, listed in `PROTOCOL.md`.
- A new transport: implement `textwire.transport.base.Transport`, add a fake-backed contract
  test, and document it in [docs/OPERATIONS.md](docs/OPERATIONS.md).
- A decision that someone could reasonably have made differently: an ADR in `docs/adr/`.
