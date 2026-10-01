# Operations

Running the server for real: buying the number, configuring it, starting it, watching it,
and knowing what it costs. Everything here assumes the server half is installed
([ONBOARDING.md](ONBOARDING.md)). Settings are environment variables prefixed `TEXTWIRE_`;
every one is listed with its default in [../server/.env.example](../server/.env.example).

- [1. Configuration rules](#1-configuration-rules)
- [2. The Twilio number](#2-the-twilio-number)
- [3. Configure and start](#3-configure-and-start)
- [4. What it costs and how it is capped](#4-what-it-costs-and-how-it-is-capped)
- [5. The alphabet probe](#5-the-alphabet-probe)
- [6. Watching it run](#6-watching-it-run)
- [6a. The dashboard](#6a-the-dashboard)
- [7. Runbook](#7-runbook)
- [8. The Android gateway transport](#8-the-android-gateway-transport)
- [9. Every setting](#9-every-setting)

## 1. Configuration rules

- Values come from the process environment, then from `server/.env` for local runs. `.env`
  is gitignored; never commit it.
- An unknown `TEXTWIRE_` variable stops the server at startup, so a typo cannot silently
  fall back to a default. The message names the variable.
- `make doctor` checks the machine and the configuration and says what the chosen transport
  still needs.
- Secrets (`TEXTWIRE_TWILIO_AUTH_TOKEN`, `TEXTWIRE_GATEWAY_PASSWORD`) are never logged and
  never printed by `doctor`.

## 2. The Twilio number

1. Create a Twilio account and, in the console, buy a **UK mobile number** (a `+44 7` number,
   the "Mobile" type; "Clean" numbers cost the same and come with a spam-free history). Only
   a mobile number is inside the phone's unlimited-text bundle; a landline or short code
   might be charged per text by the phone's carrier. Complete the regulatory bundle if the
   console asks for one.
2. Note the account SID, the auth token (Account, API keys and tokens) and the number in
   E.164 form (`+447700900000`).
3. Do **not** configure a messaging webhook on the number. Twilio stores inbound messages
   without one and the server polls for them (ADR-0005). If you later switch to
   `TEXTWIRE_INBOUND=webhook`, point the number's "A message comes in" URL at
   `TEXTWIRE_PUBLIC_BASE_URL/webhooks/twilio`.
4. From the console, send a text to the phone and reply to it from the phone, then confirm
   in the console's message log that the reply appears with the full body. Twilio reassembles
   long inbound texts into one message; the `NumSegments` field says how many SMS it took.
5. Record what the regulatory bundle asked for and the delivery latency you saw in
   [ACCEPTANCE.md](ACCEPTANCE.md); those are the two things only the real account can tell.

## 3. Configure and start

```sh
cd server
cp .env.example .env         # then edit:
#   TEXTWIRE_ALLOWED_NUMBERS=+447700900123     the phones that may use the server
#   TEXTWIRE_TWILIO_ACCOUNT_SID=AC...
#   TEXTWIRE_TWILIO_AUTH_TOKEN=...
#   TEXTWIRE_TWILIO_NUMBER=+447700900000
make doctor                  # every line ok or warn; no fail
make run                     # polls Twilio every 3 s and answers
```

The first thing to try is plain mode from any phone on the allowlist: text `s! weather
london` to the number. The reply is readable SMS. Then `h!` for the help page.

The server keeps its database in `TEXTWIRE_DATA_DIR/textwire.db` (default `server/data/`):
what it has answered, the documents it can still page, the frames it can still resend, and
the day's budget. Deleting the file loses nothing that matters beyond the current day's
budget count; the server recreates it.

## 4. What it costs and how it is capped

| Item | Twilio UK, 2026-09 |
| --- | --- |
| Each outbound SMS (every frame, every plain message) | $0.056 |
| Each inbound SMS (every request) | $0.0075 |
| The number | $2.50 a month |
| A search (3 to 5 SMS) | $0.17 to $0.28 |
| A default page (up to 12 SMS) | up to $0.67 |

The server enforces `TEXTWIRE_DAILY_SEGMENT_BUDGET` (200 by default, about $11) per UTC day:
it checks the worst case before doing any work and charges the exact count before sending.
When the day is spent, requests get one `E budget used/limit` notice per sender per
`TEXTWIRE_NOTICE_INTERVAL_MINUTES`, and nothing else is sent until midnight UTC.

`?` from a phone answers with the day's usage and an estimate:
`I 2026-09-30 143/200 sms ~8.01 USD v0.1.0`. The estimate uses
`TEXTWIRE_PRICE_PER_SEGMENT`; the real prices Twilio reports for each message are recorded
in the database as their delivery statuses arrive, and the budget summary carries both.

[OPTIMISATION.md](OPTIMISATION.md) explains every lever that decides how many SMS a page
needs. The two settings an operator can move are `TEXTWIRE_PAGE_FRAMES` (fewer frames, more
pages, the same total) and `TEXTWIRE_FRAME_ALPHABET` (section 5).

## 5. The alphabet probe

`TEXTWIRE_FRAME_ALPHABET=z85g` carries 6 percent more per SMS than the default `b64`, using
punctuation characters that every GSM network defines but that some routes have been seen to
rewrite. Before switching, prove the route: send one frame containing every Z85G character
to the phone and confirm the app's Diagnostics screen decodes it without a CRC error. That is
line 10 of [ACCEPTANCE.md](ACCEPTANCE.md); the `textwire probe` command that sends it arrives
with the Twilio transport. Until it passes, leave the default.

## 6. Watching it run

The server logs one line per event to stderr, in `TEXTWIRE_LOG_FORMAT=console` for a terminal
or `json` for a collector. Phone numbers are masked (`+44...0123`) and the auth token never
appears. The lines worth knowing:

| Line | Meaning |
| --- | --- |
| `answered verb=g tag=a7 sms=12` | A request was answered with that many SMS. |
| `ignored a sender who is not allowed` | Someone not on the allowlist texted the number. No reply was sent. |
| `notice suppressed kind=budget` | A budget or bad-request notice was due but one was sent within the interval. |
| `page unavailable reason=E fetch status 404` | The site answered with an error; the phone got that status line. |
| `send failed error=... attempts=4` | Twilio refused a message after retries. The phone will ask for the frame again. |
| `resending a message the provider could not deliver` | Twilio reported a frame undelivered; it was sent once more. |
| `requests were recorded but not fully answered before the last stop` | The server stopped mid-reply last time. The phone asks for what it is missing. |

## 6a. The dashboard

`make run` also serves a dashboard at `http://127.0.0.1:8140/` (`TEXTWIRE_HOST` and
`TEXTWIRE_PORT`). It is one page with no external assets that refreshes every five seconds
and shows:

- whether the server is alive and which transport, number, alphabet and page size it runs with;
- today's budget as a bar, the estimated cost, what the provider has actually charged so far,
  and how many SMS went out;
- the recent requests with who sent them (masked), how many replies each got, and whether it
  has been answered;
- the documents still held for paging and links, with the reply tag to quote;
- a form that sends the route probe to a phone on the allowlist (section 5).

It also answers `/healthy` (alive, no I/O), `/ready` (the store answers and the transport is
configured; `503` otherwise) and `/api/overview` (the JSON the page draws). The dashboard
binds to localhost and has no login: it is an operator's window onto their own machine.
Exposing it would need a reverse proxy with authentication in front, and is not something
the server does for you.

## 7. Runbook

**The phone gets no reply at all.** Is its number in `TEXTWIRE_ALLOWED_NUMBERS`, in E.164
form? Does the console's message log show the request arriving at the number? Is the server
running and logging `answered`? If the request arrived but the server saw nothing, the poll
window is `TEXTWIRE_LOOKBACK_MINUTES` back from the last message it handled; restart it.

**Replies arrive but the app shows gibberish or "CRC error".** The route is rewriting
characters. Set `TEXTWIRE_FRAME_ALPHABET=b64` if it was `z85g`. If it happens on `b64`,
the carrier is altering plain letters and digits, which no alphabet survives; record it in
ACCEPTANCE.md and use plain mode.

**Pages stop after a few frames and never complete.** Twilio's queue may be stalled or the
number rate-limited: check the console's message log for `undelivered` or `failed` with an
error code. The maintenance loop resends a failed frame once; the phone asks again after
60 seconds; after three rounds it gives up and shows a Retry button.

**`E budget` all day.** The day's SMS are spent. Raise `TEXTWIRE_DAILY_SEGMENT_BUDGET` if
that is what you want, or wait for midnight UTC. Check `?` and the log for what spent it.

**`E fetch blocked`.** The site's address is private, local or otherwise not globally
routable. That is the SSRF guard and it is not configurable.

**`E search failed` on every search.** The search engines behind the `ddgs` package are
rate-limiting or blocking. Try `TEXTWIRE_SEARCH_BACKEND=duckduckgo` or another named backend,
or wait; the `auto` backend rotates.

**Reset everything.** Stop the server, delete `TEXTWIRE_DATA_DIR/textwire.db`, start it. The
current day's budget count starts again from zero, so do it deliberately.

## 8. The Android gateway transport

`TEXTWIRE_TRANSPORT=gateway` replaces Twilio with a spare Android phone running
[SMS Gateway for Android](https://docs.sms-gate.app/) in its local-server mode, on the same
LAN as the server, with its own SIM. Every SMS then rides on that SIM's plan instead of
being billed per message.

Read ADR-0010 first: a phone tethered to a computer to send text in volume is what some UK
carriers' terms call a gateway device and forbid. Use your own SIM in your own phone, keep
the daily budget, and set the gateway app's send interval so it paces at about one message
a second. The server settings are `TEXTWIRE_GATEWAY_URL` (`http://<phone-ip>:8080`),
`TEXTWIRE_GATEWAY_USERNAME` and `TEXTWIRE_GATEWAY_PASSWORD`, which the app shows on its
local-server screen. This transport lands in a later phase; the settings exist so the
configuration does not change shape when it does.

## 9. Every setting

| Variable | Default | What it does |
| --- | --- | --- |
| `TEXTWIRE_ENVIRONMENT` | `local` | A label in logs and health output. |
| `TEXTWIRE_LOG_LEVEL` | `INFO` | `DEBUG` shows every poll. |
| `TEXTWIRE_LOG_FORMAT` | `console` | `json` for a log collector. |
| `TEXTWIRE_HOST`, `TEXTWIRE_PORT` | `127.0.0.1`, `8140` | The health endpoint and, in webhook mode, the inbound URL. |
| `TEXTWIRE_DATA_DIR` | `data` | Where the SQLite database lives. |
| `TEXTWIRE_ALLOWED_NUMBERS` | empty | Comma-separated E.164 numbers the server answers. Empty means nobody. |
| `TEXTWIRE_TRANSPORT` | `twilio` | `twilio` or `gateway`. |
| `TEXTWIRE_INBOUND` | `poll` | `poll` needs nothing public; `webhook` needs `TEXTWIRE_PUBLIC_BASE_URL`. |
| `TEXTWIRE_POLL_SECONDS` | `3.0` | How often Twilio is asked for new messages. |
| `TEXTWIRE_LOOKBACK_MINUTES` | `60` | How far back the first poll after a start looks. |
| `TEXTWIRE_SEND_RETRIES` | `3` | Retries when Twilio says a send failed temporarily (backoff 1, 2, 4 s). |
| `TEXTWIRE_SEND_GAP_MS` | `0` | A pause between the frames of one reply; 0 lets Twilio pace them. |
| `TEXTWIRE_STATUS_INTERVAL_SECONDS` | `60.0` | How often delivery statuses and prices are fetched and old data purged. |
| `TEXTWIRE_TWILIO_ACCOUNT_SID`, `TEXTWIRE_TWILIO_AUTH_TOKEN`, `TEXTWIRE_TWILIO_NUMBER` | empty | The account and number. Required for Twilio. |
| `TEXTWIRE_TWILIO_API_BASE` | `https://api.twilio.com` | Only changed to point tests at a fake. |
| `TEXTWIRE_PUBLIC_BASE_URL` | empty | The public https URL, for webhook mode only. |
| `TEXTWIRE_GATEWAY_URL`, `TEXTWIRE_GATEWAY_USERNAME`, `TEXTWIRE_GATEWAY_PASSWORD` | empty | The Android gateway. Required for that transport. |
| `TEXTWIRE_DAILY_SEGMENT_BUDGET` | `200` | Outbound SMS per UTC day, hard cap. |
| `TEXTWIRE_PRICE_PER_SEGMENT`, `TEXTWIRE_CURRENCY` | `0.056`, `USD` | For the estimate `?` shows. |
| `TEXTWIRE_FRAME_ALPHABET` | `b64` | `b64` or `z85g` (section 5). |
| `TEXTWIRE_PAGE_FRAMES` | `12` | SMS per page when a request does not say. |
| `TEXTWIRE_MAX_PAGE_FRAMES` | `40` | The most a request may ask for. |
| `TEXTWIRE_PLAIN_MESSAGES` | `4` | Messages per plain page, 1 to 9. |
| `TEXTWIRE_SEARCH_RESULTS` | `5` | Results per search, 1 to 10. |
| `TEXTWIRE_SEARCH_REGION`, `TEXTWIRE_SEARCH_BACKEND` | `uk-en`, `auto` | Passed to the search package. |
| `TEXTWIRE_SEARCH_TIMEOUT_SECONDS`, `TEXTWIRE_FETCH_TIMEOUT_SECONDS` | `20.0` | Before a search or fetch is given up. |
| `TEXTWIRE_FETCH_MAX_BYTES` | `3000000` | A page bigger than this is refused while it is still downloading. |
| `TEXTWIRE_USER_AGENT` | a browser-like string with `textwire` in it | What sites see. |
| `TEXTWIRE_RETENTION_HOURS` | `24` | How long documents and sent frames are kept for paging and resends. |
| `TEXTWIRE_NOTICE_INTERVAL_MINUTES` | `10` | At most one bad-request or budget notice per sender per interval. |
| `TEXTWIRE_DEBUG_DROP_ONCE` | empty | Frame numbers to skip, once, in the first multi-frame reply after a start. For the acceptance run only. |
