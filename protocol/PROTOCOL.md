# textwire protocol, version 1

This is the contract between the server (`server/`, Python, the reference implementation)
and the phone (`android/`, Kotlin). The golden vectors in `vectors/` pin every rule here
that has bytes in it; both test suites read them. When this document and the vectors
disagree, the vectors are what the code is tested against, and the disagreement is a bug to
fix in the same pull request.

- [1. Overview](#1-overview)
- [2. Frames (server to phone)](#2-frames-server-to-phone)
- [3. Tags](#3-tags)
- [4. Payloads and envelopes](#4-payloads-and-envelopes)
- [5. Document text](#5-document-text)
- [6. Requests (phone to server)](#6-requests-phone-to-server)
- [7. Plain replies](#7-plain-replies)
- [8. Delivery, loss and resend](#8-delivery-loss-and-resend)
- [9. Server behaviour](#9-server-behaviour)
- [10. Sizes and costs](#10-sizes-and-costs)
- [11. Versioning](#11-versioning)
- [12. Golden vectors](#12-golden-vectors)

## 1. Overview

```
phone                                   server
  |  "a7 g https://example.com"  (SMS)     |
  |--------------------------------------->|  fetch, extract, paginate, compress
  |                                        |
  |  frame a7 0/12, frame a7 1/12, ...     |
  |<---------------------------------------|  12 SMS, any order
  |                                        |
  |  "b0 r a7 3,5"  (only if some are lost)|
  |--------------------------------------->|
  |  frame a7 3/12, frame a7 5/12          |
  |<---------------------------------------|
```

A **request** is readable text in one SMS (a very long URL may make it a multipart SMS,
which the network reassembles). A **response** is a numbered set of **frames**, each one
single-segment SMS. Concatenating the frames' bodies gives a **payload**: a four-byte
**envelope** followed by the **document text**, usually zstd-compressed.

## 2. Frames (server to phone)

### 2.1 Encoding

A frame is sent as the base64url encoding (RFC 4648 section 5) of 6 to 120 bytes, **without
padding**. 120 bytes encode to exactly 160 characters, the most a single GSM-7 SMS holds.
Every base64url character is in the GSM-7 basic table, so a frame never switches the SMS to
UCS-2.

A receiver strips leading and trailing whitespace from the SMS text before decoding. The
encoding must be canonical: a text that does not re-encode to itself (for example, one whose
final character carries non-zero padding bits) is rejected.

A text whose first character is outside the base64url alphabet is **reserved** for a future,
denser encoding (see [ADR-0003](../docs/adr/0003-base64url-frames.md)). A v1 receiver
rejects it as `encoding`.

### 2.2 Header

| Byte | Field | Meaning |
| --- | --- | --- |
| 0 | version, type | High nibble: protocol version, `1`. Low nibble: frame type, `1` = DATA. |
| 1-2 | tag | Unsigned 16-bit big-endian; the request's tag, `0` to `1295` (section 3). |
| 3 | seq | This frame's index in the response, from `0`. |
| 4 | total | Frames in the response, `1` to `255`. |
| 5 | crc | CRC-8 over bytes 0-4 and the body. |
| 6.. | body | `0` to `114` bytes of the payload. |

The CRC is CRC-8/SMBUS: polynomial `0x07`, initial value `0x00`, no reflection, no final
XOR. Its check value for the ASCII bytes `123456789` is `0xF4`.

### 2.3 Rejections

A receiver checks a frame in this order and reports the first failure by its reason code.
The codes are part of the contract: the vectors name them and the app shows them.

| Order | Reason | Condition |
| --- | --- | --- |
| 1 | `encoding` | A character outside `A-Z a-z 0-9 - _`, a length that leaves a remainder of 1 when divided by 4, or a non-canonical encoding. |
| 2 | `length` | Fewer than 6 or more than 120 decoded bytes. |
| 3 | `version` | The version nibble is not `1`. |
| 4 | `crc` | The CRC does not match. |
| 5 | `type` | The type nibble is not `1`. |
| 6 | `tag` | The tag is greater than `1295`. |
| 7 | `sequence` | `total` is `0`, or `seq` is not less than `total`. |

The version is checked before the CRC because a future version may lay its header out
differently; the CRC is checked before everything it protects.

### 2.4 Splitting and joining

The server cuts a payload into consecutive 114-byte bodies; the last may be shorter. An
empty payload is one frame with an empty body. A payload longer than 255 x 114 = 29,070 bytes
cannot be sent, and the server never builds one (pages are sized to fit, section 9.3).

The receiver joins bodies in `seq` order once it holds every `seq` from `0` to `total - 1`.
Arrival order means nothing. A duplicate frame with identical bytes is ignored. A duplicate
`seq` with different bytes keeps the first and counts the second in diagnostics.

## 3. Tags

A tag names one response. It is written as two characters from `0-9a-z` (base 36, most
significant first) and carried in the frame header as the number `36 x d0 + d1`, `0` to
`1295`.

| Range | Written | Allocated by |
| --- | --- | --- |
| `0` to `1259` | `00` to `yz` | The phone, sequentially, wrapping around. |
| `1260` to `1295` | `z0` to `zz` | The server, for requests that arrive without a tag. |

A phone never reuses a tag while a response to it is still arriving. A new request with a
tag the server has seen from the same number **supersedes** it: the server forgets the old
response's frames and document for that tag.

## 4. Payloads and envelopes

| Byte | Field | Values |
| --- | --- | --- |
| 0 | kind | `1` PAGE, `2` SEARCH, `3` STATUS, `4` HELP |
| 1 | codec | `0` none (UTF-8 text follows), `1` zstd with dictionary `textwire-v1` |
| 2 | page | This page's number, from `1` |
| 3 | pages | Pages in the document, `page` to `255` |
| 4.. | text | The document text, raw or compressed |

**Codec 1** is a standard zstd frame (magic number included, content size in the header, no
checksum, no dictionary id) compressed at level 19 with the dictionary in
`dict/textwire-v1.zdict`. The dictionary's SHA-256 is in `dict/README.md` and in
`vectors/ids.json`; both implementations check it. The server uses codec 0 whenever
compression would save fewer than 8 bytes.

A receiver refuses to decompress more than 65,536 bytes, and refuses a frame that declares no
content size.

Envelope rejections, in order:

| Reason | Condition |
| --- | --- |
| `short` | Fewer than 4 bytes. |
| `kind` | An unknown kind. |
| `codec` | An unknown codec. |
| `page` | `page` is `0` or greater than `pages`. |
| `compression` | Codec 1 and the bytes are not a valid zstd frame for the dictionary, or declare more than 65,536 bytes, or declare no size. |
| `text` | The text is not valid UTF-8. |

## 5. Document text

Document text is a small subset of Markdown that the phone renders without a library.

- Blocks are separated by one blank line.
- The first block of every PAGE, SEARCH and HELP page is the title line, `# Title`. Every
  page of a document repeats it; the envelope says which page this is.
- `## Heading` is a heading. The server turns deeper headings into `##`.
- A block whose first line starts with `- ` is a bullet list; each line starting with `- `
  is an item, and other lines continue the item above.
- A block whose first line starts with digits, a full stop and a space (`1. `) is a
  numbered list, with the same continuation rule.
- Any other block is a paragraph. Its lines are kept as written.
- `[n]`, with `n` from `1` to `60`, anywhere in the text is a **link chip**: link number `n`
  of the document (section 9.4). The server removes every other bracketed number from
  extracted text, so the phone can treat every `[n]` as a link.
- There is no other markup. Everything else is literal text.

A SEARCH page lists results as a numbered list whose items end with their link chip and the
site's domain, followed by a snippet line:

```
# Search: weather london

1. London - BBC Weather[1] (bbc.co.uk)
Observations and forecast for London, England.

2. London weather forecast - Met Office[2] (metoffice.gov.uk)
Detailed hourly forecast for London.
```

A STATUS page has no title. Its text is one line:

- `I <summary>` for information, such as the reply to `?`:
  `I 2026-09-30 143/200 sms ~8.01 USD v0.1.0`.
- `E <area> <detail>` for an error. The areas and details are listed in section 9.6.

## 6. Requests (phone to server)

### 6.1 Grammar

```
request    = [ tag SP ] verb-token [ SP arguments ]
tag        = 2 characters from 0-9 a-z (either case)
verb-token = verb [ size ] [ "!" ]
verb       = "g" / "s" / "p" / "l" / "r" / "?" / "h"   (either case)
size       = 1 to 3 digits
```

Leading and trailing whitespace is ignored; `SP` is one or more whitespace characters. The
tag and the verb are case-insensitive, because phone keyboards capitalise the first letter;
arguments keep their case.

**The tag rule.** If the first word is two characters from `0-9a-z` and the second word is a
verb-token, the first word is the tag. Otherwise, if the first word is a verb-token, the
request has no tag and the server assigns one. So `s1 weather` is an untagged search with
size 1 for "weather", and `s1 s weather` is a search tagged `s1`. The phone app always sends
a tag.

### 6.2 Verbs

| Verb | Arguments | Meaning |
| --- | --- | --- |
| `g` | `<url>` | Fetch the page at the URL; reply with page 1. A URL without `://` gets `https://`. Only `http` and `https`. No whitespace. At most 2,000 characters. |
| `s` | `<words>` | Search; reply with the results page. Whitespace runs collapse to one space. At most 300 characters. |
| `p` | `<tag> <n>` | Page `n` (`1` to `255`) of the document that the response `<tag>` belongs to. |
| `l` | `<tag> <n>` | Follow link `n` (`1` to `255`) of the document that the response `<tag>` belongs to; reply with page 1. |
| `r` | `<tag> <frames>` | Resend frames of response `<tag>`. `<frames>` is a comma-separated list of frame numbers and inclusive ranges from `0` to `254`, such as `3,5-7`. |
| `?` | none | Today's usage and cost estimate. |
| `h` | none | A short help page. |

**Size.** Digits after the verb set the page size in SMS: frames for an encoded reply,
messages for a plain one. They are allowed on `g`, `s`, `p` and `l`. `p` without a size
uses the size its document was first fetched with. The server clamps the size to its limits
(`TEXTWIRE_MAX_PAGE_FRAMES`, and 1 to 9 messages for plain replies).

**Plain.** `!` after the verb (and size) asks for a plain reply (section 7). It is allowed on
every verb except `r`, which only resends encoded frames.

### 6.3 Canonical form

The canonical text of a request is: the tag (if any) in lower case and a space, the verb in
lower case, the size without leading zeros, `!` if plain, then a space and the arguments.
For `r` the frame list is sorted, deduplicated and written with the shortest ranges
(`3,5-7`). A URL is written with its scheme. The phone always sends canonical text; the
server accepts anything the grammar accepts.

### 6.4 Request errors

A request that does not parse gets one plain SMS in reply, `E request <message>. Send h!
for help.`, at most once per sender per notice interval. The messages are:

| Message | Cause |
| --- | --- |
| `empty request` | Nothing but whitespace. |
| `unknown request` | Neither a tagged nor an untagged verb-token starts the text. |
| `size must be 1-255` | The size is `0` or more than `255`. |
| `size not allowed here` | A size on `r`, `?` or `h`. |
| `plain not allowed here` | `!` on `r`. |
| `url missing` / `url has spaces` / `url too long` / `only http and https` | `g` argument problems. |
| `words missing` / `words too long` | `s` argument problems. |
| `expected tag and number` / `number must be 1-255` | `p` and `l` argument problems. |
| `expected tag and frames` / `bad frame list` | `r` argument problems. |
| `no arguments allowed` | Anything after `?` or `h`. |

## 7. Plain replies

A plain reply is readable text for any messaging app. The server converts the document text
to the GSM-7 alphabet (typographic quotes and dashes become ASCII, accents outside GSM-7 are
dropped, symbols and emoji are removed, other characters become `?`), then cuts it into
messages of at most 160 GSM-7 septets, each starting with a prefix:

```
[a7 1/3] # Weather in London

Cloudy with sunny spells...
```

`a7` is the response's tag and `1/3` is the message's place in this page. A page is at most
the plain size in messages (4 by default). When more pages follow, the page's last message
ends with a line telling the reader what to send next:

```
>> p! a7 2
```

Plain pages are counted separately from encoded pages of the same document.

## 8. Delivery, loss and resend

- The server sends a response's frames in `seq` order, as fast as the transport allows.
  Carriers reorder and delay them; the phone does not care.
- The phone accepts frames only from the configured server number.
- When a response is incomplete and **60 seconds** pass without another of its frames, the
  phone sends `r <tag> <missing>` with the missing numbers (as many as fit in one SMS), under
  a new tag of its own. It does this at most **3** times per response, then shows what
  arrived with a Retry button.
- The server resends the stored frames verbatim, so they carry the original tag and slot
  into the waiting response. If it no longer has them, it replies `E resend unknown <tag>` on
  the resend request's own tag.
- A response marked incomplete still accepts late frames and completes if they arrive.

## 9. Server behaviour

### 9.1 Who is answered

Only numbers in `TEXTWIRE_ALLOWED_NUMBERS`. Anything else is logged, masked, and ignored: no
reply, no cost.

### 9.2 Documents and responses

The server stores each fetched page or search result as a **document** with its title, text
and link table, for `TEXTWIRE_RETENTION_HOURS` (24). Every response it sends is recorded
against its tag and, when it has one, its document, so `p`, `l` and `r` can refer to any
response of a document by that response's tag.

### 9.3 Pagination

A page must fit its size: its envelope and text, compressed or not, must fit in
`size x 114` bytes. The server fills pages greedily, whole blocks at a time, splitting a
block that is too big for any page at sentence ends, then at spaces, then anywhere. Every
page starts with the document's title line, truncated to 60 characters. Pagination is a pure
function of the text, the title and the size, so asking for page 3 tomorrow gives the same
page 3 as today.

### 9.4 Links

Extracted pages have their links rewritten as chips (`anchor text[n]`), numbered from `1` in
reading order; a repeated URL keeps its first number; relative URLs are resolved against the
page's final URL; `mailto:`, `javascript:`, `tel:`, `data:` and same-page `#fragment` links
become plain text; at most 60 links per document, the rest become plain text.

### 9.5 Budget

Every outbound SMS is a segment charged against `TEXTWIRE_DAILY_SEGMENT_BUDGET` for the
current UTC day. The server checks the worst case before doing any work and charges the
actual count before sending. A request that would exceed the budget gets `E budget
used/limit`, at most once per sender per notice interval.

### 9.6 Status errors

| Text | Meaning |
| --- | --- |
| `E budget <used>/<limit>` | Today's budget is spent. |
| `E fetch timeout` | The site did not answer within the fetch timeout. |
| `E fetch status <code>` | The site answered with an HTTP error. |
| `E fetch too-large` | The page is bigger than `TEXTWIRE_FETCH_MAX_BYTES`. |
| `E fetch blocked` | The address is private, local or otherwise not allowed. |
| `E fetch redirects` | More than five redirects. |
| `E fetch network` | DNS or connection failure. |
| `E extract unsupported <type>` | The content type is not HTML or plain text. |
| `E extract empty` | No readable text was found. |
| `E search failed` / `E search timeout` | The search provider failed or took too long. |
| `E page unknown <tag>` / `E page range <n>/<pages>` | `p` referred to an unknown response, or past the end. |
| `E link unknown <tag>` / `E link range <n>/<links>` | `l` referred to an unknown response, or a missing link. |
| `E resend unknown <tag>` | The frames are no longer stored. |

## 10. Sizes and costs

At Twilio's UK price in 2026-09, $0.056 per outbound SMS:

| Reply | SMS | Cost |
| --- | --- | --- |
| Status or help | 1 | $0.06 |
| Five search results | 3 to 5 | $0.17 to $0.28 |
| A default page, 12 frames, 1,368 compressed bytes, about 700 to 900 words | 12 | $0.67 |

## 11. Versioning

- The version nibble changes only for an incompatible frame layout.
- Kinds, codecs and errors are added, never renumbered. A phone that meets an unknown kind or
  codec shows `unsupported` and carries on.
- Retraining the dictionary means a new file and a new codec number; the old codec stays
  decodable until no phone needs it.
- Every change here is a pull request that regenerates the vectors and passes both test
  suites.

## 12. Golden vectors

`vectors/` is generated by `make vectors` from the Python reference implementation and
committed. `make vectors-check` fails when the generator's output and the files differ, in
either direction.

| Folder | One file per case | The Kotlin suite asserts |
| --- | --- | --- |
| `frames/` | A frame and its text, or a text and its rejection reason. | Encode and decode both ways; the same reason. |
| `requests/` | A request text and its parsed form and canonical text, or its error. | Formatting the parsed form gives the canonical text. |
| `envelopes/` | An envelope and its payload bytes, or bytes and their rejection reason. | Unpacking gives the envelope; the same reason. |
| `documents/` | A fixture page's extracted text, link table and every page's payload at two sizes. | Every payload unpacks to its page text. |
| `plain/` | A document's plain pages. | Nothing; the phone does not build plain replies. |
| `ids.json` | Every numbered constant and reason code, and the dictionary's hash. | Its own constants match. |
| `manifest.json` | Every vector file and its SHA-256. | No file is missing, extra or changed. |
