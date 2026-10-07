# Day 3 Demo — Gemini Live Hindi Hello-World

**Date:** 2026-05-26  
**Branch merged:** `day-3-session-2-gemini-hello-world` → `main`  
**Tag:** `vDAY-3`

---

## What was demonstrated

A local Python script streams a pre-recorded Hindi WAV file to the Gemini Live API over a
persistent WebSocket and plays back the audio reply — all from the command line, with no
browser or app required.

This is the first end-to-end proof that the system can:
1. Accept spoken Hindi audio.
2. Pass it to an LLM that understands and responds in Hindi.
3. Return synthesised Hindi speech.

---

## How to reproduce the demo

### Prerequisites

```bash
# 1. Install dependencies
poetry install

# 2. Set your API key
echo "GOOGLE_API_KEY=<your-key>" >> .env    # get one at https://aistudio.google.com/apikey

# 3. Verify the sample clip exists (already committed)
ls scripts/samples/hello.wav
# If missing, regenerate it (macOS only):
poetry run python scripts/gen_sample.py
```

### Run it

```bash
make hello-gemini
```

Equivalent long form:

```bash
poetry run python scripts/hello_gemini.py \
    --input scripts/samples/hello.wav \
    --output /tmp/gemini-reply.wav
```

### Listen to the reply

```bash
afplay /tmp/gemini-reply.wav          # macOS
# or open in QuickTime Player / VLC
```

---

## What you hear

**Input clip** (`scripts/samples/hello.wav`):  
> *"नमस्ते, आप कैसे हैं?"*  
> ("Hello, how are you?" in Hindi)

**Expected reply** (actual content varies by model run):  
The bot replies in Hindi, introducing itself as a friendly assistant and asking how it can
help — in the voice of `Aoede` (the default TTS voice, chosen for natural Hindi prosody).

---

## What the structured log looks like

```
{"event": "loading_input", "path": "scripts/samples/hello.wav", ...}
{"event": "input_loaded", "frames": 142, "duration_s": 1.779, ...}
{"event": "opening_session", "model": "models/gemini-2.0-flash-live-001", ...}
{"event": "gemini_session_opened", "latency_ms": 312.4, ...}
{"event": "audio_sent", "stage": "audio_sent", "frames": 142, "ms": 89.2, ...}
{"event": "latency_event", "stage": "first_audio_chunk", "ms": 547.1, ...}
{"event": "run_complete", "output_duration_s": 3.24, "total_ms": 1128.6, ...}

Done.  Reply saved to /tmp/gemini-reply.wav  (3.24 s audio, 1128.6 ms total)
```

Key fields to watch:
- `latency_event / first_audio_chunk / ms` — first-chunk latency (the felt latency target).
- `total_ms` — wall-clock time from script start to WAV written.

---

## Screen recording

[TODO: 2026-05-26 — record a 60-second screen + audio capture and commit as
`demos/day-3-screen-recording.mov`.  Use `asciinema` or QuickTime screen recording.
The recording should show: terminal running `make hello-gemini`, the structured log
streaming, then `afplay` playing the reply.]

---

## Next steps after this demo

- **Day 4:** Wire `GeminiLiveClient` into the LiveKit agent skeleton so real telephone
  calls can drive the same pipeline.
- **Day 5:** Add barge-in (interrupt the bot mid-response) using the `is_final` flag
  and cancellation of the receive loop.
- **Week 2:** Add the OpenAI Realtime fallback and measure comparative latency.
