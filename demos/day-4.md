# Day 4 Demo — LiveKit Echo Agent

**Date:** 2026-05-29  
**Goal:** End-to-end audio quality verification using a minimal echo agent.

---

## What this demo shows

A Python LiveKit agent joins a room, subscribes to the browser microphone track,
and echoes every audio frame back.  No STT or TTS is involved — this is pure
PCM pass-through.  Hearing your own voice with ~75 ms delay confirms the full
media pipeline works:

```
Browser mic → WebRTC → LiveKit server → Python agent → WebRTC → Browser speaker
```

---

## Four-terminal setup

Open four terminal windows in the repo root.

### Terminal A — LiveKit server (Docker)

```bash
cd docker/livekit && docker compose up
```

Expected: `livekit-livekit-1` container starts, listens on `0.0.0.0:7880` (HTTP/WS).
Verify: `curl http://localhost:7880` → `OK`

### Terminal B — Token API (FastAPI)

```bash
DEV_MODE=true bash scripts/run_api.sh
```

Expected: Uvicorn starts on `http://0.0.0.0:8000`.
Verify: `curl http://localhost:8000/healthz` → `{"status":"ok"}`

### Terminal C — Echo agent (livekit-agents Worker)

```bash
bash scripts/run_echo_agent.sh
```

Expected output:
```
==> Starting echo agent
    LiveKit: ws://localhost:7880
    Press Ctrl-C to stop.

INFO ... worker_starting agent=echo
INFO ... echo_agent_connected room=<room-name>
INFO ... echo_track_published room=<room-name>
```

The agent is now in the room, waiting for participants.

### Terminal D — Web tester (static HTTP)

```bash
bash scripts/serve_web.sh
```

Open `http://localhost:5173` in Chrome (or any WebRTC-capable browser).

---

## Running the demo

1. In the browser:
   - Enter room name (e.g. `test-room`) and your name (e.g. `alice`).
   - Click **Join**.
   - Allow microphone access when prompted.
   - The VU meter should show audio activity immediately.

2. Speak or snap your fingers.

3. After ~75 ms you should hear your own voice back through the speakers
   (use headphones to avoid feedback).

4. Terminal C should show:
   ```
   INFO ... echo_started participant=alice track_sid=TR_...
   ```

5. Click **Leave** or close the browser tab — Terminal C shows:
   ```
   INFO ... participant_disconnected participant=alice
   INFO ... echo_agent_stopped room=test-room
   ```

---

## Measured latency

| Metric | Value |
|--------|-------|
| Roundtrip echo latency (avg 3 runs) | **74 ms** |
| Target | < 200 ms |
| Headroom | 126 ms (2.7×) |

Full breakdown in [docs/notes/day-4-livekit-latency.md](../docs/notes/day-4-livekit-latency.md).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| No echo | Check Terminal C is running and connected (`echo_agent_connected` log) |
| Feedback loop | Use headphones or mute speakers while speaking |
| `echo_agent_connected` not appearing | Check LiveKit is up (`curl localhost:7880`) |
| CORS error in browser | Confirm Terminal B has `DEV_MODE=true` |
| `ModuleNotFoundError: voiceai` | Run from repo root; use `poetry run` |
