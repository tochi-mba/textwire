# Optimisation

Every SMS the server sends costs money and takes seconds. This page is the complete list of
levers that decide how many SMS a page needs and how long it takes to arrive, what each one
is worth, what was measured, and what was decided. It is the reasoning behind the numbers in
[../protocol/PROTOCOL.md](../protocol/PROTOCOL.md); change one and update the other.

The cost of a reply is:

```
SMS = ceil( (4 + compressed_text_bytes) / body_bytes_per_frame )
```

so there are exactly three places to win: fewer text bytes to send, fewer compressed bytes
per text byte, and more body bytes per SMS. A fourth family of levers is latency, which
costs nothing but patience. The last is what the SMS cost per segment is in the first place.

## 1. Body bytes per SMS

A single GSM-7 SMS holds 160 septets. Six bytes of every frame are the header (version and
type, tag, sequence, total, CRC-8), which the resend design needs (ADR-0002).

| Alphabet | Characters | Bits per character | Bytes per SMS | Body bytes | Status |
| --- | --- | --- | --- | --- | --- |
| base64url | 64 | 6.00 | 120 | 114 | Default (ADR-0003) |
| Z85G | 85 (every printable ASCII character in the GSM-7 basic table) | 6.41 | 127 | 121 (+6.1%) | Built, off by default until the route probe passes (ADR-0013) |
| GSM-7 wide | 122 (the 85 plus 37 accented and Greek letters) | 6.93 | 138 | 132 (+15.8%) | Reserved. TxtNet Browser saw carriers rewrite exactly these characters. |
| Binary (port-addressed SMS) | 256 | 8.00 | 133 | 127 (+11.4%) | Twilio cannot send it. Possible on the Android-gateway transport only. |

Z85G maps four bytes to five characters, the same arithmetic as ZeroMQ's Z85, with a
leading full stop as the alphabet marker; a base64url frame can never start with one. It
costs one character, which is why it carries 127 bytes rather than 128. The wide alphabet
would need the same probe TxtNet failed; it stays reserved until the acceptance run says
otherwise (line 10 of [ACCEPTANCE.md](ACCEPTANCE.md)).

Two things were checked and rejected here:

- **A denser header.** Dropping the CRC saves one byte in 120 (0.8%) and loses the only
  check that a carrier did not rewrite a character. Two-byte tags are needed for 1,296 tags.
- **Concatenated SMS.** A carrier-concatenated segment carries 153 septets, a single SMS
  160, and Android drops a whole concatenated message if one part is lost (ADR-0002).

## 2. Compressed bytes per text byte

Measured on 2026-10-01 on 309 held-out page-sized samples (941,005 bytes) that the
dictionary never saw in training, all at the production level. Ratios are raw bytes over
compressed bytes; higher is better.

| Method | Ratio | Note |
| --- | --- | --- |
| zlib level 9 | 2.17x | |
| lzma preset 6 | 2.04x | Worse than zlib on inputs this small: its headers cost more than its model earns. |
| zstd level 19, no dictionary | 2.18x | |
| zstd level 19, 110 KiB trained dictionary | 2.88x | |
| zstd level 22, 110 KiB dictionary | 2.88x | Level 22 earns nothing over 19 on page-sized inputs. |
| zstd level 19, 220 KiB dictionary | 2.98x | |
| zstd level 19, 440 KiB dictionary | 3.10x | |
| Case-folding transform, then zstd with a 110 KiB dictionary | 2.90x | +0.7%. Not worth a second codec on the phone. |
| GSM-7 sanitised text, then zstd | 2.86x | The text is already 99.8% ASCII; nothing to gain. |

What this says:

- **The dictionary is the whole game.** Without it, every general-purpose compressor lands
  within a few percent of 2.2x. With it, zstd gains 30 to 40 percent, because a page is a few
  kilobytes and a compressor without history has nothing to refer back to.
- **Bigger dictionaries keep paying.** 110 to 440 KiB is worth 7.6 percent fewer bytes, or
  about one SMS in thirteen. The cost is 440 KiB in the APK and in server memory, which is
  nothing; the app already ships a native zstd library ten times that size. The dictionary
  is retrained at a range of sizes and the best held-out result is chosen (see
  [../protocol/dict/README.md](../protocol/dict/README.md) for the run that produced the
  committed file).
- **Transforms before the compressor do not pay.** A trained dictionary already learns the
  casing and punctuation of English; folding case by hand recovers under one percent.
- **Level 19 is the right level.** Level 22 is slower and no smaller on these inputs.

Not measured yet, listed so nobody wonders:

