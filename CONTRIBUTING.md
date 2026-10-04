# Contributing

Thanks for working on textwire. This page is the workflow; [AGENTS.md](AGENTS.md) is the
set of rules every change keeps, and [docs/ONBOARDING.md](docs/ONBOARDING.md) gets a new
machine ready.

## The loop

1. Branch from `main`: `git switch -c <area>-<short-name>` (for example `server-resend-cap`).
2. Make the change with its tests. A bug fix starts with a test that fails for the reason
   the bug exists, and the test's name says what the defect was.
3. Run `make check`. It must be green before you push. On Windows, run the full server
   suite in the background and keep working; see [docs/TESTING.md](docs/TESTING.md).
4. Push and open a pull request. CI runs the same gates on Ubuntu (Python 3.12 and 3.13),
   Windows (Python 3.12) and the Android build. The single required check is `ci-ok`.
5. Merge with **rebase**, so each commit stays whole: `gh pr merge --rebase --delete-branch`.

## Commits

- Conventional prefixes: `feat(server):`, `fix(android):`, `test(protocol):`, `docs:`,
  `build:`, `ci:`, `chore:`.
- One defect per fix commit. One slice per feature commit.
- The body says why, not what; the diff says what.
- Add a line under `Unreleased` in [CHANGELOG.md](CHANGELOG.md) for anything a user or an
  operator would notice.

## Definition of done for a change

- [ ] `make check` is green locally and `ci-ok` is green on the pull request.
- [ ] Coverage is still 100% line and branch on the server, `:protocol`, `:core` and the
      app's logic, and a new control on a screen has a test that uses it.
- [ ] If the wire format changed: vectors regenerated, `protocol/PROTOCOL.md` edited, both
      languages' vector tests pass.
- [ ] If behaviour on a real phone changed: [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) rerun
      for the affected lines, with the date and cost.
- [ ] If a decision was made: an ADR in `docs/adr/` and a line in its index.
- [ ] Docs describe the new behaviour; nothing in them is stale.
- [ ] If a release changes what a person sees or can do in the app: replace `WHATS_NEW` in
      `android/app/.../ui/WhatsNewDialog.kt` with what changed (a few features, each with
      the screen it lives on) and raise `UpdateGuide.LATEST_GUIDE` by one, in the same
      pull request. Fixes and changes nobody would notice do not get a guide.

## Style

- Python follows ruff's configuration in `server/pyproject.toml`, mypy strict, and the
  import-linter contracts. Google-style docstrings on public functions.
- Kotlin follows ktlint (`intellij_idea` style, 120 columns); run `./gradlew ktlintFormat`.
- Prose in docs is plain and direct: short sentences, no marketing.
