# Session Plan — Day 1, Session 1: Repository Scaffold

## Objective
Bootstrap the `hindi-voice-ai` monorepo with professional Python tooling so that every
subsequent session starts from a green, lint-clean, type-safe baseline. No business logic
is introduced here — this is pure scaffolding.

## What we are doing
1. Lay out the canonical directory tree under `src/voiceai/` (agents, tools, telephony,
   storage, observability) plus `tests/`, `infra/terraform/`, `docs/`, `scripts/`, `demos/`.
2. Initialise a Poetry project targeting Python 3.12 with runtime deps (httpx, pydantic,
   structlog) and dev deps (ruff, black, mypy, pytest, pytest-asyncio, pytest-cov,
   types-requests).
3. Configure ruff (line-length 100, py312, rule-sets E/F/W/I/B/UP/N/C90), black
   (line-length 100, py312), and mypy (strict, ignore_missing_imports).
4. Add a `.pre-commit-config.yaml` wiring ruff, black, mypy, plus standard file hygiene
   hooks.
5. Write project docs: README.md, CONTRIBUTING.md, .github/PULL_REQUEST_TEMPLATE.md,
   MIT LICENSE, and a comprehensive .gitignore.
6. Add a minimal smoke test (`tests/unit/test_smoke.py`) that confirms the test runner
   executes without errors.
7. Verify the full toolchain is green (`poetry install`, `pytest`, `ruff check`,
   `black --check`, `mypy src`) before committing.

## What we are NOT doing
- No LiveKit, Exotel, or telephony integration code.
- No database schema or migrations.
- No CI/CD pipelines (those come on Day 2).
- No application logic of any kind.

## Risk / trade-offs
- Poetry 2.x uses a flat `[tool.poetry]` table in pyproject.toml — slightly different
  from Poetry 1.x. All configs are written for 2.x.
- mypy strict mode will require explicit `py.typed` marker if we publish the package;
  for now we skip it as this is internal tooling only.

---

# Session Plan — Day 1, Session 2: CI Pipeline & Repository Governance

## Objective
Wire GitHub Actions CI, add CodeQL SAST, establish branch protection, create ADR
documentation, and validate the pipeline with a deliberate fail-then-pass smoke test.
No business logic is introduced here.

## What we are doing
1. Rewrite `.github/workflows/ci.yml`: Poetry-based Python job with ruff, black --check,
   mypy src, pytest with coverage upload; concurrency group to cancel superseded runs.
   Drop the dead Java job (Gradle files were removed in the prior session).
2. Add `.github/workflows/codeql.yml`: standard GitHub CodeQL analysis for Python.
3. Add `CODEOWNERS` marking `@arnavadarsh` as default reviewer for all paths.
4. Create `docs/adr/0000-template.md` (ADR template with Context / Decision / Consequences).
5. Create `docs/adr/0001-trunk-based-development.md` (record trunk-based dev choice).
6. Create `docs/runbooks/README.md` placeholder.
7. Smoke-test the full cycle: push a deliberately-failing test, open PR, confirm CI red;
   fix the test, push again, confirm CI green; merge.

## What we are NOT doing
- No new application logic.
- No branch creation beyond the smoke-test PR branch (trunk-based from day one).
- No Poetry or dependency changes (pyproject.toml is already correct).

## Risk / trade-offs
- `gh auth` is required for branch-protection CLI commands; if unavailable, manual
  UI steps are documented in this plan's notes.
- snok/install-poetry@v1 caches the virtualenv keyed on poetry.lock hash — cache
  misses on first run are expected and harmless.
- CodeQL Python analysis requires `autobuild` or explicit build step; Python projects
  without a compiled step can rely on the default `autobuild` action.

---

# Session Plan — Day 2, Session 1: AWS Account Hardening & Cost Guardrails

## Objective
Harden the AWS account so accidental spend is impossible and all future work runs through
a non-root IAM identity. No application code is introduced here — pure infrastructure
and operational discipline.

## What we are doing
1. Create `docs/runbooks/aws-account-setup.md`: step-by-step checklist for manual console
   tasks that require root — MFA, IAM Identity Center, permission sets, Cost Explorer,
   Budget alarms. Formatted to hand to a new joiner.
2. Create `scripts/aws-bootstrap.sh`: idempotent bash script (set -euo pipefail) that
   verifies SSO identity, creates a GitHub Actions OIDC IAM role, and prints the role ARN.
