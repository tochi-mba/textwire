# ADR-0010: The phone only ever sends what a person would

**Status:** Accepted (2026-09-30)

## Context

The phone's SIM is on a UK consumer plan with unlimited texts. UK carriers' terms, read on
2026-09-30, draw lines around automated and high-volume use:

- EE: plans are "for normal person to person use from your device"; the only hard number is
  texting "more than 300 different numbers in a month".
  ([pay monthly plan terms](https://ee.co.uk/content/dam/help/terms-and-conditions/price-plans/mobile/pay-monthly-price-plans/EE%20pay%20monthly%20plan%20T_Cs%20-%20from%2020%20August%202026.pdf))
- O2: "You must not establish, install or use a gateway device or SIM box without our prior
  written consent." ([fair usage policy](https://www.o2.co.uk/termsandconditions/mobile/o2-consumer-fair-usage-policy))
- Vodafone: no "gateway device, application, or SIM box (including devices tethered via
  cable, Bluetooth or Wi-Fi, to a computer or the internet)" for sending large volumes or
  automated messages. ([acceptable use policy, March 2026](https://binaries.vodafone.co.uk/gbnnsauqav4t/6aDmR7PPVE78OTWlAEXxKV/79825a4e75d12eb9b4f8c55157324d6d/acceptable-use-policy-march-2026.pdf))
- Three: unlimited texts are "for personal use only", and PAYG terms bar "content of an
  excessive size, quantity or frequency".

## Decision

The phone sends only what its person taps: one request per action, plus at most three resend
requests per response, each for frames that did not arrive. It never sends on a timer of its
own accord except those resends, never texts any number but the server's, and never sends in
bulk. All the volume flows the other way, from the server's Twilio number, which is an
application-to-person sender billed per message.

A spare phone running as an SMS gateway for the server (`TEXTWIRE_TRANSPORT=gateway`) is
exactly the "gateway device tethered to a computer" some carriers forbid. It is documented as
an option for the owner's own SIM, with that warning, and it is not the default.

## Why

It keeps the owner's own line well inside ordinary use: a few dozen outgoing texts on a busy
day, all to one number, all a person's actions.

## What it costs

- Every server response is paid for through Twilio instead of riding a second unlimited plan.
- Resends are bounded, so a very bad route can leave a page incomplete. The app then shows
  what arrived and offers a retry button.

## What would change our minds

A carrier's written consent for gateway use, or a published fair-use number that makes the
gateway option safe.
