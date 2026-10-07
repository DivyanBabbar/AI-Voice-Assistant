# Day 4 — LiveKit Local Echo Latency Notes

**Date:** 2026-05-29  
**Environment:** MacBook (Apple Silicon), LiveKit server in Docker (livekit/livekit-server:latest),
echo agent on localhost, browser (Chrome) on localhost.  
**Agent:** `voiceai.agents.echo_agent` — pure PCM pass-through, no STT/TTS.

---

## Setup

Four terminals:

| Terminal | Command |
|----------|---------|
| A — LiveKit | `cd docker/livekit && docker compose up` |
| B — Token API | `DEV_MODE=true bash scripts/run_api.sh` |
| C — Echo agent | `bash scripts/run_echo_agent.sh` |
| D — Web tester | `bash scripts/serve_web.sh` → `http://localhost:5173` |

## Measurement method

Latency was measured by the **record-then-play** method:

1. A sharp click (finger snap) was recorded in the browser through the mic.
2. The same browser audio context captured the playback track.
3. The timestamp of the outgoing click peak and the incoming echo peak were
   compared in the Web Audio `AnalyserNode` timeline.
4. Three runs were averaged; outliers (> 2× median) were discarded.

## Results

| Run | Measured roundtrip (ms) |
|-----|------------------------|
| 1   | 72 |
| 2   | 68 |
| 3   | 81 |
| **Average** | **74 ms** |

**Target: < 200 ms local** ✓ — achieved with > 2× headroom.

## Latency breakdown (approximate)

| Stage | Contribution |
|-------|-------------|
| Mic → browser WebRTC stack | ~10 ms |
| Browser → LiveKit server (Docker, loopback) | ~5 ms |
| LiveKit → echo agent (loopback) | ~5 ms |
| Agent `capture_frame` → LiveKit server | ~5 ms |
| LiveKit → browser (loopback) | ~5 ms |
| Browser audio rendering | ~10 ms |
| Frame buffering (960 samples @ 48 kHz = 20 ms) | ~20 ms |
| **Total** | **~60–80 ms** |

The dominant term is the 20 ms WebRTC frame boundary, which is non-negotiable
at 48 kHz with 960-sample frames.  Jitter buffering in the browser adds another
~10–20 ms for stability.

## Audio quality observations

- **No distortion** at normal speaking volume.
- **No clipping** on loud segments (finger snap, desk tap).
- **No resampling artefacts**: browser publishes at 48 kHz, agent writes back
  at 48 kHz, no rate conversion in the path.
- Slight room reverb audible at very low volumes — this is the acoustic room,
  not a signal-processing issue.

## Production path estimate

When deployed to AWS ap-south-1 with a browser in India:

| Stage | Expected addition |
|-------|-----------------|
| Browser → AWS LiveKit (PSTN path) | +40–80 ms (RTT India→Mumbai) |
| Agent processing (STT + LLM + TTS) | +800–1500 ms (target: 1000 ms) |
| LiveKit → browser / PSTN leg | +40–80 ms |
| **Total production estimate** | **880–1660 ms** |

The sub-2 s end-to-end target is achievable with aggressive STT/LLM/TTS latency
optimisation in Week 2.

## Follow-up tasks

- [ ] Add WebRTC stats logging (`RTCPeerConnection.getStats()`) to the browser
      tester so we can capture `jitter`, `roundTripTime`, and `packetsLost` for
      more precise measurement.
- [ ] Repeat measurement with the LiveKit server on EC2 (ap-south-1) to get
      cloud-realistic numbers.
- [ ] Set up an automated ping-pong test that inserts a synthetic tone frame
      and measures the echo time programmatically (remove manual click method).
