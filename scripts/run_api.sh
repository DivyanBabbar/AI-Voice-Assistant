#!/usr/bin/env bash
# Launch the voiceai FastAPI service on port 8000 with hot-reload.
# Run from the repo root: bash scripts/run_api.sh
set -euo pipefail

uvicorn voiceai.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir src