- **Brotli** with its built-in web-text dictionary would land near zstd-with-dictionary,
  but neither Python binding can attach a custom dictionary and the maintained Java
  decoder cannot take one either (ADR-0004), so it cannot use ours.
- **A bespoke context-mixing model** trained on the corpus and shipped as a static model
  could beat zstd on inputs this small by a further 10 to 20 percent. It is the one lever
  left in this section with real headroom, and it is a research project with its own
  decoder on the phone. It is not for v1.

## 3. Text bytes to send

This is where the largest savings were, and they are already in the pipeline:

- **Reader mode** removes navigation, footers, scripts and boilerplate: on the recorded
  Wikipedia fixture the HTML is 117 KB and the document text is 11 KB.
- **Links become chips** (`text[7]`, ADR-0008) and the URLs stay on the server: a link costs
  three to four bytes instead of fifty to a hundred. Following one costs a free outbound
  text of about ten characters.
- **Citations, images, escapes, bold markers, rules and table separators** are removed, and
  repeated short lines (navigation that survived extraction) are dropped.
- **Typography is simplified** everywhere: a curly quote is three UTF-8 bytes, a straight one
  is one, and the reader loses nothing.
- **Pages are cut to fit, whole blocks at a time,** so a page never wastes the frames it
  was charged for on a fragment, and the reader asks for the next page only if they want it.
  The default page is 12 SMS; a request can choose from 1 to 40.
- **Search results are five titles, domains and snippets of at most 160 characters,** about
  three to five SMS, and each result is a chip.

Levers considered and not taken:

- **Dropping the title from later pages** saves about half an SMS a page and leaves a page
  with no context if it is the one that arrives first. The title stays.
- **Sending every page of a document at once** would remove the wait for `p`, and would
  charge for pages nobody reads. On demand is right for a metered link.
- **Summarising with a model** would cut most pages to a quarter of their size. It is a
  different product with different failure modes; the assistant verb is reserved for it.

## 4. Latency

A page's arrival time is the sum of: the phone's text reaching Twilio (a few seconds), the
server noticing it (polling every 3 seconds, ADR-0005), the fetch and extraction (usually
under 2 seconds), Twilio draining the queue (10 segments a second to a UK number), and the
carrier delivering each SMS (2 to 15 seconds each, often in a burst). The design choices:

- **Frames are order-independent**, so the carrier's reordering costs nothing.
- **The phone asks only for what is missing**, after 60 seconds of silence, at most three
  times, so a lost frame costs one SMS and one minute rather than a whole page.
- **Compression state is prepared once**: digesting the dictionary took 44 ms per page and
  now takes 0.07 ms, so pagination of a long article is instant.
- **Pagination is cached** per document, size and alphabet, so `p` is a lookup.
- **A webhook instead of polling** would save up to three seconds and needs a public URL.
  It exists as an option; it is not worth a tunnel on a home PC.

## 5. Price per segment

Everything above shrinks the count; this shrinks the multiplier. Twilio's UK outbound rate
was $0.056 per segment in 2026-09. The transport is an interface with a fake and a Twilio
implementation, so a second provider is an adapter:

| Provider | Approximate UK outbound | Note |
| --- | --- | --- |
| Twilio | $0.056 | The reference implementation. Inbound $0.0075, number $2.50 a month. |
| A spare Android phone with an unlimited-text SIM | $0.00 | Built as the second transport. It is a "gateway device tethered to a computer", which some UK carriers forbid (ADR-0010); use your own SIM and your own phone only. |
| Other API providers (Vonage, Bird, AWS SNS) | $0.03 to $0.05 | Not built. Any of them is a day's work against the `Transport` interface, with the phone accepting frames from a second sender number. |

A cheaper provider for outbound with Twilio kept for inbound is the pragmatic middle: the
phone's app already accepts a list of server numbers, and plain-mode users would see two
conversations.

## 6. What the numbers add up to

For a typical 4 KB extracted article page at the defaults:

| Step | Bytes | SMS |
| --- | --- | --- |
| Extracted Markdown for one page | 4,000 | |
| zstd with the 110 KiB dictionary (2.88x) | 1,389 | 12.2 in base64url |
| zstd with the 440 KiB dictionary (3.10x) | 1,290 | 11.3 in base64url, 10.7 in Z85G |

So the two levers still open (the bigger dictionary, on by the next training run, and Z85G,
on after the route probe) take a page from 12.2 SMS to 10.7: 12 percent fewer, about eight
cents a page at Twilio's rate. Everything larger than that was already taken by reader
mode, chips and pagination before the first SMS was sent.
