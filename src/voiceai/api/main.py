"""voiceai.api.main — FastAPI application: LiveKit token endpoint + health check.

Endpoints
---------
POST /v1/livekit/token
    Issues a signed LiveKit access token for a room join grant.
    Callers (browser, telephony worker) exchange this token for a WebSocket
    connection to the LiveKit server.  Token TTL is 1 hour — fine for dev;
    tighten in production.

GET /healthz
    Returns {"status": "ok"}.  Checked by load-balancers and the Docker
    health-check in docker-compose.yml.

Settings are loaded from environment variables (see Settings below).
Swagger UI is available at /docs; OpenAPI JSON at /openapi.json.

CORS (dev only)
---------------
Set DEV_MODE=true in .env to allow http://localhost:5173 (the static HTML tester).
Never set DEV_MODE=true in staging or production.
"""

from __future__ import annotations

import datetime
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Settings — loaded from environment or .env file
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables.

    Set LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_WS_URL in your
    shell or .env file before starting the server.

    Set DEV_MODE=true to enable the CORS allowlist for the local HTML tester
    (http://localhost:5173).  Must never be true in production.
    """

    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devsecret"
    livekit_ws_url: str = "ws://localhost:7880"
    dev_mode: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


_settings = Settings()

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler (startup / shutdown hooks go here)."""
    # Nothing to initialise yet; placeholder for future connection pools, etc.
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="voiceai API",
    description="Internal API for the Hindi-first voice AI platform.",
    version="0.1.0",
    lifespan=_lifespan,
)

# Dev-only CORS: allow the static HTML tester running on localhost:5173 to call
# the token endpoint.  Gated on DEV_MODE so this never activates in production.
if _settings.dev_mode:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

TOKEN_TTL_SECONDS = 3600  # 1 hour — shrink in production
_TOKEN_TTL = datetime.timedelta(seconds=TOKEN_TTL_SECONDS)


class TokenRequest(BaseModel):
    """Body for POST /v1/livekit/token."""

    room: str
    identity: str
    name: str | None = None


class TokenResponse(BaseModel):
    """Response from POST /v1/livekit/token."""

    token: str
    ws_url: str


class HealthResponse(BaseModel):
    """Response from GET /healthz."""

    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/v1/livekit/token",
    response_model=TokenResponse,
    summary="Issue a LiveKit access token",
    description=(
        "Mints a signed JWT granting the caller permission to join the requested "
        "room.  The caller must present this token to the LiveKit server WebSocket "
        "endpoint.  Token TTL is 1 hour (dev); tighten for production."
    ),
)
def create_token(body: TokenRequest) -> TokenResponse:
    """Issue a LiveKit access token with a roomJoin grant.

    Guarantees:
    - The token is valid for exactly TOKEN_TTL_SECONDS seconds.
    - The grant allows joining (and only joining) the requested room.
    - The ws_url returned is the WebSocket URL the caller should connect to.
    """
    grants = VideoGrants(room_join=True, room=body.room)
    token = (
        AccessToken(api_key=_settings.livekit_api_key, api_secret=_settings.livekit_api_secret)
        .with_identity(body.identity)
        .with_name(body.name or body.identity)
        .with_grants(grants)
        .with_ttl(_TOKEN_TTL)
        .to_jwt()
    )
    return TokenResponse(token=token, ws_url=_settings.livekit_ws_url)


@app.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns 200 with status='ok' when the service is alive.",
)
def healthz() -> HealthResponse:
    """Liveness probe — used by Docker health-check and load-balancers."""
    return HealthResponse(status="ok")
