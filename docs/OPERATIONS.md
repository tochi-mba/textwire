# Operations

Running the server for real: buying the number, configuring it, starting it, and knowing what
it costs. Settings are environment variables prefixed `TEXTWIRE_`; every one is listed with
its default in [../server/.env.example](../server/.env.example).

## Configuration rules

- Values come from the process environment, then from `server/.env` for local runs.
- An unknown `TEXTWIRE_` variable stops the server at startup, so a typo cannot silently fall
  back to a default.
- `make doctor` checks the configuration and says what the chosen transport still needs.
