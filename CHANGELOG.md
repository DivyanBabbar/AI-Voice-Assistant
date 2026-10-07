# Changelog

All notable changes to hindi-voice-ai are documented here.
Entries are grouped by build day and session.

---

## [Unreleased]

### Maintenance — sync with upstream, lint fix, dev-dependency bumps

- Imports re-sorted in 5 files so `ruff check` passes on ruff 0.15 (I001). Added
  `known-first-party = ["voiceai"]` so ruff 0.4 and 0.15 agree on import grouping.
- Synced `pyproject.toml` / `poetry.lock` / CodeQL workflow with upstream (uvicorn and ruff
  version ranges widened, `codeql-action` v4).
- Dev tooling: pytest 9.1, pytest-asyncio 1.4 (0.23.x crashes on pytest 9), pytest-cov 7.1,
  black 26.10, tenacity 9.1. Full suite (36 tests), ruff, black and mypy pass.
- CI: `actions/checkout` v7, `actions/upload-artifact` v7. Pre-commit hook pins aligned with CI.
- `CODEOWNERS` now points at the owner of this repository. Removed committed `java/.gradle`
  build cache and added `.gradle/` to `.gitignore`.
- Not changed: `livekit` 0.17 -> 1.x (no runtime test against a LiveKit server yet) and the
  `setup-terraform`, `configure-aws-credentials` and `github-script` bumps (Terraform workflows
  are not exercised by CI).

---

## [vDAY-4] — 2026-05-29

### Day 4, Session 3 — Echo Agent + Audio Quality Check

**Shipped:**
- `src/voiceai/agents/echo_agent.py`: minimal LiveKit agent that joins any room,
  subscribes to remote audio tracks, and echoes every PCM frame back — no STT/TTS.
  All audio handling is async (`rtc.AudioStream` async iterator +
  `source.capture_frame` awaitable).  Logs join/leave via `get_logger(__name__)`.
  Exits cleanly on room disconnect; cancels in-flight echo tasks.
- `src/voiceai/agents/__init__.py`: expanded module docstring documenting the
  agents sub-package and available agent names.
- `src/voiceai/agents/runner.py`: CLI entrypoint that reads `AGENT` env var
  (routes to `echo` or future agents), calls `cli.run_app(WorkerOptions(...))`.
  SIGINT/SIGTERM handled by `cli.run_app`; exits non-zero on unknown `AGENT`.
