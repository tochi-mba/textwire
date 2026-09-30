# Security

textwire is a personal tool: one server, one owner, a short list of phone numbers. This page
is its threat model, what it defends against, and what it deliberately does not.

## Reporting

Open a private security advisory on the GitHub repository, or email the owner. Please do
not open a public issue for a vulnerability.

## What an attacker could want

| Asset | Why it matters |
| --- | --- |
| The Twilio account | Every outbound SMS costs money; a stolen token sends at your expense. |
| The server's network position | The server fetches URLs on request, so it must not become a way into your LAN. |
| The owner's browsing | Requests and pages cross the carrier network as SMS. |

## Defences

- **Allowlist.** The server answers only numbers in `TEXTWIRE_ALLOWED_NUMBERS`. Everything
  else is logged (masked) and dropped without a reply, so an unknown sender cannot cost you
  a single segment.
- **Daily budget.** `TEXTWIRE_DAILY_SEGMENT_BUDGET` caps outbound SMS per UTC day. It is
  checked before any fetch or search, using the worst case, and every sent segment is
  charged. Notices about an exhausted budget or a malformed request are rate-limited per
  sender. SMS sender IDs can be spoofed, so the budget, not the allowlist, is the real
  ceiling on what a day can cost.
- **Server-side request forgery.** The fetcher accepts only `http` and `https`, resolves the
  host itself and refuses any address that is not globally routable (private, loopback,
  link-local, multicast, reserved), follows at most five redirects and checks every hop the
  same way, and stops reading a body past `TEXTWIRE_FETCH_MAX_BYTES`.
- **Secrets.** Credentials come from the environment or `server/.env`, which is gitignored.
  The Twilio auth token is a `SecretStr`, never logged, and never echoed by `doctor`.
- **Logs.** Phone numbers are masked to their first two and last four digits by a formatter
  that scrubs every log line, as a second line of defence behind call sites that mask
  explicitly.
- **Webhook signatures.** When inbound SMS arrive by webhook instead of polling, every
  request must carry a valid `X-Twilio-Signature`.

## Known limits

- **SMS is plaintext** to the carriers on both legs. The compression is not encryption.
  Anything you would not text in the clear, do not browse over textwire.
- **DNS rebinding.** The fetcher checks the addresses a host resolves to, then lets the HTTP
  client resolve it again to connect. A hostile DNS server could answer differently the
  second time. The window is small and the exposure is one GET from your server; closing it
  would mean connecting by IP with a pinned SNI, which is future work.
- **The phone trusts the server number.** The app accepts frames only from the configured
  server number, but sender IDs can be spoofed. A spoofed frame fails its CRC or decodes as
  nonsense; it cannot make the app send anything except what the user taps.
