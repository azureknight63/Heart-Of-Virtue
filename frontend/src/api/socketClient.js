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
    // The pin was about what happens AFTER a successful upgrade. engineio's
    // websocket handler parks the WSGI request thread in
    // `while True: websocket_wait()` for the whole life of the connection
    // (engineio/socket.py), and the reasoning ran: the Procfile runs
    // `gunicorn -w 1`, one SYNC worker, which notifies the arbiter only at
    // the top of its accept loop, so a parked worker is SIGKILLed at the 30s
    // default -- taking every in-memory session with it.
    //
    // THAT REASON IS VOID (issue #653). The process model was read off the
    // Procfile and never verified; the real one was read from the server on
    // 2026-09-19 and is now mirrored at `deploy/heart-of-virtue.service`:
    //
    //     gunicorn --worker-class eventlet -w 1 --timeout 120 wsgi:app
    //
    // An eventlet worker serves requests concurrently as greenlets, so a
    // parked connection holds a greenlet rather than the worker, and for a
    // non-sync worker `--timeout` is a liveness heartbeat rather than a
    // per-request deadline. Nothing here kills the worker at 30s.
    //
    // The pin STAYS for now regardless, because the decision it encodes has
    // not been re-made: whether long-polling is still the right transport on
    // the real deployment (proxy upgrade headers, `async_mode="threading"`
    // under an eventlet worker) is #653's job. Do not read this pin as
    // load-bearing until that lands, and do not delete it on the strength of
    // the paragraph above either.
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
