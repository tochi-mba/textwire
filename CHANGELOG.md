# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository skeleton: server and Android builds, CI, onboarding and the first ADRs.
- Python protocol, shared golden vectors, recorded content and offline SMS simulator.
- Optional Z85G encoding carries 121 payload bytes per segment; base64url remains the default.
- End-to-end checks for both encodings, plain replies and lost-frame recovery.
- Kotlin frame codec verified against the same golden vectors as Python.

### Fixed

- Delivery-status retries now reserve budget before sending and retry each message only once.
