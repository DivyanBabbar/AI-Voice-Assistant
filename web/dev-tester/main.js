/**
 * @file main.js — LiveKit Dev Tester
 *
 * Joins a LiveKit room as publisher (mic) and subscriber (future remote tracks).
 * Drives a live VU-meter via AudioContext + AnalyserNode.
 *
 * Architecture: a single `app` object holds all mutable state; nothing else
 * is attached to `window`.  Every public action is an async function with
 * try/catch so errors surface in the on-screen log rather than a silent console.
 *
 * Assumes:
 *  - livekit-client UMD bundle is loaded before this module runs
 *    (exposes window.LivekitClient).
 *  - The FastAPI token endpoint is reachable at http://localhost:8000 with
 *    CORS enabled (DEV_MODE=true in the server's .env).
 */

/* global LivekitClient */

// ── Constants ─────────────────────────────────────────────────────────────────

const API_BASE  = 'http://localhost:8000';
const ROOM_NAME = 'dev-test-room';
/** Random suffix so multiple browser tabs use distinct identities. */
const IDENTITY  = `tester-${Math.random().toString(36).slice(2, 8)}`;

// ── Single global app state object ───────────────────────────────────────────

/**
 * All mutable runtime state lives here.
 * @type {{
 *   room:       LivekitClient.Room | null,
 *   msTrack:    MediaStreamTrack | null,
 *   audioCtx:   AudioContext | null,
 *   analyser:   AnalyserNode | null,
 *   vuAnimId:   number | null,
 *   muted:      boolean,
 * }}
 */
const app = {
  room:      null,
  msTrack:   null,
  audioCtx:  null,
  analyser:  null,
  vuAnimId:  null,
  muted:     false,
};

// ── DOM references ────────────────────────────────────────────────────────────

const btnJoin  = /** @type {HTMLButtonElement} */ (document.getElementById('btn-join'));
const btnLeave = /** @type {HTMLButtonElement} */ (document.getElementById('btn-leave'));
const btnMute  = /** @type {HTMLButtonElement} */ (document.getElementById('btn-mute'));
const statusEl = /** @type {HTMLElement}       */ (document.getElementById('status'));
const dotEl    = /** @type {HTMLElement}       */ (document.getElementById('status-dot'));
const vuEl     = /** @type {HTMLElement}       */ (document.getElementById('vu-bar'));
const logEl    = /** @type {HTMLElement}       */ (document.getElementById('log'));

// ── UI helpers ────────────────────────────────────────────────────────────────

/**
 * Appends a timestamped line to the on-screen log panel.
 * The newest entry is styled differently so the eye is drawn to it immediately.
 * @param {string}  msg
 * @param {'info' | 'error'} [level='info']
 */
function log(msg, level = 'info') {
  const ts   = new Date().toISOString().slice(11, 23); // HH:MM:SS.mmm
  const line = document.createElement('div');
  line.className = `log-line newest${level === 'error' ? ' error' : ''}`;
  line.textContent = `[${ts}] ${msg}`;

  // Demote the previous newest line
  const prev = logEl.querySelector('.log-line.newest');
  if (prev) prev.classList.remove('newest');

  logEl.prepend(line);

  // Keep log from growing unboundedly
  while (logEl.children.length > 200) {
    logEl.removeChild(logEl.lastChild);
  }
}

/**
 * Updates the status text and the coloured dot.
 * @param {'Disconnected' | 'Connecting…' | string} msg
 * @param {'disconnected' | 'connecting' | 'connected'} [state='disconnected']
 */
function setStatus(msg, state = 'disconnected') {
  statusEl.textContent = msg;
  dotEl.className = 'dot';
  if (state === 'connecting') dotEl.classList.add('connecting');
  if (state === 'connected')  dotEl.classList.add('connected');
}

// ── Token fetch ───────────────────────────────────────────────────────────────

/**
 * Requests a signed LiveKit JWT from the backend token endpoint.
 * Throws if the server returns a non-2xx response.
 * @returns {Promise<{token: string, ws_url: string}>}
 */
async function fetchToken() {
  const res = await fetch(`${API_BASE}/v1/livekit/token`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ room: ROOM_NAME, identity: IDENTITY, name: IDENTITY }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '(no body)');
    throw new Error(`Token endpoint returned ${res.status}: ${body}`);
  }
  return /** @type {{token: string, ws_url: string}} */ (res.json());
}

// ── VU meter ──────────────────────────────────────────────────────────────────

/**
 * Creates an AudioContext analyser connected to the given mic track and starts
 * an animation loop that updates the VU-bar width every frame.
 *
 * Must be called from within (or downstream of) a user-gesture handler so the
 * browser's autoplay policy permits AudioContext creation.
 *
 * @param {MediaStreamTrack} msTrack  The live microphone MediaStreamTrack.
 */
function startVuMeter(msTrack) {
  app.audioCtx = new AudioContext();
  app.analyser  = app.audioCtx.createAnalyser();
  app.analyser.fftSize        = 256;
  app.analyser.smoothingTimeConstant = 0.6;

  const source = app.audioCtx.createMediaStreamSource(new MediaStream([msTrack]));
  source.connect(app.analyser);

  const freqBuf = new Uint8Array(app.analyser.frequencyBinCount);

  /** Single animation frame: read frequency energy, map to bar width. */
  function tick() {
    app.analyser.getByteFrequencyData(freqBuf);
    // Average energy across all frequency bins, scale to 0-100 %.
    const avg = freqBuf.reduce((sum, v) => sum + v, 0) / freqBuf.length;
    vuEl.style.width = `${Math.min(avg * 2.8, 100).toFixed(1)}%`;
    app.vuAnimId = requestAnimationFrame(tick);
  }

  app.vuAnimId = requestAnimationFrame(tick);
}

