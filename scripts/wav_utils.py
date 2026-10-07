"""wav_utils — WAV I/O helpers for the voicebot scripts layer.

This module understands the two distinct PCM formats used in the Gemini Live pipeline:

  Input  (microphone / WAV file → Gemini):  16 kHz, mono, s16le  (PCM signed 16-bit LE)
  Output (Gemini TTS reply → speaker/file): 24 kHz, mono, s16le

⚠ Sample-rate mismatch — a common stumbling block
  Gemini Live *accepts* audio at 16 kHz but *returns* audio at 24 kHz.
  Never feed output bytes back as input without resampling: you will get
  chipmunk-pitched or mangled audio.  Always use the correct helper for each direction.

Helper summary
--------------
load_pcm_mono_16k(path)       → bytes   Read + validate an input WAV (16 kHz mono s16le).
write_pcm_mono_24k(path, data)          Write raw PCM bytes as a 24 kHz mono WAV.
"""

from __future__ import annotations

import wave
from pathlib import Path

_INPUT_RATE: int = 16_000  # Hz  — Gemini Live required INPUT sample rate
_OUTPUT_RATE: int = 24_000  # Hz  — Gemini Live TTS OUTPUT sample rate
_SAMPLE_WIDTH: int = 2  # bytes per sample — 16-bit PCM


def load_pcm_mono_16k(path: str | Path) -> bytes:
    """Read a WAV file and return its raw PCM bytes after validating the format.

    The file must be 16 kHz, mono, 16-bit signed little-endian PCM — the only
    audio format accepted by the Gemini Live API as input.

    Args:
        path: Path to the input WAV file.

    Returns:
        Raw PCM bytes (s16le, 16 kHz, mono).

    Raises:
        FileNotFoundError: The file does not exist.
        ValueError: The file does not match the required format.  The message
            includes an ``ffmpeg`` one-liner to fix the issue.
    """
    path = Path(path)
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        sampwidth = wf.getsampwidth()

        if channels != 1:
            raise ValueError(
                f"{path}: expected mono (1 channel), got {channels} channels.\n"
                "Fix: ffmpeg -i input.wav -ac 1 output.wav"
            )
        if rate != _INPUT_RATE:
            raise ValueError(
                f"{path}: expected {_INPUT_RATE} Hz sample rate, got {rate} Hz.\n"
                f"Fix: ffmpeg -i input.wav -ar {_INPUT_RATE} output.wav"
            )
        if sampwidth != _SAMPLE_WIDTH:
            raise ValueError(
                f"{path}: expected 16-bit PCM (2 bytes/sample), "
                f"got {sampwidth * 8}-bit.\n"
                "Fix: ffmpeg -i input.wav -acodec pcm_s16le output.wav"
            )

        return wf.readframes(wf.getnframes())


def write_pcm_mono_24k(path: str | Path, data: bytes) -> None:
    """Write raw PCM bytes to a WAV file at 24 kHz mono (Gemini Live output format).

    Args:
        path: Destination file path.  Parent directory must already exist.
        data: Raw PCM s16le bytes at 24 kHz mono, as returned by Gemini Live.
    """
    path = Path(path)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(_SAMPLE_WIDTH)
        wf.setframerate(_OUTPUT_RATE)
        wf.writeframes(data)
