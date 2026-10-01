# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

### Fixed

- Delivery-status retries now reserve budget before sending and retry each message only once.