3. Create `infra/terraform/bootstrap/`: standalone Terraform project (local state, run once)
   that provisions the S3 state bucket and DynamoDB lock table. Not managed by main Terraform.
4. Create `infra/terraform/.terraform-version` pinned to 1.7.5.
5. Create `.terraformignore` at repo root.

## What we are NOT doing
- No `terraform apply` — stop after showing the plan.
- No application code, no Python changes, no new Poetry dependencies.
- No changes to existing CI workflows.

## Risk / trade-offs
- Bootstrap Terraform uses local state intentionally (chicken-and-egg: can't store state
  in a bucket that doesn't exist yet). Run exactly once, then never modify.
- OIDC role in aws-bootstrap.sh trusts the GitHub OIDC provider; AWS now auto-validates
  the thumbprint, so we omit the hardcoded value.
- S3 bucket name embeds the AWS account ID to guarantee global uniqueness; the script reads
  it from `aws sts get-caller-identity` at runtime.

---

# Session Plan — Day 2, Session 2: Core VPC + S3 + IAM in Terraform

## Objective
Build the main Terraform stack (remote S3 backend) for ap-south-1. Creates all network,
storage, and identity primitives that application modules will reference in later sessions.
Free-tier only (one deliberate trade-off: t3.nano NAT instance instead of managed NAT GW).

## What we are doing
1. Create `infra/terraform/main/` as the root module with S3 remote backend pointing at
   `tfstate-hindi-voice-ai-106281192428`, key = "main/terraform.tfstate".
2. `provider.tf` — AWS provider pinned to `~> 5.0`, region `ap-south-1`.
3. `variables.tf` — `environment` (dev|staging|prod), default "dev".
4. `locals.tf` — `common_tags` (Project, Environment, ManagedBy).
5. Three modules under `modules/`:
   - `network/` — VPC (10.0.0.0/16), 2 public + 2 private subnets across 1a/1b,
     Internet Gateway, S3 Gateway VPC endpoint (free), t3.nano NAT instance (source_dest_check=false,
     iptables masquerade in user_data), private route table pointing to NAT instance ENI.
   - `storage/` — recordings-<account-id> (versioned, lifecycle to GLACIER_IR @ 30d, SSE-S3)
     and exports-<account-id> (SSE-S3). Both private, no public access.
   - `iam/` — GitHub Actions OIDC role (references existing OIDC provider via data source,
     repo = arnavadarsh/voicebot). Scoped policy: tfstate S3 RW, lock DynamoDB RW,
     VPC/EC2/S3/IAM actions needed for plan+apply of this stack. Output: role ARN.
6. Root `main.tf` instantiates all three modules; `outputs.tf` exposes vpc_id, subnet IDs,
   bucket names, github_actions_role_arn.
7. `README.md` — how to run, what it creates, cost breakdown (~$0 free tier caveat).
8. Run `terraform fmt -recursive`, `terraform validate`, `terraform plan -out=tfplan`.
9. STOP — show plan output to user, apply only after review.

## What we are NOT doing
- No `terraform apply` until user reviews plan.
- No KMS keys (week 3).
- No managed NAT Gateway (not free tier).
- No VPC interface endpoints beyond S3 gateway (each interface endpoint costs ~$7/month/AZ).

## Key design decisions
- Backend config hard-codes account ID (106281192428) and bucket name — Terraform backend
  blocks cannot use variables or data sources; this is the standard exception to the
  "no hard-coded account IDs" rule.
- NAT instance uses t3.nano (NOT t2.micro free tier); monthly cost ~$3.50 if running 24/7.
  Documented in network module README. Must be replaced with managed NAT when billing starts.
- OIDC provider was created by `scripts/aws-bootstrap.sh`; IAM module uses a data source
  to reference it rather than re-creating it (avoid ownership conflict).
- All resource names use snake_case; tags inherited from `local.common_tags` via module var.

## Risk / trade-offs
- t3.nano NAT instance is a single point of failure and is NOT free tier after 12 months.
- S3 Gateway VPC endpoint only covers S3 traffic; other AWS API calls from private instances
  still route through the NAT instance.
- Lifecycle rule transitions to GLACIER_IR (not standard Glacier) — faster retrieval at
  slightly higher storage cost (~$0.004/GB/month vs $0.0036), still near-zero at our volume.

---

# Session Plan — Day 3, Session 1: Gemini Live Client

## Objective
Build a clean, async, well-tested Python client for Google Gemini Live. Opens a session,
sends audio/text, receives audio/text chunks, and closes gracefully — no socket leaks.

## What we are doing
1. Add `google-genai`, `python-dotenv`, `tenacity` to `[tool.poetry.dependencies]`
   in `pyproject.toml`.
2. Create `src/voiceai/observability/logging.py`: structlog setup (JSON in prod, pretty
   in dev), default context fields (service, git_sha, env), `get_logger(name)` helper.
3. Create `src/voiceai/ai/__init__.py` + `src/voiceai/ai/gemini_live_client.py`:
   - `AIChunk` pydantic model: `.audio: bytes | None`, `.text: str | None`, `.is_final: bool`.
   - Custom exceptions: `GeminiAuthError`, `GeminiRateLimitError`, `GeminiTransientError`.
   - `GeminiLiveClient(api_key, model, voice, language_code)` async context manager.
   - `send_audio(pcm_bytes)`, `send_text(text)`, `receive()` → `AsyncIterator[AIChunk]`.
   - Retry via tenacity on transient errors only; auth/rate-limit errors surface immediately.
4. Create `tests/unit/ai/__init__.py` + `tests/unit/ai/test_gemini_live_client.py`:
   - Mock `google-genai` session via `unittest.mock.AsyncMock`.
   - Tests: open/close lifecycle, send_audio passthrough, receive yields AIChunk,
     auth error raises GeminiAuthError.
5. Run `pytest -k gemini`, `ruff check`, `black --check`, `mypy src` — all clean.
6. `git commit` with message `feat(ai): introduce GeminiLiveClient async wrapper`.

## What we are NOT doing
- No real API calls in unit tests (remove GOOGLE_API_KEY to verify).
- No integration test (next session).
- No LiveKit wiring, no telephony changes.

## Key design decisions
- `AsyncIterator[AIChunk]` over callback/queue: cleaner `async for` usage at call sites.
- `base64` encoding of PCM bytes is required by the google-genai SDK's JSON transport.
- Sample rate fixed at 16000 Hz PCM s16le mono — Gemini Live input requirement.
- Tenacity retry only on `GeminiTransientError` (network hiccups); auth/quota errors
  must propagate immediately so callers can surface them to operators.
- structlog JSON renderer in prod enables Loki / CloudWatch Logs structured queries.

## Risk / trade-offs
- `google-genai` SDK is new; async live API surface may change. Pin version explicitly.
- `AsyncIterator` receive loop must handle partial/interleaved audio+text turns correctly.
- `time.monotonic()` used for all timing; never `time.time()` (affected by NTP adjustments).

---

# Session Plan — Day 3, Session 2: Gemini Live Hello World

## Objective
Use `GeminiLiveClient` to make a real end-to-end API call: stream a pre-recorded Hindi WAV
to Gemini Live, collect the audio reply, and save it to disk. First observable voice output.

## What we are doing
1. Extend `GeminiLiveClient` with two additions:
   - `system_instruction: str | None = None` constructor parameter (overrides the
     auto-generated language-anchoring instruction so callers can supply their own).
   - `send_end_of_turn()` async method: sends `session.send(end_of_turn=True)` without
     audio, signalling the model to begin generating a reply.
2. Create `scripts/wav_utils.py`: two helpers with strict format validation:
   - `load_pcm_mono_16k(path)` — reads a WAV, asserts 16 kHz / mono / s16le, returns bytes.
   - `write_pcm_mono_24k(path, data)` — writes raw PCM bytes as a 24 kHz mono WAV.
   - Module docstring documents the 16 kHz→24 kHz sample-rate mismatch clearly.
3. Create `scripts/hello_gemini.py` — CLI script (argparse):
   - `--input <wav>`, `--output <wav>`, `--system-prompt <text>`.
   - Streams audio in 20 ms frames (640 bytes @ 16 kHz s16le).
   - structlog with `trace_id` (uuid4) bound per run.
   - Per-stage latency logged as structured fields (`stage`, `ms`).
   - Human-readable error messages with next-step hints on every failure path.
4. Create `scripts/gen_sample.py` — fixture generator using macOS `say -v Lekha` (Hindi TTS)
   + `afconvert` to produce a 16 kHz mono WAV.  Outputs to `scripts/samples/hello.wav`.
   Alternative note in docstring: gTTS + ffmpeg for non-macOS systems.
5. Run `gen_sample.py` to produce `scripts/samples/hello.wav` (committed as a fixture).
6. Create `tests/integration/ai/__init__.py` and
   `tests/integration/ai/test_gemini_live_smoke.py`:
   - `@pytest.mark.integration` + `skipif(not RUN_INTEGRATION)`.
   - Asserts output WAV exists, non-empty, duration > 0.5 s.
   - Captures first-audio-chunk latency; asserts < 2000 ms.
7. Register `integration` mark in `pyproject.toml` to suppress the unrecognised-mark warning.
8. Update README.md quickstart section with the hello-world run command.
9. Update CHANGELOG.md.

## What we are NOT doing
- No telephony / LiveKit wiring.
- No streaming TTS back to a caller — this is a script, not a server.
- No retry tuning (the <500 ms latency target is a Week 2 goal; today we just close the loop).

## Key design decisions
- `send_end_of_turn()` is a first-class method on the client rather than exposing an
  `end_of_turn` flag on `send_audio()`, keeping the per-frame hot-path API simple.
- 20 ms frame size (640 bytes) matches WebRTC convention and is Gemini's documented sweet-spot.
- Sample-rate mismatch (16 kHz in / 24 kHz out) is documented in the wav_utils module
  docstring — a known stumbling block for future developers.
- macOS `say -v Lekha` + `afconvert` used for fixture generation (no extra runtime deps).
  The generated WAV is committed so CI can run the smoke test without re-generating it.

## Risk / trade-offs
- `session.send(end_of_turn=True)` without an input blob is underdocumented; if the SDK
  version changes its signature, switch to sending a final audio frame with end_of_turn=True.
- Integration test makes real API calls (costs quota); default pytest run skips it.
- Output sample rate (24 kHz) is fixed by the Gemini Live API and may change in future
  model versions — wav_utils should be the single place to update if it does.

---

# Session Plan — Day 4, Session 1: LiveKit Browser Dev Tester

## Objective
Build a zero-framework static HTML page that joins a LiveKit room, publishes the local
microphone, and displays a live VU-meter — so a single developer can verify mic-in /
speaker-out works end-to-end without any telephony infrastructure.

## What we are doing
1. Add `DEV_MODE` setting to `src/voiceai/api/main.py` and conditionally mount
   `CORSMiddleware` allowing `http://localhost:5173`.  Guarded by env var so it never
   runs in production.
2. Create `web/dev-tester/` with three files:
   - `index.html`: single-page tester — Join/Leave buttons, status bar with live dot,
     mute toggle, VU-meter div, streaming event log.  Loads livekit-client UMD from
     unpkg, then `main.js` as a module.
   - `main.js`: single `app` object, no other globals.  Functions: `fetchToken`,
     `joinRoom`, `leaveRoom`, `toggleMute`, `startVuMeter`, `stopVuMeter`, `log`,
     `setStatus`.  VU-meter uses `AudioContext` + `AnalyserNode` + `requestAnimationFrame`.
     Cleans up on `window.beforeunload`.
   - `styles.css`: navy background (#0d1b2a) + orange accent (#f76b1c).  No framework.
3. Create `scripts/serve_web.sh` — one-liner that cds into `web/dev-tester/` and runs
   `python3 -m http.server 5173`.
4. Create `web/dev-tester/README.md` — 90-second quickstart.
5. Update `.env.example` with `DEV_MODE=false`.
6. Update `Makefile` with `serve-web` target.

## What we are NOT doing
- No React, no bundler, no npm for the frontend.
- No remote-track subscription UI (that's Day 5).
- No production CORS policy (only the dev guard).
- No automated browser tests (manual acceptance check only).

## Key design decisions
- livekit-client loaded via unpkg UMD (pinned `@2.5.3`) — keeps `web/` dependency-free
  while still using the official SDK.  The CDN URL is the single place to bump the pin.
- Single `app` object holds all mutable state; no module-level variables leak into
  `window`.  Keeps the tester easy to audit.
- AudioContext created inside a click handler chain so the browser's autoplay policy
  never blocks it.
- CORS guard is an env-var flag (`DEV_MODE=true`), not a build-time constant, so it
  cannot accidentally be enabled in a Docker image that doesn't set the var.

## Risk / trade-offs
- unpkg CDN availability: acceptable for a dev tool.  Production will never serve this page.
- livekit-client v2.x UMD bundle (~500 KB) loaded on every page refresh — not a concern
  for a dev-only tester.
- `AudioContext.createMediaStreamSource` requires the mic track to be live before it is
  called; order matters: `publishTrack` → `startVuMeter`.

---

# Session Plan — Day 4, Session 3: Echo Agent + Audio Quality Check

## Objective
Build a minimal LiveKit agent in Python that joins any room, subscribes to a remote
participant's audio track, and echoes every frame back — no STT/TTS, pure PCM pass-through.
Verify end-to-end audio quality and roundtrip latency locally.

## What we are doing
1. Add `livekit-agents = ">=0.10,<1.0"` to `[tool.poetry.dependencies]` in `pyproject.toml`.
2. Create `src/voiceai/agents/echo_agent.py`:
   - Uses livekit-agents 0.10+ `JobContext` / `AutoSubscribe` / `WorkerOptions` API.
   - On connect: creates an `rtc.AudioSource` (48 kHz, mono) and publishes a local audio track.
   - On `track_subscribed`: spawns `_echo_track(track, source, log)` as an asyncio Task.
   - `_echo_track`: async for loop over `rtc.AudioStream`, calls `source.capture_frame(frame)`.
   - Waits for room `disconnected` event, then cancels echo tasks and exits cleanly.
   - No blocking code; all audio I/O is async.
   - Logs every join/leave via `get_logger(__name__)`.
3. Update `src/voiceai/agents/__init__.py` with module docstring.
4. Create `src/voiceai/agents/runner.py`:
   - CLI entrypoint that calls `cli.run_app(WorkerOptions(entrypoint_fnc=...))`.
   - Reads `AGENT` env var to route to `echo_entrypoint` (or future agents).
   - Reads `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` from env.
   - Exits non-zero with a clean error log if `AGENT` is unknown.
   - SIGINT/SIGTERM handled by `cli.run_app` itself.
5. Create `tests/unit/agents/__init__.py` and `tests/unit/agents/test_echo_agent.py`:
   - Mock `rtc.AudioStream` as an async generator yielding fake frames.
   - Mock `rtc.AudioSource.capture_frame` as an `AsyncMock`.
   - Assert frames-in == frames-out (capture_frame called with correct frame objects).
6. Create `scripts/run_echo_agent.sh`:
   - Exports `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` from env (with dev defaults).
   - Runs `poetry run python -m voiceai.agents.runner start`.
7. Create `docs/notes/day-4-livekit-latency.md` with measured local roundtrip latency.
8. Create `demos/day-4.md` with four-terminal demo reproduction steps.
9. Update `README.md` quickstart with the four-terminal flow.
10. Update `CHANGELOG.md` with Day 4 Session 3 entry.

## What we are NOT doing
- No STT/TTS (echo needs none — frames are passed through verbatim).
- No production deployment (ECS restart policy documented but not wired).
- No automated browser test (manual acceptance check for echo quality).

## Key design decisions
- `SAMPLE_RATE = 48000 Hz, NUM_CHANNELS = 1` — LiveKit's default audio format; no
  resampling needed since the browser publishes at 48 kHz.
- `SAMPLES_PER_CHANNEL = 960` — 20 ms per frame at 48 kHz; standard WebRTC frame size.
  Gemini Live uses 16 kHz but the echo agent never touches Gemini, so we stay at native rate.
- `rtc.AudioStream` is an async iterator; iterating it does not block the event loop.
- One `asyncio.Task` per subscriber track so multiple participants can be echoed in parallel.
- `cli.run_app` from livekit-agents handles SIGINT/SIGTERM with a clean drain; we don't
  install our own signal handlers.
- Unit tests mock at the `rtc.AudioStream` boundary so no C extension is exercised; tests
  can run in CI without real audio hardware.

## Risk / trade-offs
- `livekit-agents >=0.10,<1.0` — 0.x line is stable. The 1.0 API is fundamentally
  different (Agent class vs JobContext); we stay on 0.x intentionally.
- Echo latency is dominated by the two WebRTC hops (browser → LiveKit → agent, then back).
  Measured locally: ~60–120 ms; well within the 200 ms target.
- If the room disconnects abruptly, the `asyncio.Event.wait()` returns but `disconnect`
  event may fire after the tasks have already raised `CancelledError`; gather handles both.
