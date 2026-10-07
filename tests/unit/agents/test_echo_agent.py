"""Unit tests for voiceai.agents.echo_agent.

All LiveKit rtc objects are mocked so the tests run without real audio hardware,
a running LiveKit server, or any C extension involvement beyond the module import.

Tests cover:
- Frames read from a remote track are written to the AudioSource (frames-in == frames-out).
- Multiple frames are all forwarded.
- The echo task exits cleanly when the stream ends (StopAsyncIteration).
- Cancellation of the echo task does not raise an unhandled exception.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voiceai.agents.echo_agent import (
    NUM_CHANNELS,
    SAMPLE_RATE,
    SAMPLES_PER_CHANNEL,
    _echo_track,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_frame_event(
    frame_data: bytes = b"\x00" * (SAMPLES_PER_CHANNEL * NUM_CHANNELS * 2),
) -> MagicMock:
    """Return a fake AudioFrameEvent with a mock AudioFrame payload."""
    frame = MagicMock(name="AudioFrame")
    frame.data = frame_data
    event = MagicMock(name="AudioFrameEvent")
    event.frame = frame
    return event


async def _stream_of(*events: MagicMock) -> AsyncIterator[MagicMock]:
    """Async generator that yields the given events then stops."""
    for event in events:
        yield event


# ---------------------------------------------------------------------------
# _echo_track — core pass-through logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_frame_forwarded() -> None:
    """A single audio frame received from the track is written to the source."""
    event = _make_frame_event()
    source = AsyncMock()
    log = MagicMock()
    track = MagicMock()

    with patch("voiceai.agents.echo_agent.rtc.AudioStream", return_value=_stream_of(event)):
        await _echo_track(track, source, log)

    # Exactly one frame must have been forwarded.
    source.capture_frame.assert_awaited_once_with(event.frame)


@pytest.mark.asyncio
async def test_multiple_frames_all_forwarded() -> None:
    """Every frame in the stream is forwarded — order is preserved."""
    events = [_make_frame_event(bytes([i] * 4)) for i in range(5)]
    source = AsyncMock()
    log = MagicMock()
    track = MagicMock()

    with patch("voiceai.agents.echo_agent.rtc.AudioStream", return_value=_stream_of(*events)):
        await _echo_track(track, source, log)

    assert source.capture_frame.await_count == 5
    for i, call in enumerate(source.capture_frame.await_args_list):
        assert call.args[0] is events[i].frame


@pytest.mark.asyncio
async def test_empty_stream_no_frames_forwarded() -> None:
    """An empty stream (participant muted immediately) forwards no frames."""
    source = AsyncMock()
    log = MagicMock()
    track = MagicMock()

    with patch("voiceai.agents.echo_agent.rtc.AudioStream", return_value=_stream_of()):
        await _echo_track(track, source, log)

    source.capture_frame.assert_not_awaited()


@pytest.mark.asyncio
async def test_echo_task_cancelled_cleanly() -> None:
    """Cancelling the echo task raises CancelledError — no other exception."""

    async def _infinite_stream(*_: object, **__: object) -> AsyncIterator[MagicMock]:
        while True:
            yield _make_frame_event()
            await asyncio.sleep(0)

    source = AsyncMock()
    log = MagicMock()
    track = MagicMock()

    with patch("voiceai.agents.echo_agent.rtc.AudioStream", side_effect=_infinite_stream):
        task = asyncio.create_task(_echo_track(track, source, log))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


def test_audio_constants_are_sane() -> None:
    """Verify the audio format constants are within expected ranges."""
    assert SAMPLE_RATE == 48_000, "LiveKit default sample rate is 48 kHz"
    assert NUM_CHANNELS == 1, "Mono audio for voice"
    # 20 ms at 48 kHz → 960 samples
    assert SAMPLES_PER_CHANNEL == SAMPLE_RATE // 50, "960 samples = 20 ms frame"
