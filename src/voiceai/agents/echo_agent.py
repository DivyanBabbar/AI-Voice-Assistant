"""agents.echo_agent — LiveKit echo agent: subscriber audio in → agent audio out.

No STT or TTS is involved.  Every AudioFrame received from a remote participant
is immediately written back to the agent's outbound AudioSource.  This serves
two purposes:

1. End-to-end audio quality verification — confirms the full media path
   (browser → LiveKit → agent → LiveKit → browser) carries audio correctly.
2. Roundtrip latency measurement — the timestamp difference between speaking
   and hearing the echo gives a reliable local RTC latency figure.

Audio format (matching LiveKit defaults — no resampling required):
- Sample rate  : 48 000 Hz
- Channels     : 1 (mono)
- Frame size   : 960 samples = 20 ms per frame (standard WebRTC interval)
"""

from __future__ import annotations

import asyncio

import structlog
from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli

from voiceai.observability.logging import get_logger

# ---------------------------------------------------------------------------
# Audio constants
# ---------------------------------------------------------------------------

# LiveKit sends and receives PCM audio at 48 kHz mono by default.
SAMPLE_RATE: int = 48_000
NUM_CHANNELS: int = 1
# 960 samples @ 48 kHz = 20 ms — the standard WebRTC frame duration.
SAMPLES_PER_CHANNEL: int = 960


# ---------------------------------------------------------------------------
# Per-track echo coroutine
# ---------------------------------------------------------------------------


async def _echo_track(
    track: rtc.RemoteAudioTrack,
    source: rtc.AudioSource,
    log: structlog.stdlib.BoundLogger,
) -> None:
    """Drain an audio track and write every frame back to *source*.

    Runs as a long-lived asyncio Task — one per subscribed remote track.
    Exits when the track ends (``StopAsyncIteration``) or is cancelled.

    Args:
        track:  The remote audio track to subscribe to.
        source: The local AudioSource to write frames into.  All echo tasks
                for the same room share one source so the agent has a single
                outbound track.
        log:    Bound logger (already carries room/participant context).
    """
    # AudioStream is an async iterator that yields AudioFrameEvent objects.
    # It does not block the event loop between frames — the C extension
    # delivers frames through a queue and this coroutine simply awaits them.
    audio_stream = rtc.AudioStream(
        track,
        sample_rate=SAMPLE_RATE,
        num_channels=NUM_CHANNELS,
    )
    async for event in audio_stream:
        # capture_frame is async; it writes the PCM frame into the source's
        # internal buffer, from where LiveKit's RTC stack reads and sends it.
        await source.capture_frame(event.frame)

    log.info("echo_track_ended", track_sid=track.sid)


def _spawn_echo(
    track: rtc.RemoteAudioTrack,
    participant: rtc.RemoteParticipant,
    source: rtc.AudioSource,
    log: structlog.stdlib.BoundLogger,
    tasks: list[asyncio.Task[None]],
) -> None:
    """Start an echo task for *track* and append it to *tasks*.

    Args:
        track:       The remote audio track to echo.
        participant: The remote participant who owns the track.
        source:      Shared AudioSource for the agent's outbound track.
        log:         Logger to bind participant context to.
        tasks:       Mutable list that collects all running echo tasks.
    """
    bound = log.bind(participant=participant.identity, track_sid=track.sid)
    bound.info("echo_started")
    tasks.append(asyncio.ensure_future(_echo_track(track, source, bound)))


def _subscribe_existing(
    room: rtc.Room,
    source: rtc.AudioSource,
    log: structlog.stdlib.BoundLogger,
    tasks: list[asyncio.Task[None]],
) -> None:
    """Subscribe to audio tracks from participants already in the room.

    The agent may join after participants are already present; this function
    handles tracks that were published before the agent connected.

    Args:
        room:   The LiveKit Room handle.
        source: Shared AudioSource for the agent's outbound track.
        log:    Logger for the current room session.
        tasks:  Mutable list that collects all running echo tasks.
    """
    for participant in room.remote_participants.values():
        for pub in participant.track_publications.values():
            track = pub.track
            if pub.subscribed and track and track.kind == rtc.TrackKind.KIND_AUDIO:
                assert isinstance(track, rtc.RemoteAudioTrack)
                _spawn_echo(track, participant, source, log, tasks)


# ---------------------------------------------------------------------------
# Agent entrypoint
# ---------------------------------------------------------------------------


async def entrypoint(ctx: JobContext) -> None:
    """LiveKit agent entrypoint: connect to the room and echo all audio.

    The livekit-agents Worker calls this coroutine once per dispatched Job.
    The function runs until the room disconnects, then returns so the Worker
    can clean up the process.

    Args:
        ctx: The JobContext provided by the livekit-agents Worker.  Carries
             the room handle and connection helpers.
    """
    log = get_logger(__name__)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    log.info("echo_agent_connected", room=ctx.room.name)

    # Create one shared AudioSource for all echoed frames.  Publishing a
    # single track keeps the agent's participant entry clean in the room.
    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
    local_track = rtc.LocalAudioTrack.create_audio_track("echo-track", source)

    # SOURCE_MICROPHONE tells LiveKit to treat this track as a mic stream
    # (not a screen-share or file playback), which matters for participant UI.
    publish_opts = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await ctx.room.local_participant.publish_track(local_track, publish_opts)
    log.info("echo_track_published", room=ctx.room.name)

    echo_tasks: list[asyncio.Task[None]] = []

    @ctx.room.on("track_subscribed")
    def _on_track_subscribed(
        track: rtc.Track,
        _pub: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            assert isinstance(track, rtc.RemoteAudioTrack)
            _spawn_echo(track, participant, source, log, echo_tasks)

    @ctx.room.on("participant_disconnected")
    def _on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
        log.info("participant_disconnected", participant=participant.identity)

    _subscribe_existing(ctx.room, source, log, echo_tasks)

    disconnected = asyncio.Event()

    @ctx.room.on("disconnected")
    def _on_disconnected(*_: object) -> None:
        disconnected.set()

    try:
        await disconnected.wait()
    finally:
        for task in echo_tasks:
            task.cancel()
        if echo_tasks:
            await asyncio.gather(*echo_tasks, return_exceptions=True)
        log.info("echo_agent_stopped", room=ctx.room.name)


# ---------------------------------------------------------------------------
# Standalone entry (used by runner.py via cli.run_app)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
