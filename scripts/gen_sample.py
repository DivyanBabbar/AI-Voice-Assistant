"""gen_sample.py — Generate the fixture WAV clip used for hello-world testing.

Produces ``scripts/samples/hello.wav``: a ~2-second 16 kHz mono PCM s16le WAV
of a Hindi voice saying "नमस्ते, आप कैसे हैं?" ("Namaste, how are you?").

This script is a **dev-only fixture generator** — it is NOT part of the
runtime path.  Run it once to regenerate the fixture after deleting it.

macOS implementation (default)
-------------------------------
1. ``say -v Lekha`` — macOS built-in Hindi TTS voice (System Preferences →
   Accessibility → Spoken Content → System Voice: Lekha must be downloaded).
2. ``afconvert`` — macOS CoreAudio file converter, converts CAF→WAV at 16 kHz.

Both tools are pre-installed on macOS; no extra dependencies are required.

Alternative (non-macOS / CI)
-----------------------------
Install gTTS and ffmpeg, then adapt this script::

    pip install gTTS
    brew install ffmpeg   # or: apt-get install ffmpeg

    from gtts import gTTS
    import subprocess, tempfile
    tts = gTTS("नमस्ते, आप कैसे हैं?", lang="hi")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tts.save(f.name)
        subprocess.run(
            ["ffmpeg", "-y", "-i", f.name, "-ar", "16000", "-ac", "1",
             "-acodec", "pcm_s16le", str(OUT_PATH)],
            check=True,
        )

Usage::

    poetry run python scripts/gen_sample.py
    # produces: scripts/samples/hello.wav
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_OUT_PATH = _SCRIPT_DIR / "samples" / "hello.wav"
_HINDI_TEXT = "नमस्ते, आप कैसे हैं?"
_LEKHA_VOICE = "Lekha"  # macOS built-in Hindi TTS voice (hi_IN)
_TARGET_RATE = 16_000


def _check_tool(name: str) -> None:
    """Abort with a helpful message if a required system tool is missing.

    Args:
        name: Executable name to look for on PATH.

    Raises:
        SystemExit: If the tool is not found.
    """
    result = subprocess.run(["which", name], capture_output=True)
    if result.returncode != 0:
        print(f"Error: '{name}' not found on PATH.", file=sys.stderr)
        print(
            "This script requires macOS 'say' and 'afconvert'. "
            "See the module docstring for a gTTS+ffmpeg alternative.",
            file=sys.stderr,
        )
        sys.exit(1)


def generate(out_path: Path = _OUT_PATH) -> None:
    """Generate a 16 kHz mono WAV fixture using macOS native TTS tools.

    Steps:
      1. Generate a CAF file with ``say -v Lekha``.
      2. Convert CAF → 16 kHz mono s16le WAV with ``afconvert``.
      3. Validate the output with :mod:`wave`.

    Args:
        out_path: Destination for the generated WAV file.

    Raises:
        SystemExit: If ``say`` or ``afconvert`` are absent or return a non-zero
            exit code.
    """
    _check_tool("say")
    _check_tool("afconvert")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".caf", delete=False) as tmp:
        caf_path = Path(tmp.name)

    try:
        print(f"Generating speech: '{_HINDI_TEXT}'  (voice: {_LEKHA_VOICE})")
        subprocess.run(
            ["say", "-v", _LEKHA_VOICE, _HINDI_TEXT, "-o", str(caf_path)],
            check=True,
        )

        print(f"Converting CAF → 16 kHz mono WAV → {out_path}")
        # LEI16 = Little-Endian 16-bit signed integer PCM (s16le)
        subprocess.run(
            [
                "afconvert",
                "-f",
                "WAVE",
                "-d",
                f"LEI16@{_TARGET_RATE}",
                "-c",
                "1",
                str(caf_path),
                str(out_path),
            ],
            check=True,
        )
    finally:
        caf_path.unlink(missing_ok=True)

    # Validate the output
    with wave.open(str(out_path), "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        duration = wf.getnframes() / rate

    print(f"OK — {out_path.name}: {channels} ch, {rate} Hz, {duration:.2f} s")
    if channels != 1 or rate != _TARGET_RATE:
        print(
            f"Warning: unexpected format — expected 1 ch / {_TARGET_RATE} Hz, "
            f"got {channels} ch / {rate} Hz",
            file=sys.stderr,
        )


if __name__ == "__main__":
    generate()
