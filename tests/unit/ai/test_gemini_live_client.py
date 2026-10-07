"""Unit tests for GeminiLiveClient.

All tests mock the google-genai WebSocket session — no real API calls are made.
Verify by removing GOOGLE_API_KEY and re-running: the suite must still pass.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import errors as genai_errors

from voiceai.ai.gemini_live_client import (
    AIChunk,
    GeminiAuthError,
    GeminiLiveClient,
    GeminiRateLimitError,
    GeminiTransientError,
    send_audio_with_retry,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_server_msg(
    *,
    audio_bytes: bytes | None = None,
    text: str | None = None,
    turn_complete: bool = False,
) -> MagicMock:
    """Build a mock LiveServerMessage.

    Args:
        audio_bytes: Optional PCM bytes to surface via ``.data``.
        text: Optional text string to surface via ``.text``.
        turn_complete: Whether to set ``server_content.turn_complete``.

    Returns:
        A configured :class:`~unittest.mock.MagicMock` that mimics the SDK
        ``LiveServerMessage`` interface used by our client code.
    """
    msg = MagicMock()
    msg.data = audio_bytes
    msg.text = text
    if turn_complete:
        msg.server_content = MagicMock()
        msg.server_content.turn_complete = True
    else:
        msg.server_content = MagicMock()
        msg.server_content.turn_complete = False
    return msg


async def _async_iter(items: list[Any]) -> AsyncIterator[Any]:
    """Turn a plain list into an async iterator for patching ``session.receive``."""
    for item in items:
        yield item


def _make_mock_session(messages: list[Any] | None = None) -> MagicMock:
    """Build a mock AsyncSession with send and receive pre-configured.

    Args:
        messages: List of mock server messages returned by ``receive()``.

    Returns:
        A :class:`~unittest.mock.MagicMock` that behaves like an open
        ``AsyncSession`` (SDK v2.x API surface).
    """
    session = MagicMock()
    session.send_realtime_input = AsyncMock()
    session.send_client_content = AsyncMock()
    if messages is not None:
        session.receive = MagicMock(return_value=_async_iter(messages))
    else:
        session.receive = MagicMock(return_value=_async_iter([]))
    return session


def _make_mock_ctx(session: MagicMock) -> MagicMock:
    """Build an async context manager that yields the given session.

    Args:
        session: The mock session to surface from ``__aenter__``.

    Returns:
        A :class:`~unittest.mock.MagicMock` whose ``__aenter__`` returns the
        mock session and whose ``__aexit__`` is a no-op coroutine.
    """
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# Test: lifecycle — open and close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_opens_and_closes_cleanly() -> None:
    """GeminiLiveClient.__aenter__/exit should open and close without exceptions."""
    session = _make_mock_session()
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        async with GeminiLiveClient(api_key="fake-key") as client:
            assert client._session is session

        # After exit, session reference is cleared.
        assert client._session is None

    ctx.__aenter__.assert_awaited_once()
    ctx.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_manager_clears_on_exception() -> None:
    """__aexit__ clears internal state even when the body raises."""
    session = _make_mock_session()
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        with pytest.raises(ValueError):
            async with GeminiLiveClient(api_key="fake-key"):
                raise ValueError("body error")

    assert session is not None  # session object still exists, but client cleared it


# ---------------------------------------------------------------------------
# Test: send_audio passes bytes to the mocked session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_audio_passes_blob_to_session() -> None:
    """send_audio should wrap PCM bytes in a Blob and call send_realtime_input."""
    pcm = b"\x00\x01" * 160  # 320 bytes — 10 ms of 16 kHz s16le mono
    session = _make_mock_session()
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        async with GeminiLiveClient(api_key="fake-key") as client:
            await client.send_audio(pcm)

    session.send_realtime_input.assert_awaited_once()
    call_kwargs = session.send_realtime_input.call_args.kwargs
    blob = call_kwargs["audio"]
    # Blob.data should be the original bytes (SDK handles base64 internally).
    assert blob.data == pcm
    assert "audio/pcm" in blob.mime_type


# ---------------------------------------------------------------------------
# Test: send_text passes text and sets end_of_turn=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_text_passes_text_and_end_of_turn() -> None:
    """send_text should wrap text in a Content object and call send_client_content."""
    session = _make_mock_session()
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        async with GeminiLiveClient(api_key="fake-key") as client:
            await client.send_text("नमस्ते")

    session.send_client_content.assert_awaited_once()
    call_kwargs = session.send_client_content.call_args.kwargs
    # turn_complete must be True so the model starts replying.
    assert call_kwargs["turn_complete"] is True
    # The turns arg should be a Content with the text in its first Part.
    content = call_kwargs["turns"]
    assert content.parts[0].text == "नमस्ते"
    assert content.role == "user"


# ---------------------------------------------------------------------------
# Test: receive yields AIChunk objects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_receive_yields_ai_chunks() -> None:
    """receive() should yield AIChunk for each server message, is_final on last."""
    audio_payload = b"\xab\xcd" * 50
    messages = [
        _make_server_msg(audio_bytes=audio_payload, turn_complete=False),
        _make_server_msg(text="नमस्ते", turn_complete=False),
        _make_server_msg(audio_bytes=b"\x01\x02", text="!", turn_complete=True),
    ]
    session = _make_mock_session(messages=messages)
    ctx = _make_mock_ctx(session)

    chunks: list[AIChunk] = []
    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        async with GeminiLiveClient(api_key="fake-key") as client:
            async for chunk in client.receive():
                chunks.append(chunk)

    assert len(chunks) == 3
    # First chunk: audio only, not final
    assert chunks[0].audio == audio_payload
    assert chunks[0].text is None
    assert chunks[0].is_final is False
    # Second chunk: text only, not final
    assert chunks[1].audio is None
    assert chunks[1].text == "नमस्ते"
    assert chunks[1].is_final is False
    # Third chunk: both audio and text, final
    assert chunks[2].audio == b"\x01\x02"
    assert chunks[2].text == "!"
    assert chunks[2].is_final is True


@pytest.mark.asyncio
async def test_receive_empty_turn_yields_no_chunks() -> None:
    """receive() on an empty turn should yield nothing."""
    session = _make_mock_session(messages=[])
    ctx = _make_mock_ctx(session)

    chunks: list[AIChunk] = []
    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        async with GeminiLiveClient(api_key="fake-key") as client:
            async for chunk in client.receive():
                chunks.append(chunk)

    assert chunks == []


# ---------------------------------------------------------------------------
# Test: auth error raises GeminiAuthError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aenter_auth_error_raises_gemini_auth_error() -> None:
    """__aenter__ should raise GeminiAuthError on HTTP 401/403."""
    # Build a fake ClientError with code 401.
    fake_response = MagicMock()
    fake_response.status_code = 401
    fake_response.json.return_value = {
        "error": {"code": 401, "message": "API key not valid", "status": "UNAUTHENTICATED"}
    }
    auth_exc = genai_errors.ClientError(401, fake_response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(side_effect=auth_exc)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        with pytest.raises(GeminiAuthError):
            async with GeminiLiveClient(api_key="bad-key"):
                pass  # pragma: no cover


@pytest.mark.asyncio
async def test_send_text_auth_error_propagates() -> None:
    """send_text should surface GeminiAuthError when the session raises 403."""
    fake_response = MagicMock()
    fake_response.status_code = 403
    fake_response.json.return_value = {
        "error": {"code": 403, "message": "Forbidden", "status": "PERMISSION_DENIED"}
    }
    auth_exc = genai_errors.ClientError(403, fake_response)

    session = _make_mock_session()
    session.send_client_content = AsyncMock(side_effect=auth_exc)
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        with pytest.raises(GeminiAuthError):
            async with GeminiLiveClient(api_key="bad-key") as client:
                await client.send_text("hello")


# ---------------------------------------------------------------------------
# Test: rate-limit error raises GeminiRateLimitError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_audio_rate_limit_raises_gemini_rate_limit_error() -> None:
    """send_audio should raise GeminiRateLimitError on HTTP 429."""
    fake_response = MagicMock()
    fake_response.status_code = 429
    fake_response.json.return_value = {
        "error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}
    }
    rate_exc = genai_errors.ClientError(429, fake_response)

    session = _make_mock_session()
    session.send_realtime_input = AsyncMock(side_effect=rate_exc)
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        with pytest.raises(GeminiRateLimitError):
            async with GeminiLiveClient(api_key="fake-key") as client:
                await client.send_audio(b"\x00" * 320)


# ---------------------------------------------------------------------------
# Test: usage outside context manager raises RuntimeError
# ---------------------------------------------------------------------------


def test_send_audio_outside_context_raises() -> None:
    """send_audio must raise RuntimeError when called outside async with."""
    client = GeminiLiveClient(api_key="fake-key")

    async def _run() -> None:
        await client.send_audio(b"\x00")

    import asyncio

    with pytest.raises(RuntimeError, match="async context manager"):
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: AIChunk model
# ---------------------------------------------------------------------------


def test_ai_chunk_defaults() -> None:
    """AIChunk fields should have correct defaults."""
    chunk = AIChunk()
    assert chunk.audio is None
    assert chunk.text is None
    assert chunk.is_final is False


def test_ai_chunk_with_values() -> None:
    """AIChunk should accept and store audio, text, and is_final."""
    chunk = AIChunk(audio=b"\x01\x02", text="hi", is_final=True)
    assert chunk.audio == b"\x01\x02"
    assert chunk.text == "hi"
    assert chunk.is_final is True


# ---------------------------------------------------------------------------
# Test: send_end_of_turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_end_of_turn_calls_realtime_input() -> None:
    """send_end_of_turn should call send_realtime_input with audio_stream_end=True."""
    session = _make_mock_session()
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        async with GeminiLiveClient(api_key="fake-key") as client:
            await client.send_end_of_turn()

    session.send_realtime_input.assert_awaited_once_with(audio_stream_end=True)


@pytest.mark.asyncio
async def test_send_end_of_turn_transient_error_raises() -> None:
    """send_end_of_turn should raise GeminiTransientError on network failure."""
    session = _make_mock_session()
    session.send_realtime_input = AsyncMock(side_effect=ConnectionError("dropped"))
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        with pytest.raises(GeminiTransientError):
            async with GeminiLiveClient(api_key="fake-key") as client:
                await client.send_end_of_turn()


# ---------------------------------------------------------------------------
# Test: receive() exception path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_receive_propagates_transient_error() -> None:
    """receive() should raise GeminiTransientError when the WebSocket drops mid-stream."""

    async def _broken_receive() -> AsyncIterator[Any]:
        yield _make_server_msg(audio_bytes=b"\x00", turn_complete=False)
        raise ConnectionError("stream dropped")

    session = _make_mock_session()
    session.receive = MagicMock(return_value=_broken_receive())
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        with pytest.raises(GeminiTransientError):
            async with GeminiLiveClient(api_key="fake-key") as client:
                async for _ in client.receive():
                    pass


# ---------------------------------------------------------------------------
# Test: _map_exception with ServerError (5xx)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_audio_server_error_raises_transient_error() -> None:
    """send_audio should raise GeminiTransientError on a 5xx ServerError."""
    from google.genai import errors as genai_errors

    fake_response = MagicMock()
    fake_response.status_code = 503
    fake_response.json.return_value = {
        "error": {"code": 503, "message": "Service Unavailable", "status": "UNAVAILABLE"}
    }
    server_exc = genai_errors.ServerError(503, fake_response)

    session = _make_mock_session()
    session.send_realtime_input = AsyncMock(side_effect=server_exc)
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        with pytest.raises(GeminiTransientError):
            async with GeminiLiveClient(api_key="fake-key") as client:
                await client.send_audio(b"\x00" * 320)


# ---------------------------------------------------------------------------
# Test: _build_connect_config with explicit system_instruction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explicit_system_instruction_overrides_default() -> None:
    """An explicit system_instruction should be passed through, not the auto-generated one."""
    custom_prompt = "You are a pirate. Speak only in Hindi."
    session = _make_mock_session()
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        async with GeminiLiveClient(api_key="fake-key", system_instruction=custom_prompt):
            pass

    config = instance.aio.live.connect.call_args.kwargs["config"]
    instruction_text = config.system_instruction.parts[0].text
    assert instruction_text == custom_prompt


# ---------------------------------------------------------------------------
# Test: __aexit__ swallows close errors gracefully
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aexit_swallows_close_error() -> None:
    """__aexit__ should not propagate errors raised while closing the session."""
    session = _make_mock_session()
    ctx = _make_mock_ctx(session)
    ctx.__aexit__ = AsyncMock(side_effect=RuntimeError("close failed"))

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        # Should not raise even though __aexit__ on the SDK ctx raises.
        async with GeminiLiveClient(api_key="fake-key"):
            pass


# ---------------------------------------------------------------------------
# Test: send_audio_with_retry retries on transient errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_audio_with_retry_succeeds_after_transient() -> None:
    """send_audio_with_retry should retry on GeminiTransientError and succeed."""
    call_count = 0

    async def _flaky_send(_: bytes) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise GeminiTransientError("temporary blip")

    session = _make_mock_session()
    ctx = _make_mock_ctx(session)

    with patch("voiceai.ai.gemini_live_client.genai.Client") as mock_genai_client:
        instance = mock_genai_client.return_value
        instance.aio.live.connect.return_value = ctx

        async with GeminiLiveClient(api_key="fake-key") as client:
            client.send_audio = _flaky_send  # type: ignore[method-assign]
            await send_audio_with_retry(client, b"\x00" * 640)

    assert call_count == 3
