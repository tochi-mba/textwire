# ADR-0006: A standalone repository that copies the LUCY family conventions

**Status:** Accepted (2026-09-30)

## Context

The owner already runs the LUCY-assistant family: a FastAPI hub and eight services with a
shared standard (uv, hatchling, ruff, strict mypy, import-linter, 100% branch coverage,
pydantic-settings that refuse unknown variables, a fixed set of Makefile verbs, AGENTS.md and
ADRs). Joining the family would also mean Keyring tokens, the parity script, the shared CI
workflow, a family port and a compose entry. The owner's Flint Android app has an equally
settled Kotlin standard: Gradle convention plugins, one version catalog, ktlint as a plain
JavaExec task, JaCoCo floors on pure-JVM modules and golden vectors shared across languages.

## Decision

textwire is its own repository. Its Python half copies the family's conventions file for
file where they apply (the Makefile verbs, `pyproject.toml` layout, the configuration rules,
the import-linter wrapper, the ADR format) but takes none of the family's runtime: no
Keyring, no parity, no shared workflow, no family port. Its Android half copies Flint's
convention plugins and version pins.

## Why

- Anyone who has worked in either repository recognises everything here.
- v1 is browse and search, which needs nothing from the family. An assistant verb that talks
  to Lucy is a later, documented addition (see `docs/ARCHITECTURE.md`), and nothing in v1
  blocks it.
- A standalone repository can be cloned and run with no other checkout, which is what
  "easy to onboard" means in practice.

## What it costs

- Conventions can drift from the family's over time; nothing enforces them here except this
  record and review.
- Integrating with Lucy later means doing the family's joining work then.

## What would change our minds

The assistant verb becoming a core feature, at which point textwire would join the family
as a service and adopt its CI and parity checks.