- `scripts/run_echo_agent.sh`: four-line shell script with dev-safe defaults
  for `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
- `tests/unit/agents/__init__.py` + `tests/unit/agents/test_echo_agent.py`:
  5 unit tests; all livekit rtc objects mocked with `AsyncMock`/`MagicMock`.
  Tests: single-frame forwarded, multiple-frames all forwarded, empty-stream,
  cancellation-is-clean, audio-constants sanity.
- `pyproject.toml`: added `livekit-agents = ">=0.10,<1.0"`;
  upgraded `livekit-api` from `^0.7` to `^0.8` (backward-compatible API surface).
- `docs/notes/day-4-livekit-latency.md`: measured local roundtrip latency
  (avg 74 ms; target < 200 ms), breakdown by stage, production estimate,
  and follow-up tasks for automated latency measurement.
- `demos/day-4.md`: four-terminal demo reproduction steps, expected log output,
  measured latency table, and troubleshooting guide.
- `README.md`: added four-terminal quickstart section for the echo agent demo.

**Half-built / follow-up:**
- Automated latency measurement (programmatic tone-echo instead of manual click).
- WebRTC `getStats()` logging in the browser tester for per-run jitter/RTT data.
- Cloud roundtrip measurement (AWS ap-south-1 LiveKit server).
- Screen + audio demo recording not yet captured (`demos/` still has placeholder).

**Blocked:**
- Installing `livekit-agents` on macOS dev machine requires the `DYLD_LIBRARY_PATH`
  workaround for the Python 3.12 pyexpat dylib issue; CI (Ubuntu) installs cleanly.

---

## [vDAY-3] — 2026-05-26

### Day 3, Session 3 — Polish, Docs, and Latency Notes

**Shipped:**
- `src/voiceai/ai/constants.py`: single source of truth for all audio-format numbers
  (`INPUT_SAMPLE_RATE_HZ`, `OUTPUT_SAMPLE_RATE_HZ`, `FRAME_SIZE_BYTES`, etc.), model
  defaults, voice defaults, and retry-policy constants.  Eliminates all magic numbers
  from `gemini_live_client.py`, `hello_gemini.py`, and the integration smoke test.
- `docs/notes/day-3-gemini-live-learnings.md`: detailed write-up of the Gemini Live
  audio format constraints, first-chunk latency observations, Hindi voice evaluation
  (Aoede chosen as primary), setup-message structure with a minimal JSON example, and a
  "things that surprised us / things to revisit" section for future team members.
- `docs/adr/0002-gemini-live-as-primary-brain.md`: ADR documenting the decision to use
  Gemini 2.0/2.5 Flash Live over Sarvam 3-step, OpenAI Realtime, and ElevenLabs, with
  consequences including the OpenAI Realtime fallback plan for Week 2 and cost estimate.
- `Makefile`: `make ci` (lint + typecheck + test), `make hello-gemini` (stream sample
  WAV → Gemini → save reply), `make lint`, `make typecheck`, `make test`.
- `demos/day-3.md`: reproduction steps for the hello-world demo, expected log output,
  and next steps.
- Unit tests expanded from 12 → 19; `src/voiceai/ai/` coverage: **100%**.  New tests
  cover `send_end_of_turn`, `receive()` exception path, `ServerError` mapping,
  explicit `system_instruction` config, `__aexit__` close-error swallowing, and
  `send_audio_with_retry` retry behaviour.

**Half-built / follow-up:**
- First-chunk latency table in `docs/notes/day-3-gemini-live-learnings.md` has
  `[TODO: 2026-05-26]` placeholders; fill in after the next live run.
- `demos/day-3.md` references a screen recording that has not yet been captured.

**Blocked:**
- Nothing.

---

### Day 3, Session 2 — Gemini Live Hello World

**Shipped:**
- `scripts/wav_utils.py`: `load_pcm_mono_16k(path)` and `write_pcm_mono_24k(path, data)`
  helpers with strict format validation.  Module docstring explicitly documents the
  16 kHz input / 24 kHz output sample-rate mismatch (a common stumbling block).
- `scripts/hello_gemini.py`: one-file CLI (argparse) that loads a WAV, streams it to
  Gemini Live in 20 ms frames, collects the audio reply, and writes a 24 kHz WAV output.
  structlog with per-run `trace_id`; per-stage latency emitted as structured fields.
  Human-readable next-step hints on every error path.
- `scripts/gen_sample.py`: fixture generator using macOS `say -v Lekha` + `afconvert`
  to produce `scripts/samples/hello.wav` (16 kHz mono Hindi TTS clip).
- `scripts/samples/hello.wav`: committed fixture — "नमस्ते, आप कैसे हैं?" at 16 kHz mono.
- `tests/integration/ai/test_gemini_live_smoke.py`: `@pytest.mark.integration` smoke test.
  Skipped by default; enable with `RUN_INTEGRATION=1`. Asserts output file exists,
  duration > 0.5 s, and first-audio-chunk latency < 2000 ms.
- `GeminiLiveClient` extended with:
  - `system_instruction: str | None` constructor param (overrides the auto-generated
    language-anchoring instruction).
  - `send_end_of_turn()` async method (signals the model to begin generating a reply).
- `pyproject.toml`: registered `integration` pytest mark to suppress warnings.
- `README.md`: added "Try the hello-world" quickstart section.

**Half-built / follow-up:**
- Latency target is < 2000 ms (acceptance bar today); tuning to < 500 ms is a Week 2 goal.
- macOS-only `say` + `afconvert` fixture generation; gTTS + ffmpeg documented as alternative.

**Blocked:**
- Nothing.

---

## [vDAY-2] — 2026-05-21

### Day 2, Session 3 — Terraform CI Integration

**Shipped:**
- `.github/workflows/terraform.yml`: PR plan workflow — runs fmt, init, validate,
  plan on every `infra/**` PR; posts plan output as a sticky comment.
- `.github/workflows/terraform-apply.yml`: Apply workflow — triggered by push to
  `main` on `infra/**`; gated by `production-infra` environment (manual approval).
- `.github/dependabot.yml`: weekly Dependabot checks for GitHub Actions and pip.
- `docs/runbooks/terraform-workflow.md`: local → PR → merge → apply lifecycle.
- `docs/runbooks/ci-deployment.md`: production-infra environment setup and approval
  process.
- `docs/runbooks/disaster-recovery.md`: DR placeholder — tfstate deletion, OIDC
  misconfig, region outage (to be deepened in Week 4).
- Trivial S3 tag (`CiTest = "day-2-plan-smoke"`) on exports bucket to smoke-test
  the plan comment loop end-to-end.

**Half-built / follow-up:**
- `production-infra` GitHub Environment must be created manually in repo Settings
  (requires repo admin access; cannot be scripted via API on free plan).
- Dependabot will open PRs to pin action refs to commit SHAs on first run.
- DR runbook sections are headings-only; expand in Week 4.

**Blocked:**
- Nothing.

---

### Day 2, Session 2 — Core VPC, S3, IAM

**Shipped:**
- `infra/terraform/main/`: root module with network, storage, and IAM sub-modules.
- VPC 10.0.0.0/16, 2 public + 2 private subnets (ap-south-1a/1b), IGW, t2.micro
  NAT instance (free-tier), S3 Gateway VPC endpoint.
- S3 buckets: `recordings-106281192428` (versioned, Glacier IR @30d) and
  `exports-106281192428`.
- IAM OIDC role `github-actions-terraform-dev` for CI.
- `.terraformignore`, `.github/workflows/codeql.yml`, `CODEOWNERS`.

**Half-built / follow-up:**
- KMS encryption deferred to Week 3; SSE-S3 in use.
- NAT instance is t2.micro free-tier shortcut; replace with NAT Gateway for prod.

**Blocked:**
- Nothing.

---

## [vDAY-1] — 2026-05-20

### Day 1 — AWS Account, IAM, and Terraform Foundation

**Shipped:**
- AWS account hardening: root MFA, IAM Identity Center, SSO user `arnav_adarsh`
  with AdministratorAccess, CloudTrail, Cost Budget.
- `infra/terraform/bootstrap/`: S3 state bucket, DynamoDB lock table, OIDC IdP,
  `github-actions-oidc` role. Applied; state stored locally then migrated.
- `scripts/aws-bootstrap.sh`: idempotent bootstrap script.
- `docs/runbooks/aws-account-setup.md`: full AWS setup checklist.
- `.github/workflows/ci.yml`: lint (ruff + black), typecheck (mypy), test (pytest).
- `docs/adr/0001-trunk-based-development.md`.
- `tests/unit/test_smoke.py`: two passing smoke tests.

**Half-built / follow-up:**
- Branch protection requires GitHub Pro (private repo); unenforced for now.
- CodeQL SARIF upload disabled; job is non-blocking (`continue-on-error: true`).

**Blocked:**
- Nothing.
