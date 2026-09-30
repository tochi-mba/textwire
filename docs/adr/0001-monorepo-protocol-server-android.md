# ADR-0001: One repository with protocol/, server/ and android/

**Status:** Accepted (2026-09-30)

## Context

textwire has two programs in two languages, a Python server and a Kotlin Android app, that
must agree byte for byte on a wire format they share. A disagreement does not fail loudly: a
frame that one side encodes and the other misreads shows up as a page of gibberish on a phone
with no data connection, which is the worst possible place to debug it.

## Decision

One git repository with three top-level parts:

- `protocol/`: the language-neutral contract. `PROTOCOL.md`, the golden vectors, the zstd
  dictionary and the fixtures both test suites read.
- `server/`: the Python server, which is also the reference implementation that generates
  the vectors.
- `android/`: the Gradle build for the app.

One CI workflow runs both halves, with a path filter so a docs-only change stays fast, and a
single aggregate check gates merges.

## Why

- A wire-format change and both implementations of it land in one pull request, reviewed
  together, tested together. Two repositories would need a versioned protocol package and a
  release dance for every change.
- The golden vectors are read from disk by both test suites. There is no copy to drift.
- A new developer clones one thing and runs one `make check`.

## What it costs

- Two toolchains in one repository: uv and Python for the server, a JDK and the Android SDK
  for the app. `make doctor` says what is missing, and `make check` skips the Android half
  locally (not in CI) when there is no JDK.
- CI runs longer than either half alone would. The path filter keeps unrelated changes
  cheap.

## What would change our minds

A second client, such as an iOS app, that needs its own release cadence. Then `protocol/`
would become its own versioned package.
