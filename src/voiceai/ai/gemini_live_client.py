"""voiceai.ai.gemini_live_client — Async wrapper for the Google Gemini Live API.

Opens a persistent WebSocket session to Gemini Live, streams bidirectional audio
and text, and closes cleanly without leaking sockets.

Key design notes
----------------
* **Audio format**: 16 kHz, 16-bit signed little-endian, mono PCM
  (``audio/pcm;rate=16000``).  This is the only format Gemini Live accepts for
  input audio.  Pass raw bytes; the SDK handles base64 encoding internally.
* **Send methods**: SDK v2.x splits sending into two surfaces:
  - ``session.send_realtime_input(audio=Blob(...))`` — for streaming PCM audio frames.
  - ``session.send_realtime_input(audio_stream_end=True)`` — signals end of user audio.
  - ``session.send_client_content(turns=..., turn_complete=True)`` — for text turns.
  The deprecated ``session.send()`` from SDK v1.x no longer works with current servers.
* **Barge-in**: The ``receive()`` loop yields chunks as they arrive.  If the
  user starts speaking mid-response, the server sets ``turn_complete=True`` on
  the next server-content message.  Callers that want barge-in must cancel
  their consume-loop themselves — this client just surfaces the flag.
* **Retry strategy**: Only ``GeminiTransientError`` (network hiccups, 5xx) is
  retried via tenacity.  Auth/quota errors propagate immediately so operators
  get actionable alerts rather than silent retry storms.
* **Timing**: All elapsed-time measurements use ``time.monotonic()``; this is
  unaffected by NTP clock adjustments that can make ``time.time()`` go backward.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import google.genai as genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from voiceai.ai.constants import (
    DEFAULT_LANGUAGE_CODE,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    INPUT_SAMPLE_RATE_HZ,
    RETRY_MAX_ATTEMPTS,
    RETRY_MULTIPLIER,
    RETRY_WAIT_MAX_S,
    RETRY_WAIT_MIN_S,
)
from voiceai.observability.logging import get_logger


class AIChunk(BaseModel):
    """A single chunk of output received from Gemini Live.

    Attributes:
        audio: Raw PCM bytes from the model's TTS output, or ``None`` if this
            chunk carries text only.
        text: Partial or full transcript text, or ``None`` if audio-only.
        is_final: ``True`` on the last chunk of a model turn (``turn_complete``
            is set on the server-content message).
    """

    audio: bytes | None = None
    text: str | None = None
    is_final: bool = False


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class GeminiAuthError(RuntimeError):
    """Raised when the API key is missing, revoked, or lacks permissions."""


class GeminiRateLimitError(RuntimeError):
    """Raised when the project has exceeded its Gemini Live quota."""


class GeminiTransientError(RuntimeError):
    """Raised on transient failures (5xx, network drop); eligible for retry."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GeminiLiveClient:
    """Async context manager for a Gemini Live session.

    Opens a WebSocket-backed Live session on ``__aenter__``, streams audio and
    text bidirectionally, and closes cleanly on ``__aexit__`` without leaking
    the underlying WebSocket.

    Example::

        async with GeminiLiveClient(api_key=os.environ["GOOGLE_API_KEY"]) as client:
            await client.send_text("नमस्ते, आप कैसे हैं?")
            async for chunk in client.receive():
                if chunk.audio:
                    play(chunk.audio)
                if chunk.is_final:
                    break

    Args:
        api_key: Google AI Studio API key.  Obtain from
            https://aistudio.google.com/apikey.
        model: Gemini model identifier.  Defaults to
            ``"models/gemini-3.1-flash-live-preview"``.  The model must support
            ``bidiGenerateContent``.
        voice: Prebuilt voice name for TTS output (e.g. ``"Aoede"``,
            ``"Charon"``).  Defaults to ``"Aoede"``.
        language_code: BCP-47 language tag for the conversation.  Defaults to
            ``"hi-IN"`` (Hindi, India).  Injected as a system instruction hint.
        system_instruction: Full system instruction text.  When provided, this
            overrides the auto-generated language-anchoring instruction built
            from ``language_code``.  Useful for scripts and integration tests
            that need precise control over the model's persona.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        voice: str = DEFAULT_VOICE,
        language_code: str = DEFAULT_LANGUAGE_CODE,
        system_instruction: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._language_code = language_code
        # Explicit instruction takes precedence over the auto-generated language hint.
        self._system_instruction = system_instruction
        self._log = get_logger(__name__)
        # These are set during __aenter__ and cleared in __aexit__.
        self._genai_client: genai.Client | None = None
        self._session: Any = None  # AsyncSession (SDK type; no public stub)
        self._session_ctx: Any = None  # async context manager from SDK

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> GeminiLiveClient:
        """Open a Gemini Live session.

        Returns:
            ``self`` so callers can write ``async with GeminiLiveClient(...) as c``.

        Raises:
            GeminiAuthError: API key is invalid or revoked.
            GeminiTransientError: Connection failed for a transient reason.
        """
        t0 = time.monotonic()
        self._genai_client = genai.Client(api_key=self._api_key)
        config = self._build_connect_config()
        ctx = self._genai_client.aio.live.connect(model=self._model, config=config)
        try:
            self._session = await ctx.__aenter__()
            self._session_ctx = ctx
        except Exception as exc:
            self._genai_client = None
            raise self._map_exception(exc) from exc
        elapsed_ms = (time.monotonic() - t0) * 1_000
        self._log.info("gemini_session_opened", model=self._model, latency_ms=round(elapsed_ms, 1))
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Close the session and release the underlying WebSocket.

        Args:
            exc_type: Exception class, if any.
            exc_val: Exception instance, if any.
            exc_tb: Traceback, if any.
        """
        if self._session_ctx is not None:
            try:
                await self._session_ctx.__aexit__(exc_type, exc_val, exc_tb)
            except Exception:
                # Swallow close errors; we already have the real exception.
                pass
            finally:
                self._session_ctx = None
                self._session = None
                self._genai_client = None
        self._log.info("gemini_session_closed")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Send a chunk of PCM audio to the live session via realtime input.

        The SDK wraps the blob in the new ``realtime_input.audio`` wire format
        (SDK v2.x) and base64-encodes it for JSON transport.  Pass raw bytes here.

        Args:
            pcm_bytes: Raw PCM s16le audio at ``_SAMPLE_RATE_HZ`` Hz.

        Raises:
            GeminiTransientError: The send failed due to a network error.
        """
        self._assert_open()
        blob = genai_types.Blob(data=pcm_bytes, mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE_HZ}")
        try:
            await self._session.send_realtime_input(audio=blob)
        except Exception as exc:
            raise self._map_exception(exc) from exc

    async def send_end_of_turn(self) -> None:
        """Signal the end of the user's audio turn so the model begins replying.

        Call this after streaming all audio frames for the current turn.  The
        server will begin sending ``AIChunk`` objects on the next ``receive()``
        call once it receives this signal.

        Uses ``audio_stream_end=True`` on the realtime-input channel (SDK v2.x).
        This is the correct signal for VAD-based Live sessions when streaming
        pre-recorded audio rather than live microphone input.

        Raises:
            GeminiTransientError: The signal could not be delivered.
        """
        self._assert_open()
        try:
            await self._session.send_realtime_input(audio_stream_end=True)
        except Exception as exc:
            raise self._map_exception(exc) from exc

    async def send_text(self, text: str) -> None:
        """Send a text turn and signal end-of-turn to the model.

        Useful for testing and for mixed-mode turns where the user dictates
        text rather than audio.

        Args:
            text: UTF-8 text to send (e.g. a transcribed utterance).

        Raises:
            GeminiAuthError: API key issue surfaced mid-session.
            GeminiRateLimitError: Quota exceeded.
            GeminiTransientError: Transient send failure.
        """
        self._assert_open()
        content = genai_types.Content(
            parts=[genai_types.Part(text=text)],
            role="user",
        )
        try:
            await self._session.send_client_content(turns=content, turn_complete=True)
        except Exception as exc:
            raise self._map_exception(exc) from exc

    async def receive(self) -> AsyncIterator[AIChunk]:
        """Yield ``AIChunk`` objects from the current model turn.

        Iterates until the server sets ``turn_complete=True``, which signals the
        end of a model response.  Callers that want barge-in should cancel the
        loop immediately and call ``send_audio`` with the new user speech.

        Yields:
            :class:`AIChunk` — each carries audio and/or text, plus
            ``is_final=True`` on the last chunk of a turn.

        Raises:
            GeminiTransientError: WebSocket lost mid-stream.
        """
        self._assert_open()
        try:
            async for server_msg in self._session.receive():
                is_final = bool(
                    server_msg.server_content and server_msg.server_content.turn_complete
                )
                yield AIChunk(
                    audio=server_msg.data,  # bytes | None; SDK concatenates inline_data parts
                    text=server_msg.text,  # str | None; SDK concatenates text parts
                    is_final=is_final,
                )
        except Exception as exc:
            raise self._map_exception(exc) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_connect_config(self) -> genai_types.LiveConnectConfig:
        """Build the LiveConnectConfig for session setup.

        Returns:
            Configured :class:`~google.genai.types.LiveConnectConfig` with the
            requested voice and a system instruction that anchors the language.
        """
        voice_config = genai_types.VoiceConfig(
            prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(voice_name=self._voice)
        )
        instruction_text = self._system_instruction or (
            f"You are a helpful assistant. Always respond in the language "
            f"matching BCP-47 tag '{self._language_code}' unless the user "
            f"explicitly switches language."
        )
        system_instruction = genai_types.Content(
            parts=[genai_types.Part(text=instruction_text)],
            role="user",
        )
        return genai_types.LiveConnectConfig(
            response_modalities=[genai_types.Modality.AUDIO],
            speech_config=genai_types.SpeechConfig(voice_config=voice_config),
            system_instruction=system_instruction,
        )

    def _assert_open(self) -> None:
        """Raise ``RuntimeError`` if the session is not active.

        Raises:
            RuntimeError: Client used outside of ``async with`` block.
        """
        if self._session is None:
            raise RuntimeError(
                "GeminiLiveClient must be used as an async context manager "
                "(i.e. inside 'async with GeminiLiveClient(...) as c:')."
            )

    @staticmethod
    def _map_exception(exc: Exception) -> Exception:
        """Map SDK / WebSocket exceptions to our domain exceptions.

        HTTP 401/403 → :class:`GeminiAuthError` (do not retry).
        HTTP 429 → :class:`GeminiRateLimitError` (do not retry).
        HTTP 5xx / network → :class:`GeminiTransientError` (retry eligible).

        Args:
            exc: The raw exception from the SDK or websockets library.

        Returns:
            A domain-specific exception wrapping the original.
        """
        if isinstance(exc, genai_errors.ClientError):
            if exc.code in (401, 403):
                return GeminiAuthError(f"Authentication failed: {exc}")
            if exc.code == 429:
                return GeminiRateLimitError(f"Rate limit exceeded: {exc}")
        if isinstance(exc, genai_errors.ServerError):
            return GeminiTransientError(f"Server error (transient): {exc}")
        # Covers websockets.ConnectionClosed and other network-level failures.
        return GeminiTransientError(f"Transient error: {exc}")


# ---------------------------------------------------------------------------
# Retry-decorated send helpers (module-level, so tenacity decorates cleanly)
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type(GeminiTransientError),
    wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_WAIT_MIN_S, max=RETRY_WAIT_MAX_S),
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    reraise=True,
)
async def send_audio_with_retry(client: GeminiLiveClient, pcm_bytes: bytes) -> None:
    """Call ``client.send_audio`` with exponential-backoff retry on transient errors.

    Auth and rate-limit errors are NOT retried — they surface immediately.

    Args:
        client: An open :class:`GeminiLiveClient` instance.
        pcm_bytes: Raw PCM bytes to send.

    Raises:
        GeminiAuthError: Auth failure (not retried).
        GeminiRateLimitError: Quota exceeded (not retried).
        GeminiTransientError: Still failing after 4 attempts.
    """
    await client.send_audio(pcm_bytes)
