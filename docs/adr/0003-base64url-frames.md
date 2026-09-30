# ADR-0003: Frames are base64url; denser alphabets are reserved, not built

**Status:** Accepted (2026-09-30)

## Context

Twilio sends and receives text SMS only, not binary or port-addressed SMS. So a frame has to
be text, and to stay at 160 characters it has to stay inside the GSM-7 alphabet: a single
character outside it switches the whole message to UCS-2 and cuts it to 70 characters.

Within GSM-7 there is a choice. Base64url uses 64 characters, all in the basic table,
carrying 6 bits each: 120 bytes per 160-character SMS. A custom alphabet of the 83
single-septet printable ASCII characters carries 6.375 bits (127 bytes); one of about 120
basic-table characters, including accented letters, carries 6.9 bits (138 bytes).

## Decision

v1 frames are base64url without padding: 120 bytes per SMS, six of them header. A frame
whose first character is outside the base64url alphabet is reserved for a future, denser
encoding, so one can be added later without changing the frame header.

## Why

- Base64url is in both standard libraries, so neither side carries a hand-written codec in
  its most important code path.
- Every base64url character is plain ASCII in the GSM-7 basic table. The closest prior
  project, TxtNet Browser, used a 114-character GSM-7 alphabet and found carriers rewriting
  its non-ASCII characters.
- The gain from a denser alphabet is at most 15%, and whether our route preserves the extra
  characters can only be learned on the real route (the acceptance run's alphabet probe).

## What it costs

Up to about 15% more SMS per page than the densest safe alphabet would need.

## What would change our minds

An alphabet probe on the real route that passes every character of the 83-character ASCII
set, repeated over a week. Then an 83-character alphabet is worth its 6% and the reserved
prefix is where it goes.
