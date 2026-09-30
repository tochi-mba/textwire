# Frequently asked questions

**Why SMS at all? Everyone has data.**
Not always: prepaid plans that ran out, rural signal that carries texts but not data, roaming
abroad, and phones on unlimited-text plans with tiny data allowances. textwire exists for the
hours and places where a text gets through and nothing else does.

**How much does a page cost?**
Every reply is outbound SMS from the server's number. At Twilio's UK rate in 2026-09 ($0.056
per SMS) a search is about $0.20 and a default page about $0.67. The phone's own texts ride on
its plan. [OPTIMISATION.md](OPTIMISATION.md) explains where every byte goes and
[OPERATIONS.md](OPERATIONS.md) how to cap the daily spend.

**Why not just send the page as text?**
A plain 4 KB page is 26 SMS. Compressed with the shared dictionary it is 12, and with the
denser alphabet 11. The plain mode (`!`) exists for phones without the app; it is the
expensive way to read.

**Why does the app need SMS permissions?**
It sends requests and receives frames as SMS; there is no other channel. It reads only
messages from the configured server number and never touches anything else in the inbox.
ADR-0011 explains why it is not the default SMS app.

**Frames show up in my messaging app as gibberish.**
That is expected in v1: Android delivers every SMS to the default messaging app as well.
Mute or archive the server's number there. Becoming the default SMS app, which would stop
this, is a later phase (ADR-0011).

**A page arrived with some frames missing. What happens?**
The app waits 60 seconds after the last frame, then asks for exactly the missing ones, up
to three times. If they still do not come it shows what it has with a Retry button. The
server keeps every frame for 24 hours so a resend is free of any fetching.

**Can I use it from a phone without the app?**
Yes. Text the server number `s! weather london` (the `!` asks for a readable reply). You get
the results as normal texts, and the last one says what to send for the next page. Any
phone, any messaging app.

**Is my browsing private?**
No more than SMS is. Both legs cross the carrier network in the clear, and the server's
provider sees every message. Do not browse anything over textwire that you would not text
in the clear. [../SECURITY.md](../SECURITY.md) has the full threat model.

**Can someone else use my server and run up my bill?**
Only numbers on the allowlist are answered, and a daily budget caps what any day can cost.
Sender numbers can be spoofed in theory, which is why the budget, not the allowlist, is the
real ceiling.

**Why Twilio? It is not the cheapest.**
It has a proper API, stores inbound messages so the server can poll instead of exposing a
webhook, and its UK numbers are ordinary mobile numbers that unlimited-text plans cover. A
spare Android phone with its own SIM is the free alternative and is built as the second
transport; other API providers are an adapter away. See section 5 of
[OPTIMISATION.md](OPTIMISATION.md).

**Can I run the whole thing without a Twilio account or a phone?**
Yes: `make simulate` runs the real server and a virtual phone in your terminal against
recorded pages. Drop `--offline` to fetch real pages; still no SMS is sent.

**Why is there a Python server and a Kotlin app instead of one language?**
The server needs the web (fetching, extraction, search) and Python has the best tools for
that; the app needs Android. What they share, the wire format, is pinned by golden vectors
that both test suites read (PROTOCOL.md section 12), so the two cannot drift apart silently.

**How do I add a new request verb?**
Grammar in `server/src/textwire/protocol/requests.py`, behaviour in the handler, the Kotlin
request formatter, a vector case, PROTOCOL.md section 6 and the help text. AGENTS.md lists
the checklist.

**How do I retrain the dictionary?**
`uv run python scripts/train_dictionary.py --write` from `server/`, then `make vectors`.
Once v1 has shipped, a retrained dictionary is a new codec number, not an edit (ADR-0004).
