# hindi-voice-ai

> **A Hindi-first voice AI platform for rural India** — real-time, telephony-native
> conversations powered by LiveKit agents, large language models, and Exotel PSTN
> integration, designed to work over a plain phone call with no app install required.

---

## What this is

A production-grade Python monorepo that will power voice-based AI assistants capable of
conducting natural conversations in Hindi (and regional dialects). The system accepts
inbound calls via Exotel, routes them through a LiveKit media server, transcribes speech
in real-time, runs an LLM-backed dialogue agent, and speaks the response back using
text-to-speech — all with sub-2-second round-trip latency.

## What this is not

- **Not a web chatbot.** There is no browser UI. The primary interface is a phone call.
- **Not English-first.** Prompts, tool descriptions, and fallback copy are written in
  Hindi. English support comes later.
- **Not a monolith.** The repo is structured for incremental extraction into microservices
  as load grows.

---

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|----------|
| Python | 3.12 | `brew install python@3.12` |
| Poetry | 2.x | [install.python-poetry.org](https://install.python-poetry.org) |
| Git | 2.40 | `brew install git` |
| pre-commit | 3.x | `pip install pre-commit` |

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/arnavadarsh/voicebot.git
cd voicebot

# 2. Install dependencies (creates an isolated .venv automatically)
poetry install

# 3. Copy env template and add your Google AI Studio API key
cp .env.example .env
# edit .env and set GOOGLE_API_KEY=<your-key>

# 4. Run tests
poetry run pytest

# 5. Lint + format check
poetry run ruff check .
poetry run black --check .

# 6. Type check
poetry run mypy src

# 7. Install pre-commit hooks (run once after cloning)
pre-commit install
```

### Try the hello-world

Stream a pre-recorded Hindi clip to Gemini Live and save the audio reply:

```bash
poetry run python scripts/hello_gemini.py \
    --input scripts/samples/hello.wav \
    --output /tmp/reply.wav
```

Play the reply (macOS):

```bash
afplay /tmp/reply.wav
```

To regenerate the sample clip (requires macOS `say` with the Lekha voice):

```bash
poetry run python scripts/gen_sample.py
```

### Run the echo agent (four-terminal demo)

Verify end-to-end audio quality and measure roundtrip latency with a minimal
LiveKit echo agent — no STT/TTS, pure PCM pass-through.

**Terminal A — LiveKit server:**
```bash
cd docker/livekit && docker compose up
```

**Terminal B — Token API:**
```bash
DEV_MODE=true bash scripts/run_api.sh
```

**Terminal C — Echo agent:**
```bash
bash scripts/run_echo_agent.sh
```

**Terminal D — Web tester:**
```bash
bash scripts/serve_web.sh
# open http://localhost:5173, join a room, speak — hear your echo back
```

Measured local roundtrip latency: **~74 ms** (target: < 200 ms).
See [docs/notes/day-4-livekit-latency.md](docs/notes/day-4-livekit-latency.md)
and [demos/day-4.md](demos/day-4.md) for full details.

---

## Repo layout

```
voicebot/
├── src/
│   └── voiceai/
│       ├── agents/        # LiveKit voice agent definitions
│       ├── tools/         # MCP / function-calling tools
│       ├── telephony/     # Exotel + SIP integration
│       ├── storage/       # Postgres, S3, Redis clients
│       └── observability/ # Logging, tracing, metrics
├── tests/
│   ├── unit/              # Fast, no-IO tests
│   └── integration/       # Tests that need real infrastructure
├── infra/
│   └── terraform/         # Infrastructure-as-code (Day 2+)
├── docs/                  # Architecture decisions, runbooks
├── scripts/               # Dev / ops one-off scripts
├── demos/                 # Recorded demo clips
├── pyproject.toml         # Single source of truth for deps + tool config
├── .pre-commit-config.yaml
├── CONTRIBUTING.md
└── plan.md                # Session-by-session implementation plans
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit style, and PR checklist.

---

## Licence

MIT — see [LICENSE](LICENSE).
