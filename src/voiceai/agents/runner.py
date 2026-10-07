"""agents.runner — CLI entrypoint for the LiveKit agents Worker process.

Usage (via shell script or direct):

    AGENT=echo python -m voiceai.agents.runner start

The ``start`` subcommand is handled by ``livekit.agents.cli.run_app`` and
connects to the LiveKit server specified by the three required env vars:

    LIVEKIT_URL        WebSocket URL of the LiveKit server (ws://... or wss://...)
    LIVEKIT_API_KEY    LiveKit API key used to authenticate the worker
    LIVEKIT_API_SECRET LiveKit API secret used to sign worker tokens

The AGENT env var selects which agent entrypoint to load.  Currently
supported values:

    echo    Raw audio echo — frames in, frames out (no STT/TTS).

If AGENT is unrecognised the process logs an error and exits with code 1 so
that a supervisor (ECS task / systemd) will restart it after a backoff.

SIGINT and SIGTERM are handled by ``cli.run_app``; the Worker drains
in-flight jobs before exiting.
"""

from __future__ import annotations

import os
import sys

from livekit.agents import WorkerOptions, cli

from voiceai.agents.echo_agent import entrypoint as _echo_entrypoint
from voiceai.observability.logging import configure_logging, get_logger

# ---------------------------------------------------------------------------
# Agent registry — add new agents here
# ---------------------------------------------------------------------------

_ENTRYPOINTS = {
    "echo": _echo_entrypoint,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the LiveKit agents Worker and route to the selected agent.

    Reads the ``AGENT`` environment variable to pick the entrypoint, then
    delegates everything else (argument parsing, signal handling, process
    lifecycle) to ``livekit.agents.cli.run_app``.

    Raises:
        SystemExit: With code 1 if the AGENT name is not recognised.
    """
    configure_logging()
    log = get_logger(__name__)

    agent_name = os.environ.get("AGENT", "echo")
    entrypoint_fnc = _ENTRYPOINTS.get(agent_name)
    if entrypoint_fnc is None:
        log.error(
            "unknown_agent",
            agent=agent_name,
            known=sorted(_ENTRYPOINTS.keys()),
        )
        sys.exit(1)

    log.info("worker_starting", agent=agent_name)

    # WorkerOptions picks up LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    # from the environment automatically if not passed here.
    opts = WorkerOptions(entrypoint_fnc=entrypoint_fnc)
    cli.run_app(opts)


if __name__ == "__main__":
    main()
