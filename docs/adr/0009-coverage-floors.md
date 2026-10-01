# ADR-0009: 100% coverage on the server and on all Kotlin logic; screens held by line

**Status:** Accepted (2026-09-30), revised 2026-10-01

## Context

The owner's standard is 100% line and branch coverage. The server and the pure-Kotlin
modules meet it directly. The Android app module was first left unmeasured, on the belief
that JaCoCo over Robolectric describes the harness more than the tests. Measuring it showed
otherwise: the numbers are accurate, and they found real gaps. The activity and the settings
store had no test at all, the SMS receiver's delivery path was never run, and Retry silently
dropped a stalled page-turn request.

What JaCoCo cannot measure fairly is the branch count of Compose code. The Compose compiler
wraps every composable in branches for skipping and restarting that no test steers.

## Decision

- The server is held at 100% line and branch coverage by `coverage.py` with `fail_under =
  100`. No `pragma: no cover` exists, and a test fails if one appears.
- The Kotlin `:protocol` and `:core` modules, which hold the codec, reassembly, the
  conversation state machine and the Markdown parser, are held at 100% line and branch by a
  JaCoCo floor that `check` enforces. Kotlin-generated synthetic classes are excluded.
- In `:app`, everything outside the `ui` package (the controller, storage, settings, the SMS
  gateway and receiver, the resend worker, the activity) is held at 100% line and branch.
- The Compose screens in `ui` are held at 99% of lines and no branch floor. The lines no
  test can reach are the closing braces of exhaustive `when`s, where Kotlin emits a throw
  for a case that cannot exist; they are four lines in 457.
- The two browser scripts (the dashboard's and the site's) are tested in Node from the
  server suite. They are small enough that every path has a named test; no coverage tool
  is run over them.

## Why

A floor is only honest where the tool measures the code and not its compiler. Lines of a
screen are that; branches of a screen are not. Replacing the exhaustive `when`s with `else`
branches would reach 100% of lines and lose the compiler's check that every screen and
every kind of block is handled, which is the worse trade.

## What it costs

Screen tests must reach every line, so a new control needs a test that scrolls to it and
uses it. The app's tests run under Robolectric and take about three minutes.

A bug that only a real device shows can still hide behind a passing suite. The on-device
acceptance run in `docs/ACCEPTANCE.md` exists for exactly that.

## What would change our minds

A coverage tool that understands Compose's generated branches, which would let the screens
carry a branch floor too.
