"""Integration smoke test for the Gemini Live end-to-end pipeline.

Exercises the full path:
  input WAV → GeminiLiveClient → audio reply → output WAV

Skipped by default to avoid making real API calls in CI.
Enable by setting ``RUN_INTEGRATION=1`` in the environment.

Example::

    RUN_INTEGRATION=1 poetry run pytest tests/integration/ai/test_gemini_live_smoke.py -v
"""

from __future__ import annotations

import os
import sys
import time
import wave
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Allow importing wav_utils from scripts/ without installing it as a package.
sys.path.insert(0, str(Path(__file__).parents[3] / "scripts"))

from wav_utils import load_pcm_mono_16k, write_pcm_mono_24k  # noqa: E402

from voiceai.ai.constants import FRAME_SIZE_BYTES  # noqa: E402
from voiceai.ai.gemini_live_client import GeminiLiveClient  # noqa: E402

load_dotenv()

pytestmark = pytest.mark.integration

_SAMPLE_WAV = Path(__file__).parents[3] / "scripts" / "samples" / "hello.wav"
_SYSTEM_PROMPT = "You are a friendly Hindi-speaking assistant. Always reply in Hindi."
_MAX_FIRST_CHUNK_LATENCY_MS = 3_000  # p95 observed ≈ 400–800 ms; 3 s is a generous ceiling


@pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION"),
    reason="Set RUN_INTEGRATION=1 to run integration tests (makes real Gemini API calls)",
)
@pytest.mark.asyncio
async def test_gemini_live_smoke(tmp_path: Path) -> None:
    """Full end-to-end smoke test: stream Hindi WAV → receive audio reply.

    Assertions:
    - Output file exists and is non-empty.
    - Output WAV duration > 0.5 s.
    - First-audio-chunk latency < 2000 ms.

    Args:
        tmp_path: pytest-provided temporary directory for output file.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    assert api_key, "GOOGLE_API_KEY must be set to run integration tests"
    assert _SAMPLE_WAV.exists(), (
        f"Sample WAV not found at {_SAMPLE_WAV}. " "Run: poetry run python scripts/gen_sample.py"
    )

    pcm_data = load_pcm_mono_16k(_SAMPLE_WAV)
    frames = [pcm_data[i : i + FRAME_SIZE_BYTES] for i in range(0, len(pcm_data), FRAME_SIZE_BYTES)]

    output_path = tmp_path / "reply.wav"
    audio_chunks: list[bytes] = []
    first_chunk_ms: float | None = None

    async with GeminiLiveClient(
        api_key=api_key,
        system_instruction=_SYSTEM_PROMPT,
    ) as client:
        for frame in frames:
            await client.send_audio(frame)
        await client.send_end_of_turn()

        t_recv = time.monotonic()
        async for chunk in client.receive():
            if chunk.audio:
                if first_chunk_ms is None:
                    first_chunk_ms = (time.monotonic() - t_recv) * 1_000
                audio_chunks.append(chunk.audio)
            if chunk.is_final:
                break

    assert audio_chunks, "Gemini returned no audio chunks"
    all_audio = b"".join(audio_chunks)
    write_pcm_mono_24k(output_path, all_audio)

    # Assert output file exists and is non-empty.
    assert output_path.exists(), "Output WAV was not written"
    assert output_path.stat().st_size > 0, "Output WAV is empty"

    # Assert duration > 0.5 s (24 kHz s16le: 24000 * 2 bytes per second).
    with wave.open(str(output_path), "rb") as wf:
        duration_s = wf.getnframes() / wf.getframerate()
    assert duration_s > 0.5, f"Reply too short: {duration_s:.3f} s (expected > 0.5 s)"

    # Assert first-chunk latency is within the acceptance threshold.
    assert first_chunk_ms is not None, "No audio chunk was received"
    assert first_chunk_ms < _MAX_FIRST_CHUNK_LATENCY_MS, (
        f"First-chunk latency {first_chunk_ms:.0f} ms exceeds "
        f"{_MAX_FIRST_CHUNK_LATENCY_MS} ms threshold"
    )
