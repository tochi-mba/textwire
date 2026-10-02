# ADR-0005: Twilio inbound by polling; no public endpoint needed

**Status:** Accepted (2026-09-30)

## Context

Twilio can tell the server about an inbound SMS in two ways: by calling a webhook, or by the
server listing messages through the REST API. A webhook needs a public HTTPS URL, which on a
home PC means a tunnel or a reverse proxy, and an endpoint that has to be defended. Since
2025-01-06 Twilio stores and lists every inbound message even when no webhook is configured.

## Decision

In the default configuration the server polls the Messages list every three seconds for
messages sent to its number, deduplicates by message SID in its database, and never exposes
anything to the internet. A signed webhook receiver is planned as an option for
deployments that already have a public URL: the signature check it needs is written and
tested (`transport.twilio`), and `textwire serve` refuses `TEXTWIRE_INBOUND=webhook` until
the receiver itself exists.

## Why

- Nothing to expose, nothing to defend, nothing to set up. The server works behind any home
  router.
- Three seconds is noise against SMS delivery, which takes seconds to tens of seconds.
- Polling survives restarts cleanly: on start the server looks back an hour and the database
  says which requests were already answered.

## What it costs

- One small REST call every three seconds, about 29,000 a day. Twilio does not bill for API
  reads.
- Up to three extra seconds of latency on each request.

## What would change our minds

Twilio rate-limiting the list endpoint at this frequency, or a hosted deployment that has a
public URL anyway.
