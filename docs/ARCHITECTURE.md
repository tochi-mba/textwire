# Architecture

```
  Galaxy S21 (no data)                 UK mobile network / Twilio            PC (has internet)
 +----------------------+  SMS "a7 g https://..."  +-----------+  poll  +---------------------------+
 | textwire app         | -----------------------> | Twilio    | <----- | textwire server           |
 |  :protocol  codec    |                          | UK number |  send  |  transport (Twilio)       |
 |  :core      reassembly, conversations, markdown | ---------> |  service (handler, budget)|
 |  :app       SMS, storage, UI                    |           |  content (fetch, extract, |
 +----------------------+  <-- N x 160-char frames +-----------+        |    search, paginate)      |
                                                                        |  protocol (frames, zstd)  |
                                                                        |  store (SQLite)           |
                                                                        +---------------------------+
```

## The path of one request

1. The app builds a request such as `a7 g https://example.com`, records it, and sends it
   with `SmsManager`.
2. The carrier delivers it to the server's Twilio number. Twilio stores it.
3. The server polls Twilio, skips anything it has already handled, and checks the sender
   against the allowlist and the request against the daily budget.
4. The content pipeline fetches the page (with SSRF checks), extracts the article as
   Markdown, turns links into numbered chips, and cuts the text into pages that fit the
   requested number of SMS once compressed.
5. The server wraps page 1 in an envelope, compresses it with the trained dictionary, cuts it
   into frames, stores the frames for resends, charges the budget and sends them.
6. The app's SMS receiver takes frames from the server's number, stores them, and hands them
   to the conversation for that tag. When every frame is in, it decompresses the page and
   renders it; if some stay missing for a minute it asks for exactly those.

## Server modules

| Package | Responsibility | May import |
| --- | --- | --- |
| `textwire.protocol` | Frames, tags, requests, envelopes, compression, GSM-7, plain replies, vectors. Pure. | nothing else in textwire |
| `textwire.content` | Fetching, extraction, links, pagination, search, rendering documents. | protocol |
| `textwire.transport` | Twilio, the Android gateway, and a fake, behind one interface (`Transport`: `receive`, `send`, `status`). | protocol |
| `textwire.service` | `store` (SQLite), `budget`, `library` (URLs and queries to documents), `handler` (one request to its replies: resolve, render, commit), `dispatcher` (the receive and maintenance loops), `wiring` (builds them from settings). | content, transport, protocol |
| `textwire.vectors` | Generates and checks the golden vectors from the reference implementation. | content, protocol |
| `textwire.api` | Health endpoints and the optional Twilio webhook. | service and below |
| `textwire.simulate` | `phone` (the app's receiving logic in Python: tags, reassembly, resend requests) and `session` (a running server plus that phone over the fake transport; what `textwire simulate` drives). | service and below |
| `textwire.cli` | The `textwire` command. | everything |

`textwire.config`, `textwire.logs` and `textwire.clock` are leaves that everything may use.
import-linter enforces these rules in `make check`.

## Android modules

| Module | Responsibility |
| --- | --- |
| `:protocol` | Pure Kotlin: `FrameCodec` (both alphabets), `Tags`, `Requests` (canonical formatting), `Envelope` (unpacking and `joinFrames`), `Compression` (zstd with the packaged dictionary). Tested against the shared golden vectors. |
| `:core` | Pure Kotlin: `Conversation` (the per-response state machine of PROTOCOL.md section 8: frames in, resend requests and give-up out, clock passed in), `TagAllocator`, `Markdown` (document text to blocks and chips), `CostMeter`. |
| `:app` | Android: `sms` (a manifest-registered receiver that hands frames to the controller, and the `SmsManager` gateway), `data` (`Storage` on SQLite and `SettingsStore` on SharedPreferences), `work` (a WorkManager job that ticks conversations so resends go out with the UI dead), `Controller` (hand-wired, owns the open conversations and the `StateFlow` the screens draw), `ui` (home, reader with tappable chips, diagnostics, settings). `TextwireApp` builds the one controller the activity, receiver and worker share. |
