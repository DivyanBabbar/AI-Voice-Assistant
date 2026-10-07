#!/usr/bin/env bash
# Serve the /web/dev-tester static files on port 5173.
# Run from the repo root: bash scripts/serve_web.sh
#
# The dev tester needs:
#   1. LiveKit running:  cd docker/livekit && docker compose up -d
#   2. API running:      DEV_MODE=true bash scripts/run_api.sh
#   3. This script:      bash scripts/serve_web.sh
#
# Then open http://localhost:5173

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTER_DIR="${REPO_ROOT}/web/dev-tester"

echo "Serving ${TESTER_DIR} on http://localhost:5173"
echo "Press Ctrl-C to stop."
echo ""

cd "${TESTER_DIR}"
python3 -m http.server 5173
