# Onboarding

From a clean machine to a green `make check` and a page on the screen, in about an hour.
Every step is safe to repeat. If a step does not match what you see, that is a bug in this
page: fix it in the same pull request as whatever you came to do.

- [1. Install the tools](#1-install-the-tools)
- [2. Clone and check the machine](#2-clone-and-check-the-machine)
- [3. Run every gate](#3-run-every-gate)
- [4. See it work without a phone](#4-see-it-work-without-a-phone)
- [5. Read the map](#5-read-the-map)
- [6. Make a first change](#6-make-a-first-change)
- [7. Put it on a phone](#7-put-it-on-a-phone)
- [8. Daily workflow](#8-daily-workflow)

## 1. Install the tools

| Tool | Why | Check | Install (Windows) | Install (macOS / Linux) |
| --- | --- | --- | --- | --- |
| Git | the repository | `git --version` | `winget install Git.Git` | package manager |
| GNU Make | the task runner | `make --version` | `winget install ezwinports.make` | preinstalled / `apt install make` |
| uv | Python and the server's dependencies | `uv --version` | `winget install astral-sh.uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python 3.12+ | the server | `uv python list --only-installed` | `uv python install 3.12` | `uv python install 3.12` |
| JDK 17 | the Android build | `java -version` | `winget install EclipseAdoptium.Temurin.17.JDK` | `sdk install java 17-tem` |
| Android SDK platform 36 | the Android build | `echo $ANDROID_HOME` | Android command-line tools, then `sdkmanager "platforms;android-36" "build-tools;36.0.0"` | same |
| adb | installing the app on a phone | `adb version` | comes with platform-tools | same |

On Windows run everything from Git Bash; the Makefiles and `tools/doctor.sh` are POSIX
shell. The JDK and Android SDK are only needed for the Android half; without them
`make check` skips it locally and says so (CI never skips). Android Studio is not required:
the Gradle wrapper builds everything from the command line.

## 2. Clone and check the machine

```sh
git clone https://github.com/tochi-mba/textwire.git
cd textwire
make doctor
```

`make doctor` prints one line per requirement, `ok`, `warn` or `fail`, with the fix for each.
`warn` on the Twilio transport is normal: nothing here needs an account.

## 3. Run every gate

```sh
make install     # the server's virtualenv (uv sync)
make check       # server: ruff, mypy strict, import contracts, tests at 100% branch coverage
                 # vectors: the committed golden vectors match the reference
                 # android: ktlint, unit tests, coverage floors (skipped without a JDK)
```

The first server run takes about two minutes (it includes property tests); the first Android
run downloads Gradle and the SDK pieces and takes a few minutes more. Both are much faster
after that.

## 4. See it work without a phone

```sh
make simulate
```

That starts the real server and a virtual phone in your terminal, talking over an in-memory
SMS transport, with recorded pages. Type what you would text:

```
> s bbc weather london          five results, each a chip you can follow
> l 1                           follow result 1 (page 1 of it)
> n                             the next page
> b                             back a page
> g dunmore-gazette.example/news/text-only-library
> s! bbc weather london         the same search as readable plain SMS
> ?                             today's usage and cost
> help                          the simulator's own commands
> q
```

Each reply ends with a line like `-- page 1/2 | 4 SMS | 0.1 s | reply a7`: that is what the
request would have cost. To watch a lost frame get recovered:

```sh
cd server
uv run python -m textwire simulate --offline --drop 3 --nak 1 -c "g dunmore-gazette.example/news/text-only-library"
```

Drop `--offline` to fetch real pages and run real searches; still no SMS is sent.

## 5. Read the map

Thirty minutes, in this order:

1. [ARCHITECTURE.md](ARCHITECTURE.md): how a request becomes a page on the phone, and
   which module owns which step.
2. [../protocol/PROTOCOL.md](../protocol/PROTOCOL.md): the wire format. Sections 2, 4 and 6
   are the ones you will touch.
3. [../AGENTS.md](../AGENTS.md): the invariants every change keeps.
4. [TESTING.md](TESTING.md): the layers, the fakes, and how the golden vectors work.
5. [GLOSSARY.md](GLOSSARY.md) when a word is used in a way you did not expect, and
   [FAQ.md](FAQ.md) for the questions everyone asks in the first week.
6. [OPTIMISATION.md](OPTIMISATION.md) if you want to know why every byte is where it is.

## 6. Make a first change

A small, real change that touches every layer: add a status reason.

1. `git switch -c first-change`.
2. In `server/src/textwire/service/handler.py`, find where `E link range` is produced.
   Suppose a new reason `E link empty` for a document with no links at all.
3. Write the test first in `server/tests/service/test_handler.py`, using `build_rig` and
   `rig.ask(...)`; run it with `uv run python -P -m pytest tests/service/test_handler.py -k empty -q`
   and watch it fail.
4. Make it pass. Run `make -C server check`: coverage must stay at 100%.
5. Add the reason to the table in `protocol/PROTOCOL.md` section 9.6.
6. If you changed anything on the wire (you did not, this time), `make vectors` and commit
   the diff.
7. Add a line under `Unreleased` in `CHANGELOG.md`, push, open a pull request. `ci-ok` is
   the one check that has to be green.

[../CONTRIBUTING.md](../CONTRIBUTING.md) has the commit and pull-request conventions.

## 7. Put it on a phone

Only when you have an Android phone and a Twilio number to talk to; the simulator covers
everything else. See [OPERATIONS.md](OPERATIONS.md) for the server side.

```sh
make android-apk                 # dist/textwire-debug.apk
make android-install             # adb install -r onto the phone adb sees
```

On Android 15, a sideloaded app's SMS permissions are a "restricted setting": if the grant
dialog does not appear, open App info, the three-dot menu, "Allow restricted settings", then
grant SMS. On Samsung One UI also exclude the app from battery optimisation (Settings,
Battery, Background usage limits, Never sleeping apps) so frames are received while the app
is in the background. Mute the server's number in the messaging app: frames show up there
too (ADR-0011).

Line by line, [ACCEPTANCE.md](ACCEPTANCE.md) is the checklist a change to the app or the
protocol is tested against on the device.

## 8. Daily workflow

```sh
make check                                   # before every push
cd server && uv run python -P -m pytest tests/protocol -q     # a slice while you work
cd server && uv run ruff format . && uv run ruff check --fix .  # tidy
cd android && ./gradlew ktlintFormat         # tidy Kotlin
make vectors                                 # after any wire-format change; commit the diff
```

Run the full server suite in the background on Windows and keep working; and never edit a
source file while a coverage run is measuring it. See [TESTING.md](TESTING.md).
