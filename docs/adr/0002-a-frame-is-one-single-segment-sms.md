# ADR-0002: A frame is one single-segment SMS, reassembled by us

**Status:** Accepted (2026-09-30)

## Context

A page is kilobytes; an SMS is 140 bytes. The network offers concatenated SMS (a user data
header links segments into one long message), and Twilio will split a long body into
segments for us. The alternative is to send many independent single SMS and put our own
sequence numbers in them.

## Decision

Every frame is exactly one single-segment SMS of at most 160 GSM-7 characters. Each carries
a six-byte header of our own (version, type, tag, sequence, total, CRC-8). The app
reassembles by tag and sequence, whatever order the frames arrive in, and asks for the
missing ones by number.

## Why

- **More payload.** A single SMS carries 160 septets. A segment of a concatenated message
  carries 153, because the concatenation header takes the rest.
- **Cheaper loss.** When one segment of a concatenated message is lost, Android discards the
  whole message and the app never sees any of it. With independent frames the app sees
  everything that arrived and asks for exactly what did not.
- **Order-free.** Twilio drains a queue at about ten segments a second and carriers reorder
  freely. Our header makes order irrelevant.
- **One code path.** Every frame looks the same to the receiver, so there is no second
  reassembly mechanism to test.

## What it costs

- Six bytes of every 120 are header: 5% overhead.
- The receiver has to implement reassembly, timeouts and resend requests. It is a small,
  pure state machine, fully unit-tested on both sides.

## What would change our minds

Evidence from the acceptance run that single SMS from our route are dropped or delayed much
more often than concatenated ones, which is not how carriers are known to behave.
