# Contributing to hindi-voice-ai

Thanks for working on this project. This document captures the conventions every
contributor (human or AI) must follow so the history stays readable and CI stays green.

---

## Branch naming

Branches must follow this pattern:

```
day-N-session-M-<slug>
```

Examples:
- `day-1-session-1-scaffold`
- `day-2-session-1-livekit-agent-skeleton`
- `day-5-session-2-exotel-webhook`

The slug is a short, kebab-cased description of what the branch adds.

---

## Commit messages — Conventional Commits

Every commit must conform to [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>
```

**Types:** `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `perf`, `style`

**Scope:** the sub-package or concern — e.g. `agents`, `telephony`, `storage`, `ci`,
`repo`, `deps`

**Subject rules:**
- Imperative mood: "add", not "added" or "adds"
- No trailing period
- ≤ 72 characters

Examples:
```
feat(agents): add Hindi greeting intent handler
fix(telephony): handle Exotel SIP DTMF edge case
chore(repo): scaffold project with Python tooling and CI-ready layout
test(storage): add Redis connection pool integration tests
```

---

## Pull Request expectations

All PRs must use [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

Before marking a PR ready for review:

- [ ] `poetry run pytest` passes with ≥ 90 % coverage on changed lines
- [ ] `poetry run ruff check .` exits 0
- [ ] `poetry run black --check .` exits 0
- [ ] `poetry run mypy src` exits 0
- [ ] Pre-commit hooks pass locally (`pre-commit run --all-files`)
- [ ] PR title follows Conventional Commits format
- [ ] PR description explains **why**, not just what

PRs are squash-merged into `main`. Each squash commit becomes one entry in the changelog,
so the PR title must be a valid Conventional Commit message.

---

## Python code standards

- **Docstrings:** every module gets a one-line module docstring; every public function
  gets a Google-style docstring with `Args`, `Returns`, and `Raises`.
- **Type hints:** mandatory on all public functions; mypy strict mode must pass.
- **Line length:** 100 characters (enforced by ruff + black).
- **Imports:** sorted by ruff (isort-compatible, `I` rule set).
- **Comments:** only for non-obvious logic — networking quirks, retry behaviour, timing
  constraints. Never restate what the code does.

---

## Day / session tagging

If a commit represents a demoable milestone, tag it on `main` after squash-merge:

```bash
git tag vDAY-N.M -m "Day N, Session M — <short description>"
git push origin vDAY-N.M
```
