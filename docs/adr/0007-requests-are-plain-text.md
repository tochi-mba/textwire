# ADR-0007: Requests are plain text, and `!` answers in plain text

**Status:** Accepted (2026-09-30)

## Context

Requests travel from the phone to the server; responses travel back. Requests are tiny and,
on the owner's plan, free. Responses are large and cost money. Both could use the same
encoded frames, or requests could be text a person can read and type.

## Decision

A request is readable text: an optional two-character tag, a one-letter verb, and its
arguments, for example `a7 g https://example.com` or `s weather london`. Responses are
encoded frames, except when the verb is followed by `!`, in which case the server answers
with readable SMS that any messaging app shows properly, paginated, with a hint for the next
page.

## Why

- The server can be demonstrated, debugged and used from any phone, including one without
  the app, from the first day.
- A request is one SMS either way, so encoding it would save nothing.
- Logs and the Twilio console show exactly what was asked.

## What it costs

- A small grammar with an ambiguity to define: a request that starts with two characters
  and a verb is tagged, otherwise it is not. `PROTOCOL.md` states the rule and the golden
  vectors pin it.
- Plain replies are paid for like any other SMS and carry less per message than frames
  (no compression). They are capped per page.

## What would change our minds

A carrier that rewrites or drops plain-text requests, which is not something carriers do to
person-to-person text.
