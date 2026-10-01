# Testing

textwire is tested in layers. Each layer proves one kind of thing, runs in one place, and
has one way to add to it. The rule behind all of them: `make check` passes with no network,
no Twilio account and no phone, and anything that needs those is marked and run by hand.

| Layer | Where | Runs in | Proves |
| --- | --- | --- | --- |
| Unit | `server/tests/**`, `android/*/src/test/**` | `make check`, CI | Each module does what its docstring says, at 100% line and branch coverage on the server, the pure-Kotlin modules and the app's logic (ADR-0009). |
| Property | the `hypothesis` tests among the unit tests | `make check`, CI | Round trips hold for every input: frames, alphabets, envelopes, requests, pagination, plain splitting, GSM-7 sanitising. |
| Golden vectors | `protocol/vectors/`, `server/tests/vectors/`, `android/protocol/src/test/` | `make check`, CI | Python and Kotlin agree on every byte of the wire format, and the committed files match the reference (`make vectors-check`). |
| End to end, in process | `server/tests/simulate/`, `server/tests/service/test_dispatcher.py` | `make check`, CI | The real server, the real pipeline and the virtual phone agree over the fake transport: searches, pages, links, plain mode, dropped frames and resends, both alphabets. |
| Contract | `server/tests/transport/test_twilio.py` | `make check`, CI | The Twilio client sends the right requests and reads the fields the server depends on, against recorded response shapes. |
| Repository rules | `server/tests/test_repo_rules.py` | `make check`, CI | File sizes, no coverage pragmas, versions agree, every ADR is indexed, every internal link in the docs resolves. |
| Screens | `android/app/src/test/**/ui/UiTest.kt` | `make check`, CI | Every screen of the app does what a person expects, at the Galaxy S21 Ultra's screen size and again on a small phone, where every control must still be reachable. |
| Browser scripts | `server/tests/js/`, run by `server/tests/test_javascript.py` | `make check`, CI | The dashboard's script and the site's `app.js`, run in Node against a stand-in page: what a phone texted is escaped, the budget bar, the probe form, the menu, the Copy buttons. |
| The site | `server/tests/test_check_site.py`, `server/tests/test_site.py` | `make check`, CI | The landing page has no broken anchor, link, asset or Copy button and no draft text; the handbook builds strictly; every link from one into the other resolves. |
| Live | `server/tests/live/` (marker `live`) | by hand, `make -C server test-live` | One real SMS reaches a real phone through a real account. Costs money; never in CI. |
| Device acceptance | [ACCEPTANCE.md](ACCEPTANCE.md) | by hand, on the phone | What only a real route can show: latency, delivery, the alphabet probe, background receipt, recovery after a kill. |

## Running the server suite

```sh
make -C server check                        # everything, exactly as CI runs it
cd server
uv run python -P -m pytest tests/protocol -q                 # one package
uv run python -P -m pytest tests/service/test_handler.py -q  # one file
uv run python -P -m pytest -k "resend" -q                    # by name
uv run python -P -m pytest --cov --cov-report=html           # then open htmlcov/index.html
```

`-P` keeps `sys.path` the same as CI's. On the reference Windows machine, run the full suite
in the background and keep working: it takes about two minutes, and a foreground run blocks
the session. Never edit a source file while a coverage run is in progress: the report then
lines up old line numbers with the new file and a complete module reads as 72%.

## Running the Android suite

```sh
cd android
./gradlew check                 # ktlint, unit tests, coverage floors, for every module
./gradlew :protocol:test        # one module
./gradlew ktlintFormat          # fix layout before ktlintCheck complains
```

`:protocol` and `:core` are held at 100% line and branch by JaCoCo. In `:app`, everything
outside the `ui` package is held at 100% line and branch too, and the Compose screens at 99%
of lines (ADR-0009 says which four lines no test can reach, and why screens carry no branch
floor). The report is `app/build/reports/jacoco/jacocoAppReport/html/index.html`.

The app's tests run under Robolectric at the Galaxy S21 Ultra's screen size
(`app/src/test/resources/robolectric.properties`). One test repeats the important controls
on a 320 by 480 phone, where they must still be reachable by scrolling. `MainActivityTest`
drives the real activity over the real application, including the permission dialog's
answer; `SmsTest` feeds the receiver real SMS-DELIVER PDUs.

## How the fakes work

Every seam to the outside world is a `Protocol` with a hand-written fake in the same package
or next to it, and the real thing is only ever reached through that seam:

