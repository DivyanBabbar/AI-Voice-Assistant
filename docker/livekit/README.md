# LiveKit local development stack

This directory contains the Docker Compose file and server config to run a
LiveKit media server on your laptop for development.

> **Security note**: `devkey` / `devsecret` are placeholder credentials
> for local use only.  They are checked into version control intentionally.
> Never use them outside your laptop.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Docker Desktop | ≥ 4.x |
| livekit-cli (`lk`) | latest (`brew install livekit-cli`) |

---

## Start the server

```bash
# From the repo root
docker compose -f docker/livekit/docker-compose.yml up -d
```

The server exposes:

| Port | Protocol | Purpose |
|------|----------|---------|
| 7880 | TCP | WebSocket API + HTTP |
| 7881 | TCP | TURN (TCP fallback) |
| 7882 | UDP | RTC media |

---

## Verify with livekit-cli

```bash
# Point the CLI at the local server
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=devsecret

# List rooms (should return an empty list on a fresh server)
lk room list
```

Expected output:

```
No rooms found
```

---

## Stop the server

```bash
docker compose -f docker/livekit/docker-compose.yml down
```

---

## Health check

```bash
curl -s http://localhost:7880/healthz
# → {"alive":true}
```
