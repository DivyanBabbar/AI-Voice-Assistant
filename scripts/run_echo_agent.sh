#!/usr/bin/env bash
# Start the LiveKit echo agent worker.
#
# Prerequisites (run in separate terminals first):
#   1. LiveKit server:  cd docker/livekit && docker compose up -d
#   2. Token API:       DEV_MODE=true bash scripts/run_api.sh
#   3. Web tester:      bash scripts/serve_web.sh
#
# Then in a fourth terminal:
#   bash scripts/run_echo_agent.sh
#
# Speak into the microphone in the browser and hear your voice echoed back.
#
# Env overrides (all have dev-safe defaults):
#   LIVEKIT_URL        - defaults to ws://localhost:7880
#   LIVEKIT_API_KEY    - defaults to devkey
#   LIVEKIT_API_SECRET - defaults to devsecret
#   AGENT              - defaults to echo

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export LIVEKIT_URL="${LIVEKIT_URL:-ws://localhost:7880}"
export LIVEKIT_API_KEY="${LIVEKIT_API_KEY:-devkey}"
export LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET:-devsecret}"
export AGENT="${AGENT:-echo}"

echo "==> Starting ${AGENT} agent"
echo "    LiveKit: ${LIVEKIT_URL}"
echo "    Press Ctrl-C to stop."
echo ""

export PATH="/Users/arnavadarsh/.local/bin:${PATH}"
exec poetry run python -m voiceai.agents.runner start
