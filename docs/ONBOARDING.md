# Onboarding

From a clean machine to a green `make check`. Every step is safe to repeat.

## 1. Install the tools

| Tool | Why | Check | Install (Windows) | Install (macOS / Linux) |
| --- | --- | --- | --- | --- |
| Git | the repository | `git --version` | `winget install Git.Git` | package manager |
| GNU Make | the task runner | `make --version` | `winget install ezwinports.make` | preinstalled / `apt install make` |
| uv | Python and the server's dependencies | `uv --version` | `winget install astral-sh.uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python 3.12+ | the server | `uv python list --only-installed` | `uv python install 3.12` | `uv python install 3.12` |
| JDK 17 | the Android build | `java -version` | `winget install EclipseAdoptium.Temurin.17.JDK` | `sdk install java 17-tem` |
| Android SDK platform 36 | the Android build | `echo $ANDROID_HOME` | Android command-line tools, then `sdkmanager "platforms;android-36" "build-tools;36.0.0"` | same |

On Windows run everything from Git Bash. The JDK and Android SDK are only needed for the
Android half; without them `make check` skips it locally (CI never skips).

## 2. Clone and check the machine

```sh
git clone https://github.com/tochi-mba/textwire.git
cd textwire
make doctor
```

`make doctor` lists every requirement as `ok`, `warn` or `fail` with the fix for each.

## 3. Run every gate

```sh
make install
make check
```

## 4. Try the offline simulator

From `server/`, run:

```sh
uv run python -m textwire simulate --offline
```

Enter `s bbc weather london`, `g https://dunmore-gazette.example/news/text-only-library`,
`n`, `b`, `?`, or `h`. Append `!` to a request verb for readable plain SMS replies.
Type `q` to exit. The recorded fixtures and in-memory SMS transport require no account,
phone or network, and incur no SMS charges.

To demonstrate recovery of a deliberately lost frame:

```sh
uv run python -m textwire simulate --offline --drop 1 --nak 1 -c "g https://dunmore-gazette.example/news/text-only-library"
```

`TEXTWIRE_FRAME_ALPHABET=z85g` selects the optional denser encoding. The default is `b64`.
This simulator is currently the runnable application; the Android UI and real SMS adapter
are still pending. Kotlin currently implements frame encoding and decoding, verified against
the shared Python vectors; envelope decoding and the phone receiver remain to be built.

## 5. Read the map

- [ARCHITECTURE.md](ARCHITECTURE.md): how a request becomes a page on the phone.
- [../protocol/PROTOCOL.md](../protocol/PROTOCOL.md): the wire format.
- [../AGENTS.md](../AGENTS.md): the rules every change keeps.
- [TESTING.md](TESTING.md): the test layers and how to run each.
