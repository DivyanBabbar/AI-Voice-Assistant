"""hello_gemini.py — End-to-end hello-world for Gemini Live.

Loads a 16 kHz mono WAV file, streams it to the Gemini Live API, and saves
the 24 kHz mono audio reply to disk.  Every stage is logged via structlog with
a per-run ``trace_id`` (uuid4).  Per-stage latency is emitted as structured
fields (``stage``, ``ms``) so the output is grep-friendly for quick analysis.

Usage::

    poetry run python scripts/hello_gemini.py \\
        --input scripts/samples/hello.wav \\
        --output /tmp/reply.wav

    # With a custom system prompt:
    poetry run python scripts/hello_gemini.py \\
        --input scripts/samples/hello.wav \\
        --output /tmp/reply.wav \\
        --system-prompt "You are a pirate. Speak only in Hindi."
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

# Allow importing wav_utils from the same scripts/ directory without installing it.
sys.path.insert(0, str(Path(__file__).parent))

import structlog
import structlog.contextvars
from dotenv import load_dotenv
from wav_utils import load_pcm_mono_16k, write_pcm_mono_24k

from voiceai.ai.constants import (
    DEFAULT_MODEL,
    FRAME_SIZE_BYTES,
    INPUT_SAMPLE_RATE_HZ,
    OUTPUT_SAMPLE_RATE_HZ,
    PCM_SAMPLE_WIDTH_BYTES,
)
from voiceai.ai.gemini_live_client import (
    GeminiAuthError,
    GeminiLiveClient,
    GeminiRateLimitError,
    GeminiTransientError,
)
from voiceai.observability.logging import configure_logging

_DEFAULT_SYSTEM_PROMPT: str = "You are a friendly Hindi-speaking assistant. Always reply in Hindi."


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured :class:`argparse.ArgumentParser`.
    """
    p = argparse.ArgumentParser(
        description="Stream a WAV file to Gemini Live and save the audio reply."
    )
    p.add_argument(
        "--input",
        required=True,
        type=Path,
        metavar="WAV",
        help="Path to a 16 kHz mono PCM s16le WAV file (input audio).",
    )
    p.add_argument(
        "--output",
        required=True,
        type=Path,
        metavar="WAV",
        help="Destination path for the 24 kHz mono WAV reply from Gemini.",
    )
    p.add_argument(
        "--system-prompt",
        default=_DEFAULT_SYSTEM_PROMPT,
        metavar="TEXT",
        help=f"System instruction for the model. Default: '{_DEFAULT_SYSTEM_PROMPT}'",
    )
    return p


