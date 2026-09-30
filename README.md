# textwire

**A REX Technologies product.** Browse the web and search from an Android phone that has no
data connection, over plain SMS.

The phone sends a request as a text message to a number the server owns. The server fetches
the page or runs the search on the real internet, reduces it to readable text, compresses it
with a trained zstd dictionary, and sends it back as numbered SMS frames. The app reassembles
them, asks again for any that went missing, and shows a clean, tappable page.

> **Status: under construction.** The build plan's phases land one pull request at a time;
> [CHANGELOG.md](CHANGELOG.md) says what works today.

## What it costs to run

Every reply is paid for as outbound SMS from the server's Twilio number: $0.056 per SMS to a
UK mobile in 2026-09. A search costs about $0.20, a page about $0.67. A hard daily budget
(200 SMS by default) caps the damage from any mistake. The phone's own texts to the server
ride on its plan.

## Quick start for developers

```sh
git clone https://github.com/tochi-mba/textwire.git
cd textwire
make doctor     # what this machine is missing, and how to fix it
make install    # the server's virtualenv
make check      # every gate CI runs
```

[docs/ONBOARDING.md](docs/ONBOARDING.md) is the full walkthrough.

## Repository

| Path | What |
| --- | --- |
| [protocol/](protocol/PROTOCOL.md) | The wire format, golden vectors, dictionary and fixtures. |
| [server/](server/README.md) | The Python server. |
| `android/` | The Android app. |
| [docs/](docs/ARCHITECTURE.md) | Architecture, onboarding, operations, testing, acceptance, ADRs. |

## Licence

MIT. Copyright (c) 2026 REX Technologies. See [LICENSE](LICENSE).