| Seam | Interface | Fake | Real |
| --- | --- | --- | --- |
| The web | `content.fetch.Fetcher` | `content.fakes.FakeFetcher` (a table of URLs; unknown is 404) | `HttpxFetcher` |
| Name resolution | `content.fetch.Resolver` | a table in the fetch tests | `SystemResolver` |
| Search | `content.search.SearchProvider` | `content.fakes.FakeSearchProvider` | `DdgsSearchProvider` |
| SMS | `transport.base.Transport` | `transport.fake.FakeTransport` (an inbox and an outbox) | `TwilioTransport` |
| Time | `clock.Clock` | `clock.FakeClock` (moves only when told; `sleep` returns at once) | `SystemClock` |
| The phone | none; it is the other end | `simulate.phone.VirtualPhone` | the Android app |

`content.fakes.load_fixtures` builds a fetcher and a search provider from
`protocol/fixtures/index.json`, so tests and the offline simulator read the same recorded
pages. There are no mocking libraries on the server; `respx` is used only to stand in for
Twilio's HTTP endpoints in the contract tests.

## The golden vectors

`protocol/vectors/` is generated from the Python reference by `make vectors` and committed.
`make vectors-check` (part of `make check`) fails when the generator's output and the files
differ in either direction. Every case is one JSON file; `manifest.json` carries a hash of
each. The Kotlin build translates the frame, envelope and request cases and the constants in
`ids.json` into tab-separated and properties resources at test time (`GoldenVectorsTask` and
`IdsPropertiesTask` in `android/build-logic`), so the app module needs no JSON library. The
Kotlin suite asserts frames both ways, envelopes decode-only (with the packaged dictionary,
whose hash it checks against `ids.json`), and requests format-only, since the phone never
parses one.

To change the wire format:

1. Change the Python implementation and its tests.
2. Edit `protocol/PROTOCOL.md` to say the new rule.
3. `make vectors`, then read the diff: it is the review surface. A vector that changed for a
   reason you did not intend is a bug.
4. Change the Kotlin implementation until its vector test passes.
5. Commit all of it in one pull request.

Compressed vectors are asserted both ways in Python (the pinned `zstandard` reproduces the
committed bytes) and decode-only in Kotlin, so a library upgrade shows up as a vector diff
to regenerate deliberately.

## Adding a test

- **A bug fix starts with a failing test** whose name says what the defect was:
  `test_a_reused_tag_forgets_what_it_meant_before`. The test is the commit's first hunk.
- **Name the behaviour, not the method.** `test_strangers_get_nothing_and_cost_nothing`,
  not `test_handle_unknown_sender`.
- **Phone numbers** come from `tests/conftest.py`: Ofcom's drama range, so no test can text
  a real person.
- **Time** comes from the `clock` fixture, a `FakeClock` at 2026-09-30 12:00 UTC.
- **Handler tests** use `tests/service/conftest.py`'s `build_rig`: recorded fixtures, an
  in-memory store, a budget, and `rig.ask("a7 g https://...")` to handle one SMS.
- **Coverage is 100% or the build fails.** A branch that cannot be reached is a branch to
  delete, not to exclude.

## Live tests

`server/tests/live/` sends real SMS through the account in `server/.env`. They are marked
`live`, deselected by default (`-m 'not live'` in `pyproject.toml`), and run only by hand:

```sh
TEXTWIRE_LIVE_TARGET=+447700900123 make -C server test-live
```

Record the result, the date and the cost in [ACCEPTANCE.md](ACCEPTANCE.md).

## The browser scripts

Two pieces of JavaScript ship: the script inside the dashboard page
(`server/src/textwire/api/dashboard.py`) and the landing page's `site/app.js`. Neither has a
build step, so their tests have none either: `server/tests/js/dom.mjs` is a small stand-in
for the parts of a page they touch, and the tests use only `node:test`.

```sh
cd server
uv run python -P -m pytest tests/test_javascript.py -q    # as the suite runs them
```

`test_javascript.py` cuts the script out of the page the server really serves, so the test
cannot drift from what ships. Without Node the two tests skip locally and say so; in CI a
missing Node is a failure.

## The site

`make site` builds the whole GitHub Pages site into `build/site`: MkDocs writes the handbook
into `build/site/handbook`, the files in `site/` are copied in beside it, and
`server/scripts/check_site.py` checks the result. The same checker runs on `site/` alone in
the test suite, where links into the handbook are taken on trust because the handbook is not
built yet. To look at the result, `python -m http.server -d build/site` and open the address
it prints; `make site-serve` serves the handbook alone with live reload.
