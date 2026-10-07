.PHONY: ci lint typecheck test hello-gemini serve-web

POETRY := $(shell command -v poetry 2>/dev/null || echo "${HOME}/.local/bin/poetry")

# Run the full local CI suite (lint → typecheck → test).  Must be green before pushing.
ci: lint typecheck test

# Ruff (import order + style) then black (formatting check).
lint:
	$(POETRY) run ruff check src tests scripts
	$(POETRY) run black --check src tests scripts

# mypy strict mode on the src/ package.
typecheck:
	$(POETRY) run mypy src

# Unit tests only (no real API calls).  Integration tests require RUN_INTEGRATION=1.
test:
	$(POETRY) run pytest -m "not integration"

# Stream scripts/samples/hello.wav to Gemini Live and save the reply to /tmp/gemini-reply.wav.
# Prerequisites: GOOGLE_API_KEY in .env, scripts/samples/hello.wav present.
# To regenerate the sample: poetry run python scripts/gen_sample.py
hello-gemini:
	$(POETRY) run python scripts/hello_gemini.py \
		--input scripts/samples/hello.wav \
		--output /tmp/gemini-reply.wav
	@echo ""
	@echo "Reply saved to /tmp/gemini-reply.wav — open it in QuickTime or run:"
	@echo "  afplay /tmp/gemini-reply.wav"

# Serve the LiveKit dev tester on http://localhost:5173.
# Prerequisites: LiveKit running (docker/livekit), API running with DEV_MODE=true.
serve-web:
	bash scripts/serve_web.sh
