/**
 * Thin wrapper over socket.io-client for the combat stream (issue #436).
 *
 * Isolates the dependency so the hook and its tests never touch io() directly.
 * The socket connects to the API origin (SocketIO is served from the app root,
 * not under /api).
 */
import { io } from 'socket.io-client';

/** Origin to connect the socket to, or undefined for same-origin. */
export function socketUrl() {
  const apiUrl = import.meta.env.VITE_API_URL;
  if (!apiUrl) return undefined;
  try {
    return new URL(apiUrl, window.location.origin).origin;
  } catch {
    return undefined;
  }
}

export function createCombatSocket({ url } = {}) {
  return io(url ?? socketUrl(), {
    autoConnect: true,
    // The handshake is what authenticates this socket: the server reads the
    // HttpOnly session cookie off it (issue #493). Same-origin polling would
    // send the cookie anyway; this is explicit so a cross-origin dev setup
    // (VITE_API_URL pointed straight at the API port) does not silently
    // connect as nobody.
    withCredentials: true,
    // LOAD-BEARING IN PRODUCTION — do not delete this as a dev-server relic.
    //
    // The reason is NOT that the server cannot serve a WebSocket upgrade. It
    // can, and it advertises that it can: engineio's threading driver sets
    // `'websocket': SimpleWebSocketWSGI`
    // (engineio/async_drivers/threading.py), and `BaseServer._upgrades()`
    // returns `['websocket']` whenever that entry is non-None — it consults
    // nothing about the WSGI server. Under gunicorn the hijack even has
    // explicit support: simple_websocket's Server sets `mode = 'gunicorn'`
    // when it finds `gunicorn.socket` in the environ, engineio's
    // `_websocket_wsgi.py` raises StopIteration in that mode, and gunicorn's
    // sync worker catches it. Two earlier versions of this comment claimed
    // otherwise — first blaming CSP, then "the deployment cannot serve an
    // upgrade at all". Both were false.
    //
    // Nor is it the reason this comment gave next: that a completed upgrade
    // parks the WSGI request in `while True: websocket_wait()`
    // (engineio/socket.py) and the Procfile's one SYNC worker is SIGKILLed
    // at the 30s default with it. THAT REASON IS VOID (issue #653): the
    // process model was read off the Procfile and never verified. Production
    // runs the unit mirrored at `deploy/heart-of-virtue.service`,
    //
    //     gunicorn --worker-class eventlet -w 1 --timeout 120 wsgi:app
    //
    // where a parked connection holds a greenlet, not the worker, and
    // `--timeout` is a liveness heartbeat rather than a per-request deadline.
    //
    // The pin stands for three reasons that do hold (#653, "pin now,
    // migrate later"):
    //
    //   (a) The reverse proxy in front of the API is unverified. Nobody has
    //       read its config (docs/development/deployment.md: Apache or nginx,
    //       unconfirmed), so whether it forwards `Upgrade`/`Connection` on
    //       `/games/HeartOfVirtue/*` is unknown. Plain HTTP long-polling is
    //       the one transport known to pass through it.
    //   (b) The server runs Socket.IO with `async_mode="threading"`
    //       (src/api/app.py) inside an eventlet worker. Flask-SocketIO's
    //       gunicorn + eventlet recipe assumes `async_mode="eventlet"`; a
    //       long-lived WebSocket held by the threading driver's
    //       simple-websocket under a monkey-patched eventlet hub is an
    //       unsupported combination nobody has exercised. Polling requests
    //       are ordinary short WSGI requests, which that worker does serve.
    //   (c) The worker class itself is due to change: gunicorn 26 removed
    //       the eventlet worker, requirements-api.txt holds gunicorn below
    //       26 until production migrates off eventlet, and the transport
    //       should be re-derived on whatever worker that lands on, not on
    //       this one.
    //
    // Re-open the transport only after all three are settled.
    //
    // (The pin also avoids the spurious 500 — "write() before
    // start_response" — that Werkzeug's threaded dev server logs when a
    // browser closes a WebSocket. That was the original reason and it is the
    // lesser one.)
    //
    // NOTE: CSP is NOT the reason, whatever an older comment here claimed.
    // CSP Level 3 relaxed `connect-src 'self'` to match the ws/wss variants of
    // the page's own origin, and both Blink and Gecko implement that — so
    // `'self'` would permit a same-origin upgrade just fine.
    //
    // tests/test_socket_transport_pin_contract.py holds this pin to the
    // verified unit and to #653, so the prose and the deployment cannot drift
    // apart again.
    transports: ['polling'],
  });
}
