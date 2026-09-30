# ADR-0012: A hard daily segment budget with a cost meter

**Status:** Accepted (2026-09-30)

## Context

Twilio charged $0.056 per outbound SMS segment to UK mobiles in 2026-09. A default page is
12 segments, about $0.67. A mistake in the phone's resend logic, a loop, or a spoofed sender
could spend real money quickly, and nobody would notice until the bill.

## Decision

- The server enforces `TEXTWIRE_DAILY_SEGMENT_BUDGET` segments per UTC day, 200 by default.
- Before any fetch or search it checks the worst case for the request (the page size); after
  building the reply it charges the actual number of segments, before sending them.
- Resends are charged like everything else.
- When the budget is spent, the reply is a single `E budget used/limit` status, at most once
  per sender per `TEXTWIRE_NOTICE_INTERVAL_MINUTES`.
- `?` returns today's usage and an estimated cost; the app shows the same estimate from its
  own count. The server records Twilio's real price for each message as delivery statuses
  arrive.

## Why

A cap that cannot be bypassed turns every failure mode that costs money into one that
merely stops working until midnight UTC.

## What it costs

A busy day can hit the cap. Raising it is one setting, which is where that decision belongs.

## What would change our minds

Nothing about having a cap. The default may move once real daily usage is known.
