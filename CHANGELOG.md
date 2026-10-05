# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `textwire setup`: a guided walk from no Twilio account to a working `server/.env`, with a link to each Twilio page it needs (opened on request), every value checked as it is typed, the auth token never shown, and a live check that the account is upgraded (a trial account breaks every frame) and the number is the account's and can send SMS.
- Repository skeleton: server and Android builds, CI, onboarding and the first ADRs.
- Python protocol, shared golden vectors, recorded content and offline SMS simulator.
- Optional Z85G encoding carries 121 payload bytes per segment; base64url remains the default.
- End-to-end checks for both encodings, plain replies and lost-frame recovery.
- Kotlin frame codec verified against the same golden vectors as Python.
- Kotlin envelope unpacking with the packaged dictionary, request formatting and tags, all pinned by the vectors; the `:core` module with the conversation state machine, tag allocator, Markdown parser and cost meter at 100% coverage.
- The Android app: a manifest-registered SMS receiver, an SMS gateway, SQLite storage of requests, frames and pages, a WorkManager resend timer, a hand-wired controller, and four Compose screens (home, reader with tappable chips, diagnostics, settings). Tested with fakes, Robolectric and Compose UI tests, including a real SMS-DELIVER PDU.
- Twilio transport: a small REST client, polling receiver, delivery status with real prices, and webhook signature helpers.
- `textwire serve` runs the real server; `textwire probe` sends one frame with every byte value so a route can be checked.
- The shared dictionary is now 880 KiB, trained at four sizes with the best held-out result kept: 3.25x on unseen pages against 2.88x before.
- Documentation: optimisation analysis with measured numbers, operations guide with a runbook, glossary, FAQ, expanded onboarding and testing guides.

- The operator dashboard: `textwire serve` now serves a self-contained page at `http://127.0.0.1:8140/` with status, today's budget and cost, recent requests, held documents and a route-probe form, plus `/healthy`, `/ready` and `/api/overview`.
- The documentation site: MkDocs Material over the repository's own Markdown, built strictly in CI and published to GitHub Pages from main.
- The GitHub Pages site now opens on a landing page in the REX ink and signal style (`site/`), with the documentation beside it as the handbook under `/handbook/`. A checker fails the build on a broken anchor, link, asset or Copy button, on draft text, and on any link from the landing page into the handbook that does not resolve.
- The Android app redesigned on Material 3 in the REX palette: a bottom bar of four destinations, one field on Home that searches words and opens addresses, progress cards for replies in flight, a reader with Previous and Next, a diagnostics checklist, a settings form validated as you type, and a first-run guide.
- The dashboard restyled in the same palette, with labelled controls, a budget meter screen readers can read, and tables that scroll on a narrow window.
- Tests for the two browser scripts, run in Node from the server suite; UI tests at the phone's real screen size and on a small phone; tests of the real activity, the settings store and the SMS receiver with real PDUs; `make doctor` tested against stand-in tools.
- Coverage floors on the app module: 100% line and branch on everything outside the screens, 99% of lines on the screens (ADR-0009, revised).
- Every app setting a person could want, applied the moment it changes: texts per page with a live estimate of words and cost, open pages as they arrive, how long to wait before asking again and how many times, price and currency, a daily limit, the reader's text size, keeping the screen on while reading, notifications, how long pages are kept, clear history, and reset. Documented in ONBOARDING.md section 7.
- Notifications for pages that arrive while the app is closed; tapping one opens the page.
- What's new: after an update worth explaining, the app opens once on a short guide to what changed, each item with Show me; never on a new install, and readable again from Settings.
- Delete a page from Home or the reader, with Undo; share a page as plain text; dismiss a reply that stopped; clear the diagnostics log.
- Server settings: `TEXTWIRE_SEARCH_SAFESEARCH`, `TEXTWIRE_SEARCH_SNIPPET_CHARS` (0 roughly halves a search's cost), `TEXTWIRE_FETCH_MAX_REDIRECTS` and `TEXTWIRE_DASHBOARD`. The dashboard lists every setting the server runs with, filterable, with secrets hidden.
- A performance baseline (`benchmarks/`): SMS per page for every fixture at every alphabet and size, how full the SMS are, and median timings of each pipeline stage on the server (`make bench`) and on the phone (`./gradlew :core:bench`). A page that costs more SMS fails `make bench`.

### Changed

- The app speaks one language: a reply in flight is named by what was asked ("Searching: weather london", "Getting page 3") instead of its wire text, counts read "1 text" and "12 texts" rather than "SMS", Home's line reads "Received today: nothing yet", page times show to the minute, and card titles are at full strength.
- Every page and link request now carries the app's page size, so a server whose default differs cannot silently override the setting.
- The CRC of every frame is computed from a lookup table on both sides, one step a byte instead of eight; the golden vectors prove the result is unchanged.
- `textwire serve` refuses `TEXTWIRE_INBOUND=webhook`, which was accepted while nothing served it.
- Links in the handbook to files it does not publish (source code, `.env.example`) lead to the file on GitHub instead of nowhere.

### Fixed

- Today's count of texts started again only when the first text of the new day arrived; it now starts at midnight UTC.
- The reader's "Asking for the next page" state matched any pending request containing " l", such as a search for "london".
- The not-found page of the site lost its styles and its way home when served below the top level.
- Retry on a stalled next-page, link, status or help request asked for nothing and dropped the request; it now asks again in the same words under a fresh tag.
- Delivery-status retries now reserve budget before sending and retry each message only once.
