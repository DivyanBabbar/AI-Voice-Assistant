"""agents — LiveKit-based voice agent definitions and session orchestration.

Each agent in this sub-package is a self-contained async entrypoint that
conforms to the livekit-agents JobContext protocol.  The runner module
(runner.py) wires the chosen agent to the LiveKit Worker process via
``cli.run_app``.

Available agents
----------------
echo
    Subscribes to incoming audio tracks and republishes every frame back
    into the room — no STT/TTS, pure PCM pass-through.  Used for latency
    measurement and end-to-end audio quality verification.
"""
