# Testing

| Layer | Where | Runs in | What it proves |
| --- | --- | --- | --- |
| Unit | `server/tests/`, `android/*/src/test/` | `make check`, CI | Each module does what it says, at 100% branch coverage on the server, `:protocol` and `:core`. |
| Golden vectors | `protocol/vectors/`, read by both suites | `make check`, CI | Python and Kotlin agree on every byte of the wire format. |
| Repository rules | `server/tests/test_repo_rules.py` | `make check`, CI | File sizes, no coverage pragmas, versions agree, ADR index, internal links resolve. |

## Running the server suite

```sh
make -C server check                               # everything, as CI runs it
cd server && uv run python -P -m pytest tests/test_config.py -q   # one file
```

On the reference Windows machine run the full suite in the background and keep working;
it is quick, but a foreground run blocks the session.

## Current implementation

The offline end-to-end tests run the dispatcher, content pipeline, storage and virtual phone
together for base64url and Z85G. They cover searches, paging, plain replies, dropped-frame
recovery and bounded resend attempts. Dispatcher regression tests cover duplicate inbound
messages, backoff, delivery tracking and budgeted delivery retries.

The Kotlin suite consumes the committed frame vectors, including malformed messages and
both alphabets. Envelope, request and document vectors currently run on Python only;
the Android implementation of those contracts is pending. No device or carrier acceptance
has been performed. Coverage is a regression gate, not proof of carrier reliability.
