# ADR-0009: 100% coverage on the server, `:protocol` and `:core`; `:app` measured

**Status:** Accepted (2026-09-30)

## Context

The owner's standard is 100% line and branch coverage. The server and the pure-Kotlin
modules can meet it honestly. The Android app module is different: most of its code is
Compose UI and framework glue that runs under Robolectric, where JaCoCo measures the
framework's instrumented classes as much as ours, and the numbers describe the harness more
than the tests.

## Decision

- The server is held at 100% line and branch coverage by `coverage.py` with `fail_under =
  100`. No `pragma: no cover` exists, and a test fails if one appears.
- The Kotlin `:protocol` and `:core` modules, which hold the codec, reassembly, the
  conversation state machine and the Markdown parser, are held at 100% line and branch by a
  JaCoCo floor that `check` enforces. Kotlin-generated synthetic classes are excluded.
- The `:app` module is tested with Robolectric and Compose UI tests. Its coverage is
  reported, not floored. Everything in it that has logic lives behind a small interface
  whose pure implementation sits in `:core`.

## Why

A floor on `:app` would push tests toward exercising the framework rather than the
behaviour, and would make every UI change a fight with the tool. Keeping the logic out of
`:app` keeps what matters at 100%.

## What it costs

A bug in Android glue code can hide behind a passing suite. The on-device acceptance run in
`docs/ACCEPTANCE.md` exists for exactly that code.

## What would change our minds

A coverage tool that measures Compose and Robolectric code as reliably as plain JVM code.
