"""observability.logging — Structured logging configuration via structlog.

Provides a single call-site `get_logger(name)` that returns a bound structlog
logger. In production (ENV != "dev") logs are emitted as JSON for ingestion by
Loki / CloudWatch; in development the renderer is the colourised ConsoleRenderer.
"""

from __future__ import annotations

import logging
import os
import subprocess

import structlog


def _get_git_sha() -> str:
    """Return the short HEAD git SHA, or 'unknown' if not in a git repo.

    Returns:
        Seven-character git SHA string, e.g. ``"a1b2c3d"``.
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return sha or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def configure_logging() -> None:
    """Wire structlog's shared processors and renderer.

    Must be called once at process start (e.g. from the application entry-point
    or a pytest fixture).  Subsequent calls are idempotent because structlog
    checks ``is_configured()``.

    Behaviour:
      - ENV == "dev"  → human-readable ConsoleRenderer with colours.
      - ENV != "dev"  → JSONRenderer, one JSON object per line, UTC timestamps.

    The following fields are injected into every log record:
      - ``service``: always ``"voiceai"``.
      - ``git_sha``: short HEAD SHA (best-effort; ``"unknown"`` in CI if checkout
        depth=1 without ``--tags``).
      - ``env``: value of the ``ENV`` environment variable, default ``"dev"``.
    """
    if structlog.is_configured():
        return

    env = os.getenv("ENV", "dev")
    git_sha = _get_git_sha()

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Inject fixed fields so every log has service/git_sha/env without
        # callers needing to bind them manually.
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if env == "dev":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bind service-level context once; all loggers in this process inherit it.
    structlog.contextvars.bind_contextvars(
        service="voiceai",
        git_sha=git_sha,
        env=env,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog BoundLogger pre-bound with ``module=name``.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A bound structlog logger that emits records with ``module=name``.

    Example::

        log = get_logger(__name__)
        log.info("session_opened", session_id="abc123")
    """
    configure_logging()
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
