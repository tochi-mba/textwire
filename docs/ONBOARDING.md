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

## 4. Read the map

- [ARCHITECTURE.md](ARCHITECTURE.md): how a request becomes a page on the phone.
- [../protocol/PROTOCOL.md](../protocol/PROTOCOL.md): the wire format.
- [../AGENTS.md](../AGENTS.md): the rules every change keeps.
- [TESTING.md](TESTING.md): the test layers and how to run each.
