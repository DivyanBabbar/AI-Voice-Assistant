# LiveKit Dev Tester

Browser page for verifying mic → LiveKit room → speaker works end-to-end.
No app install, no framework — just three static files.

---

## 90-second quickstart

### 1 — Start LiveKit (Docker)

```bash
cd docker/livekit
docker compose up -d
```

Confirm it's healthy:

```bash
curl -s http://localhost:7880/healthz   # → {"status":"ok"}
```

### 2 — Start the FastAPI server with CORS enabled

Add to your `.env` (repo root):

```
DEV_MODE=true
```

Then start the API:

```bash
bash scripts/run_api.sh
# → Uvicorn running on http://0.0.0.0:8000
```

`DEV_MODE=true` adds a CORS allowlist for `http://localhost:5173`.
**Never set this in staging or production.**

### 3 — Serve the tester page

```bash
bash scripts/serve_web.sh
# → Serving on http://localhost:5173
```

Or manually:

```bash
cd web/dev-tester
python3 -m http.server 5173
```

### 4 — Open the browser

Navigate to **http://localhost:5173**, then:

1. Click **Join room** → grant mic permission when the browser asks.
2. Speak — the orange VU-meter bar should move in real time.
3. Click **Mute mic** to silence the track (VU-meter will drop to zero).
4. Click **Leave room** — confirm the log shows "Room disconnected".
5. Rejoin without reloading the page to verify the reconnect path.

---

## Verify the participant in LiveKit

With [lk CLI](https://github.com/livekit/livekit-cli) installed:

```bash
lk room list --url ws://localhost:7880 --api-key devkey --api-secret devsecret
lk room participants --room dev-test-room --url ws://localhost:7880 \
   --api-key devkey --api-secret devsecret
```

The tester identity (`tester-<random>`) should appear while the browser tab is open,
and disappear a few seconds after you click **Leave room** or close the tab.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `POST /v1/livekit/token` → CORS error | Ensure `DEV_MODE=true` in `.env` and restart the API server |
| Token fetch 401 / 422 | Check `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` in `.env` match `docker/livekit/livekit.yaml` |
| LiveKit WS connect fails | Confirm `docker compose up` is running: `docker ps` should show the livekit container healthy |
| VU meter doesn't move | Check browser mic permission; try a different microphone input in system settings |
| Console error: `LivekitClient is not defined` | The unpkg script failed to load — check network; verify the pinned version in `index.html` exists on unpkg |

---

## Files

| File | Purpose |
|------|---------|
| `index.html` | Page shell — loads livekit-client UMD then `main.js` as a module |
| `main.js` | All LiveKit logic, token fetch, VU-meter |
| `styles.css` | Navy + orange styles, no framework |
