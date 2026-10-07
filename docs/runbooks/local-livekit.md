# Runbook: Local LiveKit troubleshooting

Use this when `docker compose up` fails, the CLI cannot connect, or the
browser reports WebSocket errors.

---

## 1. Port conflicts

**Symptom**: `Bind for 0.0.0.0:7880 failed: port is already allocated`.

```bash
# Find what is using port 7880
lsof -i :7880
# Kill it or change the host-side port in docker-compose.yml
```

For UDP port 7882:

```bash
lsof -i udp:7882
```

---

## 2. Docker health-check keeps failing

**Symptom**: `docker ps` shows the container as `unhealthy`.

```bash
# Tail container logs
docker compose -f docker/livekit/docker-compose.yml logs -f livekit

# Try the health endpoint manually
curl -v http://localhost:7880/healthz
```

Common causes:
- The `--dev` flag is missing from the command (already set in compose).
- The config file path inside the container is wrong — verify the volume
  mount in `docker-compose.yml`.

---

## 3. Firewall blocking UDP

**Symptom**: Browser joins the room but audio never flows; ICE state stays
`checking`.

On macOS, the built-in firewall may block inbound UDP.  Allow Docker:

```
System Settings → Network → Firewall → Options
Add /usr/bin/docker (or Docker Desktop) → Allow incoming connections
```

On Linux, check `ufw`:

```bash
sudo ufw allow 7882/udp
```

---

## 4. Browser microphone permission

**Symptom**: `getUserMedia` rejected; console shows `NotAllowedError`.

- For `http://localhost` browsers allow mic access without HTTPS.
- For non-localhost (e.g. a VM's IP), you need HTTPS.  Use `ngrok` or a
  self-signed cert for local dev.

---

## 5. Token endpoint returns 422

**Symptom**: `curl POST localhost:8000/v1/livekit/token` returns HTTP 422.

The request body must include both `room` and `identity`:

```bash
curl -s -X POST http://localhost:8000/v1/livekit/token \
  -H "Content-Type: application/json" \
  -d '{"room": "demo", "identity": "tester"}' | jq
```

---

## 6. Token endpoint returns 500 / ImportError

**Symptom**: uvicorn crashes with `ModuleNotFoundError: livekit`.

The Poetry virtualenv is missing the new dependencies:

```bash
poetry install
```

---

## 7. lk CLI cannot connect

**Symptom**: `lk room list` hangs or returns `connection refused`.

```bash
# Confirm the container is running
docker ps | grep livekit

# Re-check env vars
echo $LIVEKIT_URL   # must be ws://localhost:7880
echo $LIVEKIT_API_KEY
echo $LIVEKIT_API_SECRET
```
