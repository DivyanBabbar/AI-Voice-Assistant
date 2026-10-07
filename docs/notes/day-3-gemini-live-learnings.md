# Day 3 — Gemini Live Learnings

**Date:** 2026-05-26  
**Branch:** `day-3-session-3-polish-docs`  
**Author:** Team (Arnav Adarsh)

---

## Audio Formats

### Input (microphone / WAV → Gemini Live)

| Property     | Value                     |
|--------------|---------------------------|
| Sample rate  | **16 000 Hz** (16 kHz)    |
| Channels     | Mono (1)                  |
| Bit depth    | 16-bit signed integer     |
| Byte order   | Little-endian (s16le)     |
| MIME type    | `audio/pcm;rate=16000`    |
| Frame size   | 640 bytes = 20 ms         |

These constraints are fixed by the Gemini Live API — no other input format is accepted.
Passing stereo or 44.1 kHz audio causes the session to produce garbled or empty output
without returning an error.

### Output (Gemini TTS reply → speaker / file)

| Property     | Value                     |
|--------------|---------------------------|
| Sample rate  | **24 000 Hz** (24 kHz)    |
| Channels     | Mono (1)                  |
| Bit depth    | 16-bit signed integer     |
| Byte order   | Little-endian (s16le)     |

**Critical mismatch:** input is 16 kHz, output is 24 kHz.  Never feed output bytes back
into `send_audio` without resampling; doing so produces chipmunk-pitched or corrupted
audio.  The `wav_utils` module enforces the correct format at read and write time.

---

## First-Chunk Latency

First-chunk latency is measured from the moment `send_realtime_input(audio_stream_end=True)`
is called until the first audio bytes are received from `session.receive()`.

| Run | Input duration | First-chunk latency | Notes |
|-----|---------------|---------------------|-------|
| 1   | 1.8 s         | [TODO: 2026-05-26 — paste actual ms from structured log] | Dev laptop, Mumbai ISP |
| 2   | 1.8 s         | [TODO: 2026-05-26 — paste actual ms from structured log] | Second run |

**Acceptance threshold (Day 3):** < 3 000 ms (integration smoke test).  
**Week 2 target:** < 500 ms end-to-end (requires server-side VAD + streaming, not batch send).

*How to capture real numbers:* Run `make hello-gemini` and grep the structured log output for
`"stage":"first_audio_chunk"`.  Copy the `ms` field value into the table above.*

---

## Available Hindi-Capable Voices

The Gemini Live API exposes prebuilt TTS voices via `SpeechConfig.voice_config`.
All voices below were confirmed to produce intelligible Hindi audio in Day 3 testing.

| Voice    | Character          | Preferred for Hindi? | Notes |
|----------|--------------------|----------------------|-------|
| **Aoede**  | Warm, conversational | **Yes — primary choice** | Most natural prosody in Hindi; good pace for rural callers unfamiliar with AI voices |
| **Charon** | Deeper, neutral      | Secondary choice     | Clearer consonants, slightly robotic; good for short transactional replies |
| **Kore**   | Bright, energetic    | Tertiary             | Sounds natural but slightly too fast for first-time users |
| Fenrir   | Authoritative        | Not recommended      | Accent feels mismatched for hi-IN content |
| Puck     | Playful, light       | Not recommended      | Too casual for a customer-service bot |

**Recommendation:** Use `Aoede` as the default (`DEFAULT_VOICE` in `constants.py`).
Switch to `Charon` if the deployment context is transactional (IVR menus, confirmations).

---

## Setup-Message Structure

A Gemini Live session is configured by passing a `LiveConnectConfig` to
`client.aio.live.connect(model=..., config=...)`.  Below is the minimal structure used
in this project.

### Minimal example (JSON representation)

```json
{
  "response_modalities": ["AUDIO"],
  "speech_config": {
    "voice_config": {
      "prebuilt_voice_config": {
        "voice_name": "Aoede"
      }
    }
  },
  "system_instruction": {
    "role": "user",
    "parts": [
      {
        "text": "You are a helpful assistant. Always respond in the language matching BCP-47 tag 'hi-IN'."
      }
    ]
  }
}
```

### SDK equivalent (Python)

```python
from google.genai import types as genai_types

config = genai_types.LiveConnectConfig(
    response_modalities=[genai_types.Modality.AUDIO],
    speech_config=genai_types.SpeechConfig(
        voice_config=genai_types.VoiceConfig(
            prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(voice_name="Aoede")
        )
    ),
    system_instruction=genai_types.Content(
        parts=[genai_types.Part(text="...system prompt...")],
        role="user",
    ),
)
```

Key points:
- `response_modalities=["AUDIO"]` — omitting this causes the model to return text only.
- `system_instruction.role` must be `"user"` (not `"system"`); the SDK validates this.
- The system instruction is the correct place to anchor the language.  A BCP-47 tag in
  the instruction (`hi-IN`) is more reliable than relying on the model to auto-detect
  language from audio alone.

---

## Things That Surprised Us

1. **Input/output sample-rate asymmetry.** The Live API accepts 16 kHz but returns 24 kHz.
   The SDK documentation does not prominently call this out; we discovered it when the
   output WAV played back at the wrong pitch.

2. **`session.send()` is deprecated.** SDK v1.x examples (most of the internet) use
   `session.send(...)`.  This method no longer works with current Live servers (v2.x).
   The correct split is:
   - `send_realtime_input(audio=Blob(...))` for streaming audio frames.
   - `send_realtime_input(audio_stream_end=True)` to signal turn end.
   - `send_client_content(turns=Content(...), turn_complete=True)` for text turns.

3. **`system_instruction.role` must be `"user"`.** Using `"system"` raises a validation
   error inside the SDK.  This is counterintuitive but is the current API contract.

4. **First audio chunk vs. full-turn latency.** The model starts streaming audio before
   the turn is complete.  Measuring only `total_ms` (time until `turn_complete=True`)
   overstates the felt latency significantly; first-chunk latency is the right metric.

5. **VAD is server-side in Live sessions.** We don't need to run VAD locally — the server
   detects end-of-speech.  However, for pre-recorded audio (as in `hello_gemini.py`),
   we must explicitly call `send_realtime_input(audio_stream_end=True)` to trigger
   the model reply; server-side VAD alone is not sufficient.

---

## Things to Revisit

| Item | Priority | Target |
|------|----------|--------|
| Measure actual first-chunk latency on a stable connection and fill in the table above | High | Day 3 close |
| Tune system prompt for rural Hindi dialect (Bihari/Bhojpuri vocabulary) | Medium | Week 2 |
| Evaluate `gemini-2.5-flash-preview-native-audio-dialog` for better prosody | Medium | Week 2 |
| Add server-side VAD passthrough so callers can interrupt (barge-in) | High | Day 5 (LiveKit integration) |
| Resampling pipeline: if output audio ever needs to be fed back, add a `scipy.signal.resample` step | Low | Week 2 |
| Cost baseline: log bytes sent/received per session to model the ₹/min estimate | Medium | Day 4 |
