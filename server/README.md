# textwire server

The Python half of [textwire](../README.md): it receives requests sent as SMS, fetches pages
and runs searches, reduces them to text, compresses them and sends them back as numbered SMS
frames. It is also the reference implementation of the wire format in
[../protocol/PROTOCOL.md](../protocol/PROTOCOL.md): the golden vectors are generated here.

```sh
make install    # uv sync with the dev group
make check      # ruff, mypy strict, import contracts, tests at 100% branch coverage
make doctor     # check the machine and the configuration
```

Configuration is environment variables prefixed `TEXTWIRE_`; [.env.example](.env.example)
lists every one with its default.