/**
 * Cancels the VU meter animation loop and tears down the AudioContext.
 * Safe to call even if the meter was never started.
 */
function stopVuMeter() {
  if (app.vuAnimId !== null) {
    cancelAnimationFrame(app.vuAnimId);
    app.vuAnimId = null;
  }
  vuEl.style.width = '0%';
  if (app.audioCtx) {
    app.audioCtx.close();
    app.audioCtx = null;
    app.analyser  = null;
  }
}

// ── Room lifecycle ────────────────────────────────────────────────────────────

/**
 * Joins the LiveKit room:
 *   1. Fetches a token from the backend.
 *   2. Creates a Room, registers event listeners.
 *   3. Connects to the LiveKit WebSocket.
 *   4. Publishes the local microphone as an audio track.
 *   5. Starts the VU meter.
 *
 * @throws {Error} If the token endpoint is unreachable or the room connect fails.
 */
async function joinRoom() {
  setStatus('Connecting…', 'connecting');
  btnJoin.disabled = true;
  log(`Joining room "${ROOM_NAME}" as "${IDENTITY}"`);

  const { token, ws_url: wsUrl } = await fetchToken();
  log(`Token received — connecting to ${wsUrl}`);

  const { Room, RoomEvent, createLocalAudioTrack } = LivekitClient;

  app.room = new Room({ adaptiveStream: true, dynacast: true });

  app.room
    .on(RoomEvent.Connected, () => {
      setStatus(`Connected — room: ${ROOM_NAME}`, 'connected');
      btnLeave.disabled = false;
      btnMute.disabled  = false;
      log('Room connected');
    })
    .on(RoomEvent.Disconnected, () => {
      setStatus('Disconnected', 'disconnected');
      btnJoin.disabled  = false;
      btnLeave.disabled = true;
      btnMute.disabled  = true;
      btnMute.textContent = 'Mute mic';
      btnMute.classList.remove('muted');
      stopVuMeter();
      app.room    = null;
      app.msTrack = null;
      app.muted   = false;
      log('Room disconnected');
    })
    .on(RoomEvent.Reconnecting, () => {
      setStatus('Reconnecting…', 'connecting');
      log('Reconnecting to room…');
    })
    .on(RoomEvent.Reconnected, () => {
      setStatus(`Connected — room: ${ROOM_NAME}`, 'connected');
      log('Reconnected');
    })
    .on(RoomEvent.TrackPublished, (pub, participant) => {
      log(`Track published: ${pub.kind} by ${participant.identity}`);
    })
    .on(RoomEvent.TrackSubscribed, (_track, pub, participant) => {
      log(`Track subscribed: ${pub.kind} from ${participant.identity}`);
    })
    .on(RoomEvent.ParticipantConnected, (p) => {
      log(`Participant joined: ${p.identity}`);
    })
    .on(RoomEvent.ParticipantDisconnected, (p) => {
      log(`Participant left: ${p.identity}`);
    });

  await app.room.connect(wsUrl, token);

  const audioTrack = await createLocalAudioTrack({
    echoCancellation:  true,
    noiseSuppression:  true,
    autoGainControl:   true,
  });

  await app.room.localParticipant.publishTrack(audioTrack);
  app.msTrack = audioTrack.mediaStreamTrack;
  log('Microphone track published');

  startVuMeter(app.msTrack);
}

/**
 * Gracefully leaves the room: stops the VU meter and calls room.disconnect().
 * The RoomEvent.Disconnected handler resets the remaining UI state.
 */
async function leaveRoom() {
  if (!app.room) return;
  btnLeave.disabled = true;
  log('Leaving room…');
  stopVuMeter();
  await app.room.disconnect();
}

/**
 * Toggles the local microphone mute state via the LiveKit participant API.
 * Updates button label and CSS class to reflect the current state.
 */
async function toggleMute() {
  if (!app.room) return;
  app.muted = !app.muted;
  await app.room.localParticipant.setMicrophoneEnabled(!app.muted);
  btnMute.textContent = app.muted ? 'Unmute mic' : 'Mute mic';
  btnMute.classList.toggle('muted', app.muted);
  log(app.muted ? 'Mic muted' : 'Mic unmuted');
}

// ── Event wiring ──────────────────────────────────────────────────────────────

btnJoin.addEventListener('click', async () => {
  try {
    await joinRoom();
  } catch (err) {
    setStatus('Error — see log', 'disconnected');
    btnJoin.disabled = false;
    log(`ERROR joining: ${/** @type {Error} */ (err).message}`, 'error');
    console.error('[LiveKit Dev Tester] joinRoom error:', err);
  }
});

btnLeave.addEventListener('click', async () => {
  try {
    await leaveRoom();
  } catch (err) {
    log(`ERROR leaving: ${/** @type {Error} */ (err).message}`, 'error');
    console.error('[LiveKit Dev Tester] leaveRoom error:', err);
  }
});

btnMute.addEventListener('click', async () => {
  try {
    await toggleMute();
  } catch (err) {
    log(`ERROR toggling mute: ${/** @type {Error} */ (err).message}`, 'error');
    console.error('[LiveKit Dev Tester] toggleMute error:', err);
  }
});

// Clean up on tab close / reload so LiveKit server removes the participant promptly.
window.addEventListener('beforeunload', () => {
  if (app.room) {
    // disconnect() is synchronous in the beforeunload path; the async version
    // may not complete before the page tears down, which is acceptable.
    app.room.disconnect();
  }
});
