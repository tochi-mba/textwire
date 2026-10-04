# Benchmarks

`baseline.json` is the yardstick for every optimisation: what each recorded page costs in SMS,
and how fast the server turns a request into frames. `phone.json` is the phone's half: how
fast the app turns those SMS back into a page. Change something that should make
textwire cheaper or faster, run `make bench`, and the comparison says, metric by metric, what
moved.

```sh
make bench          # this checkout against both baselines (the phone half needs a JDK)
make bench-record   # replace both baselines with this checkout's numbers
cd android && ./gradlew :core:bench            # the phone half alone
cd android && ./gradlew :core:bench -Precord   # record it alone
```

## What is measured

Everything runs over the recorded fixtures in [../protocol/fixtures](../protocol/fixtures/README.md):
three pages (a news article, a Wikipedia article, a plain-text note) and one search.

**Cost** is exact. For every document, at every alphabet and page size the golden vectors use
(base64url at 12 and 4 SMS a page, Z85G at 12) and for plain replies of 4 messages a page:

| Metric | Meaning |
| --- | --- |
| `pages` | How many pages the document is cut into. |
| `sms_first_page` | SMS for the page a request gets first. |
| `sms_total` | SMS to read the whole document. This is what an optimisation must move. |
| `text_bytes` | UTF-8 bytes of page text before compression. |
| `payload_bytes` | Bytes actually sent: envelope plus compressed text. |
| `ratio` | `text_bytes / payload_bytes`; higher is better. |
| `fill` | How full the SMS are: payload over what the frames could have carried. |

`sms_total` at the top level adds every document up per cut. `dictionary` records which
dictionary the numbers were made with, so a retrained dictionary shows up as a change.

**Speed** is the median of several runs, in milliseconds: extracting every fixture page,
cutting every document into pages (with the pagination cache cleared), compressing and
decompressing the longest article, encoding and decoding one page's frames, and a whole
page request and search request through the real handler with the fake transport. The
machine they ran on is recorded beside them.

**The phone** replays every page of every fixture document, in both alphabets, exactly as the
server sends it, and times on the JVM: loading the packaged 880 KiB dictionary (paid once
when the app starts), decoding every frame, decompressing every page, parsing every page,
and the whole path from texts to a page. A JVM on a PC is not the phone, so these numbers
compare one change against another, not against the device; `PhoneBenchTest` checks that
what is replayed rebuilds each page's text exactly.

## How comparisons work

- **Any cost change is reported**, better or worse, because cost does not depend on the
  machine. `make bench` fails if a page now takes more SMS.
- **A timing is reported** when it moved by more than half of its baseline in either
  direction. Slower timings do not fail the command: the same code runs at different
  speeds on different machines, and on one machine under load.
- The test suite checks that the committed baseline's cost half is what the code produces
  (`server/tests/test_bench.py`), the same way the vector check keeps the golden vectors
  honest. A change that alters what is sent must come with `make bench-record` and the
  baseline's diff, which is then the review: fewer SMS, or a reason.

Record speed on an idle machine. The committed baseline was recorded on the reference
Windows machine; compare timings from another machine with that in mind.
