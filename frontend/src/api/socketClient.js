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
    //     gunicorn --worker-class gthread -w 1 --threads 32 --timeout 120 wsgi:app
    //
    // (an eventlet worker until 2026-09-26), where a parked connection holds
    // one of the worker's threads, not the worker, and `--timeout` is a
    // liveness heartbeat rather than a per-request deadline.
    //
    // The pin stands (#653, "pin now, migrate later") for two reasons that
    // hold on that worker:
    //
    //   (a) The reverse proxy in front of the API is unverified. Nobody has
    //       read its config (docs/development/deployment.md: Apache or nginx,
    //       unconfirmed), so whether it forwards `Upgrade`/`Connection` on
    //       `/games/HeartOfVirtue/*` is unknown. Plain HTTP long-polling is
    //       the one transport known to pass through it.
    //   (b) Capacity. `async_mode="threading"` (src/api/app.py) on gthread is
    //       the combination Flask-SocketIO documents, but every connected
    //       client -- a parked WebSocket or a pending long-poll -- holds one
    //       of the worker's 32 threads, so the thread count bounds concurrent
    //       socket players. Measure that before opening a transport that holds
    //       its thread for the whole connection rather than per poll.
    //
    // (A third reason, retired 2026-09-26: `async_mode="threading"` inside an
    // eventlet worker was an unsupported combination. The unit left eventlet.)
    //
    // Re-open the transport only after both are settled.
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