def _load_input(path: Path, log: structlog.stdlib.BoundLogger) -> tuple[bytes, list[bytes]]:
    """Load and validate the input WAV; return raw PCM bytes and 20-ms frames.

    Args:
        path: Path to the input WAV file.
        log: Bound structlog logger for this run.

    Returns:
        Tuple of (raw_pcm_bytes, list_of_20ms_frames).

    Raises:
        SystemExit: If the file is missing or its format is invalid.
    """
    log.info("loading_input", path=str(path))
    try:
        pcm_data = load_pcm_mono_16k(path)
    except FileNotFoundError as exc:
        log.error("input_not_found", path=str(path), error=str(exc))
        print(f"\nError: {exc}", file=sys.stderr)
        print(
            "Next step: run  poetry run python scripts/gen_sample.py  to create a sample clip.",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValueError as exc:
        log.error("input_format_invalid", path=str(path), error=str(exc))
        print(f"\nFormat error: {exc}", file=sys.stderr)
        print(
            "Next step: use ffmpeg or afconvert to produce a 16 kHz mono s16le WAV.",
            file=sys.stderr,
        )
        sys.exit(1)

    frames = [pcm_data[i : i + FRAME_SIZE_BYTES] for i in range(0, len(pcm_data), FRAME_SIZE_BYTES)]
    duration_s = len(pcm_data) / (INPUT_SAMPLE_RATE_HZ * PCM_SAMPLE_WIDTH_BYTES)
    log.info("input_loaded", frames=len(frames), duration_s=round(duration_s, 3))
    return pcm_data, frames


async def _stream_and_collect(
    client: GeminiLiveClient,
    frames: list[bytes],
    log: structlog.stdlib.BoundLogger,
) -> list[bytes]:
    """Stream audio frames, signal end-of-turn, then collect the audio reply.

    Args:
        client: An open :class:`GeminiLiveClient`.
        frames: List of 20-ms PCM chunks to send.
        log: Bound structlog logger for this run.

    Returns:
        List of raw audio bytes from Gemini's reply (each chunk appended in order).
    """
    t_send_start = time.monotonic()
    for frame in frames:
        await client.send_audio(frame)
    await client.send_end_of_turn()
    send_ms = round((time.monotonic() - t_send_start) * 1_000, 1)
    log.info("audio_sent", stage="audio_sent", frames=len(frames), ms=send_ms)

    audio_chunks: list[bytes] = []
    first_chunk_logged = False
    t_recv_start = time.monotonic()

    async for chunk in client.receive():
        if chunk.audio:
            if not first_chunk_logged:
                first_ms = round((time.monotonic() - t_recv_start) * 1_000, 1)
                log.info("latency_event", stage="first_audio_chunk", ms=first_ms)
                first_chunk_logged = True
            audio_chunks.append(chunk.audio)
        if chunk.is_final:
            break

    return audio_chunks


async def run(args: argparse.Namespace) -> None:
    """Execute the full send-and-receive cycle against the Gemini Live API.

    Args:
        args: Parsed CLI arguments with ``input``, ``output``, and
            ``system_prompt`` attributes.

    Raises:
        SystemExit: On any failure (auth, network, empty reply, bad input).
    """
    log = structlog.get_logger()
    t_start = time.monotonic()

    _, frames = _load_input(args.input, log)

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        log.error("missing_api_key")
        print("\nError: GOOGLE_API_KEY is not set.", file=sys.stderr)
        print(
            "Next step: add  GOOGLE_API_KEY=<your-key>  to your .env file. "
            "Get a key at https://aistudio.google.com/apikey",
            file=sys.stderr,
        )
        sys.exit(1)

    log.info("opening_session", model=DEFAULT_MODEL)
    try:
        async with GeminiLiveClient(
            api_key=api_key,
            system_instruction=args.system_prompt,
        ) as client:
            audio_chunks = await _stream_and_collect(client, frames, log)
    except GeminiAuthError as exc:
        log.error("auth_error", error=str(exc), exc_info=True)
        print(f"\nAuth error: {exc}", file=sys.stderr)
        print(
            "Next step: verify GOOGLE_API_KEY is valid — https://aistudio.google.com/apikey",
            file=sys.stderr,
        )
        sys.exit(1)
    except GeminiRateLimitError as exc:
        log.error("rate_limit_error", error=str(exc), exc_info=True)
        print(f"\nRate limit: {exc}", file=sys.stderr)
        print(
            "Next step: wait a moment and retry, or check your quota "
            "at https://console.cloud.google.com/iam-admin/quotas",
            file=sys.stderr,
        )
        sys.exit(1)
    except GeminiTransientError as exc:
        log.error("transient_error", error=str(exc), exc_info=True)
        print(f"\nNetwork error: {exc}", file=sys.stderr)
        print(
            "Next step: check your connection and retry. "
            "The client retries transient errors automatically (up to 4 attempts).",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:
        log.error("unexpected_error", error=str(exc), exc_info=True)
        print(f"\nUnexpected error: {exc}", file=sys.stderr)
        print("Next step: review the structured log output above for details.", file=sys.stderr)
        sys.exit(1)

    all_audio = b"".join(audio_chunks)
    if not all_audio:
        log.error("empty_reply")
        print(
            "\nError: Gemini returned no audio. Try adjusting the system prompt or input clip.",
            file=sys.stderr,
        )
        sys.exit(1)

    write_pcm_mono_24k(args.output, all_audio)

    output_duration_s = len(all_audio) / (OUTPUT_SAMPLE_RATE_HZ * PCM_SAMPLE_WIDTH_BYTES)
    total_ms = round((time.monotonic() - t_start) * 1_000, 1)
    log.info(
        "run_complete",
        output_path=str(args.output),
        output_duration_s=round(output_duration_s, 3),
        total_ms=total_ms,
    )
    print(
        f"\nDone.  Reply saved to {args.output}  "
        f"({output_duration_s:.2f} s audio, {total_ms} ms total)"
    )


def main() -> None:
    """Entry point: load .env, configure logging, bind trace_id, then run.

    Raises:
        SystemExit: Propagated from :func:`run` on any error.
    """
    load_dotenv()
    configure_logging()

    args = _build_arg_parser().parse_args()
    structlog.contextvars.bind_contextvars(trace_id=str(uuid.uuid4()))

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
