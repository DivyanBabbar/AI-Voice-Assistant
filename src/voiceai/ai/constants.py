"""voiceai.ai.constants — Shared constants for the Gemini Live AI module.

Audio format constants reflect Gemini Live's fixed wire format:
  Input  (microphone / WAV → Gemini):  16 kHz, mono, PCM s16le
  Output (Gemini TTS reply → speaker):  24 kHz, mono, PCM s16le

Model and voice defaults are kept here so scripts and tests stay in sync
with the production client configuration without hard-coding strings in
multiple places.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Audio format — Gemini Live wire spec
# ---------------------------------------------------------------------------

INPUT_SAMPLE_RATE_HZ: int = 16_000
"""Sample rate for audio sent *to* Gemini Live.  Fixed by the API."""

OUTPUT_SAMPLE_RATE_HZ: int = 24_000
"""Sample rate for audio received *from* Gemini Live TTS.  Fixed by the API."""

PCM_SAMPLE_WIDTH_BYTES: int = 2
"""Bytes per sample for signed 16-bit PCM (s16le)."""

FRAME_DURATION_MS: int = 20
"""Target frame duration for streaming audio, in milliseconds."""

FRAME_SIZE_BYTES: int = INPUT_SAMPLE_RATE_HZ * PCM_SAMPLE_WIDTH_BYTES * FRAME_DURATION_MS // 1_000
"""Byte length of one 20 ms audio frame at 16 kHz s16le mono (= 640 bytes)."""

# ---------------------------------------------------------------------------
# Gemini Live model and conversation defaults
# ---------------------------------------------------------------------------

DEFAULT_MODEL: str = "models/gemini-2.0-flash-live-001"
"""Default Gemini Live model (GA).  Day 3 also tested ``gemini-3.1-flash-live-preview``.
Must support ``bidiGenerateContent``."""

DEFAULT_VOICE: str = "Aoede"
"""Default prebuilt TTS voice.  Aoede is the most natural-sounding Hindi option
observed during Day 3 evaluation (see docs/notes/day-3-gemini-live-learnings.md)."""

DEFAULT_LANGUAGE_CODE: str = "hi-IN"
"""BCP-47 language tag for the default Hindi (India) conversation."""

# ---------------------------------------------------------------------------
# Retry policy for transient errors
# ---------------------------------------------------------------------------

RETRY_MAX_ATTEMPTS: int = 4
"""Maximum number of send attempts before propagating a transient error."""

RETRY_WAIT_MIN_S: float = 0.5
"""Minimum wait (seconds) before the first retry."""

RETRY_WAIT_MAX_S: float = 8.0
"""Maximum wait (seconds) for any single retry backoff."""

RETRY_MULTIPLIER: float = 0.5
"""Exponential-backoff multiplier applied to successive retry waits."""
