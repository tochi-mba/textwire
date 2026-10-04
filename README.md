# textwire

**A REX Technologies product.** Browse the web and search from an Android phone that has no
data connection, over plain SMS.

The phone sends a request as a text message to a number the server owns. The server fetches
the page or runs the search on the real internet, reduces it to readable text, compresses it
with a trained zstd dictionary, and sends it back as numbered SMS frames. The app reassembles
them, asks again for any that went missing, and shows a clean, tappable page.

**Site:** <https://tochi-mba.github.io/textwire/> (the landing page and the handbook).

> **Status: 0.1.0.** The server, the Android app and the wire format are built and tested end
> to end in process, including lost and reordered texts. What has been seen on a real phone is
> recorded only in [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md); a line there without a date has
> not been observed yet. [CHANGELOG.md](CHANGELOG.md) says what changed.

You can try it without a phone or an account: `make simulate`, then type
`s bbc weather london`. That runs the real server and a virtual phone against recorded pages
and sends no SMS.

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

[docs/ONBOARDING.md](docs/ONBOARDING.md) is the full walkthrough. `make run` starts the server
and its dashboard at `http://127.0.0.1:8140/`; `make simulate` runs the whole system in your
terminal with no phone and no account.

## Repository

| Path | What |
| --- | --- |
| [protocol/](protocol/PROTOCOL.md) | The wire format, golden vectors, dictionary and fixtures. |
| [server/](server/README.md) | The Python server. |
| `android/` | The Android app. |
| [benchmarks/](benchmarks/README.md) | The performance baseline: SMS per page and pipeline speed, with `make bench` to compare. |
| `site/` | The landing page of the GitHub Pages site; the handbook beside it is built from this repository's Markdown. |
| [docs/](docs/ARCHITECTURE.md) | Architecture, onboarding, operations, testing, acceptance, [optimisation](docs/OPTIMISATION.md), a [glossary](docs/GLOSSARY.md), a [FAQ](docs/FAQ.md), ADRs. |

## Licence

MIT. Copyright (c) 2026 REX Technologies. See [LICENSE](LICENSE).
