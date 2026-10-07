"""Unit tests for /v1/livekit/token and /healthz.

All tests use FastAPI's TestClient — no real LiveKit server needed.
AccessToken is mocked so the JWT output is predictable without a valid secret.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from voiceai.api.main import TOKEN_TTL_SECONDS, app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_JWT = "header.payload.signature"


def _mock_token_chain(fake_jwt: str = _FAKE_JWT) -> MagicMock:
    """Return a mock AccessToken that resolves to ``fake_jwt`` via the builder chain."""
    token = MagicMock()
    token.with_identity.return_value = token
    token.with_name.return_value = token
    token.with_grants.return_value = token
    token.with_ttl.return_value = token
    token.to_jwt.return_value = fake_jwt
    return token


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_create_token_happy_path() -> None:
    """POST /v1/livekit/token returns a token and ws_url on valid input."""
    mock_token = _mock_token_chain()

    with patch("voiceai.api.main.AccessToken", return_value=mock_token):
        resp = client.post(
            "/v1/livekit/token",
            json={"room": "demo-room", "identity": "user-42", "name": "Alice"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["token"] == _FAKE_JWT
    assert body["ws_url"].startswith("ws://")


def test_create_token_without_name_uses_identity_as_display_name() -> None:
    """When 'name' is omitted the endpoint should still succeed."""
    mock_token = _mock_token_chain()

    with patch("voiceai.api.main.AccessToken", return_value=mock_token):
        resp = client.post(
            "/v1/livekit/token",
            json={"room": "test-room", "identity": "bot-1"},
        )

    assert resp.status_code == 200
    # with_name should have been called with the identity as fallback
    mock_token.with_name.assert_called_once_with("bot-1")


# ---------------------------------------------------------------------------
# Token grants
# ---------------------------------------------------------------------------


def test_create_token_grants_room_join() -> None:
    """The token must be issued with roomJoin=True for the requested room."""
    from livekit.api import VideoGrants

    captured_grants: list[VideoGrants] = []

    mock_token = _mock_token_chain()

    def _capture_grants(grants: VideoGrants) -> MagicMock:
        captured_grants.append(grants)
        return mock_token

    mock_token.with_grants.side_effect = _capture_grants

    with patch("voiceai.api.main.AccessToken", return_value=mock_token):
        client.post(
            "/v1/livekit/token",
            json={"room": "lobby", "identity": "presenter"},
        )

    assert len(captured_grants) == 1
    grant = captured_grants[0]
    assert grant.room_join is True
    assert grant.room == "lobby"


def test_create_token_ttl_is_one_hour() -> None:
    """The token TTL must be exactly 3600 seconds (passed as timedelta)."""
    import datetime

    mock_token = _mock_token_chain()

    with patch("voiceai.api.main.AccessToken", return_value=mock_token):
        client.post(
            "/v1/livekit/token",
            json={"room": "r", "identity": "u"},
        )

    mock_token.with_ttl.assert_called_once()
    ttl_arg = mock_token.with_ttl.call_args.args[0]
    assert ttl_arg == datetime.timedelta(seconds=TOKEN_TTL_SECONDS)
    assert TOKEN_TTL_SECONDS == 3600


# ---------------------------------------------------------------------------
# Validation — missing required fields → 422
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"room": "r"},
        {"identity": "u"},
        {"name": "Alice"},
    ],
)
def test_create_token_missing_required_fields_returns_422(payload: dict) -> None:
    """POST without 'room' or 'identity' must return HTTP 422."""
    resp = client.post("/v1/livekit/token", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_healthz_returns_ok() -> None:
    """GET /healthz must return 200 with status='ok'."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# OpenAPI schema is wired (Swagger / /openapi.json available)
# ---------------------------------------------------------------------------


def test_openapi_schema_is_reachable() -> None:
    """GET /openapi.json must return 200 — confirms Swagger is wired."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "/v1/livekit/token" in schema["paths"]
    assert "/healthz" in schema["paths"]
