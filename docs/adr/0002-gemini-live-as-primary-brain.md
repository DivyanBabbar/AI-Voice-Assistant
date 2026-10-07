# ADR-0002: Use Gemini 2.0/2.5 Flash Live as the primary conversation brain

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Arnav Adarsh

---

## Context

The hindi-voice-ai platform must handle real-time, bidirectional voice conversations in
Hindi over PSTN calls.  The core latency target is < 2 s round-trip on a 2G/3G connection
(the typical network quality for the target rural India user base).

The system requires three capabilities in a single pipeline:
1. **Automatic Speech Recognition (ASR)** — Hindi audio → text.
2. **Dialogue / LLM reasoning** — generate a contextually appropriate reply.
3. **Text-to-Speech (TTS)** — reply text → Hindi audio.

We evaluated four approaches:

### Option A — Sarvam 3-step pipeline (Sarvam ASR → LLM → Sarvam TTS)

Sarvam AI offers a Hindi-first ASR and TTS API optimised for Indian languages and accents.
Combining it with a separate LLM (e.g. GPT-4o or Claude) gives very high Hindi quality.
Rejected because:
- Three sequential API round-trips add ≥ 800 ms of irreducible network latency on top of
  model inference time; the 2 s target becomes very hard to hit.
- Three separate billing relationships, three SLAs to monitor, and more failure surfaces.
- No streaming partial-response support across the 3-step boundary today.

### Option B — OpenAI Realtime API (GPT-4o Audio)

OpenAI's Realtime API offers integrated ASR + dialogue + TTS over a single WebSocket,
similar to Gemini Live.  Hindi support is present but secondary; prosody and vocabulary
accuracy for rural Hindi dialects is noticeably weaker than Gemini in informal testing.
Cost is higher (approximately $0.06/min input + $0.24/min output vs Gemini's lower rate).
Retained as the **Week 2 fallback** (see Consequences).

### Option C — ElevenLabs conversational AI stack

ElevenLabs provides voice-to-voice conversation agents.  Hindi support is limited and
primarily covers accent-neutralised TTS rather than dialectal comprehension.  The pricing
model and API surface are also less well-suited to telephony integration.  Rejected.

### Option D — Gemini 2.0/2.5 Flash Live (this decision)

Google's Gemini Live API streams bidirectional PCM audio over a persistent WebSocket,
collapsing ASR + reasoning + TTS into a single latency-optimised round-trip.  Key facts
as of Day 3 evaluation (2026-05-26):
- End-to-end first-chunk latency observed: **< 3 000 ms** (acceptance bar); typical
  400–800 ms in informal testing on a stable connection.
- Hindi (`hi-IN`) comprehension is strong; voices `Aoede` and `Charon` produce natural
  Hindi prosody.
- Input: 16 kHz mono PCM s16le.  Output: 24 kHz mono PCM s16le.
- Pricing: approximately ₹1/min (audio input + audio output combined) at current Google
  AI Studio rates, well within the project budget.

## Decision

We will use **Gemini 2.0 Flash Live** (`models/gemini-2.0-flash-live-001`) as the primary
conversation brain, accessed via `GeminiLiveClient` in `src/voiceai/ai/gemini_live_client.py`.

Rejected alternatives:
- **Sarvam 3-step**: too much latency from sequential round-trips.
- **ElevenLabs**: insufficient Hindi dialect support.
- **OpenAI Realtime**: retained as fallback (see below), not primary.

## Consequences

### Positive

- Single WebSocket session replaces three sequential API calls; latency budget is fully
  available for transport (LiveKit/Exotel) rather than inference hops.
- One API key, one billing account, one set of rate-limit quotas to manage.
- Gemini's multilingual model was trained on significantly more Hindi data than most
  western LLMs; comprehension of rural vocabulary and code-switching is noticeably better.
- Streaming output means the TTS audio starts playing before the full reply is generated,
  further reducing perceived latency.

### Negative

- Single point of failure: if Google's Live API has an outage, all calls fail.  Mitigated
  by the OpenAI Realtime fallback planned for Week 2 (see below).
- The 16 kHz → 24 kHz sample-rate asymmetry between input and output is a permanent
  constraint that must be handled in every audio pipeline component.
- Model behaviour (system prompt following, barge-in handling) may drift across Google
  model updates; we are pinned to the `gemini-2.0-flash-live-001` GA identifier to reduce
  this risk.
- Preview models (e.g. `gemini-2.5-flash-preview-native-audio-dialog`) may offer better
  quality but are not suitable for production due to API stability guarantees.

### Neutral / follow-on work

- **Week 2:** Implement OpenAI Realtime API as a hot-standby fallback.  `GeminiLiveClient`
  and the future `OpenAIRealtimeClient` should share the same async interface so the
  LiveKit agent can switch providers without code changes.
- **Day 4:** Instrument per-session byte counts to validate the ₹1/min cost estimate
  against real call traffic.
- **Day 5:** Integrate `GeminiLiveClient` into the LiveKit agent; the client's
  `send_audio` / `receive` interface is already designed for that purpose.
- The `DEFAULT_MODEL` constant in `src/voiceai/ai/constants.py` must be updated
  whenever the team evaluates a new Gemini Live model version.

---

*ADR format adapted from Michael Nygard's original template.*
