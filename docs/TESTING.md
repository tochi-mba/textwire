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
