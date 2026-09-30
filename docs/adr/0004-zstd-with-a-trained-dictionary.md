# ADR-0004: zstd with a trained dictionary; Brotli rejected

**Status:** Accepted (2026-09-30)

## Context

Every byte saved is money: Twilio charges per SMS, and a page is a dozen of them. The text is
short (a page is a few kilobytes of Markdown), which is where general-purpose compressors are
weakest, because they have no history to refer back to. A shared dictionary gives them that
history before the first byte.

## Decision

Pages are compressed with zstd at level 19 using a 64 KiB dictionary trained on real
extracted pages and search results. The dictionary is committed at
`protocol/dict/textwire-v1.zdict` with its SHA-256, and its id is the codec number in the
envelope. The server compresses with `zstandard` (pinned exactly, because the golden vectors
depend on its output); the app decompresses with `zstd-jni`. Retraining the dictionary is a
protocol change: a new file, a new codec id, regenerated vectors.

## Why

- zstd's trained dictionaries are built for exactly this: many small, similar documents.
  Facebook reported two to five times better compression on small data with a dictionary
  than without.
- Brotli has a built-in dictionary of web text, but the Python bindings (`Brotli` and
  `brotlicffi`, both at 1.2 in 2026-09) cannot attach a custom one, and the Java decoder on
  Maven Central is from 2017. Using a custom Brotli dictionary would mean shelling out to the
  CLI on the server and vendoring decoder sources on the phone.
- `zstd-jni` publishes an Android AAR with native libraries for every ABI, maintained, with
  dictionary support.

## What it costs

- A native library in the app, about 1 MB per ABI before splits.
- The committed dictionary is a binary file whose bytes the vectors depend on. `.gitattributes`
  marks it binary and a test checks its hash.
- Level 19 is slow per byte, but pages are a few kilobytes and the server has time.

## What would change our minds

A measured ratio on held-out pages that is no better than Brotli's built-in dictionary, or a
maintained Brotli binding with custom-dictionary support on both platforms.
