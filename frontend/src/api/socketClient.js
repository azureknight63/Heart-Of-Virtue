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
    // The pin is about what happens AFTER a successful upgrade. engineio's
    // websocket handler parks the WSGI request thread in
    // `while True: websocket_wait()` for the whole life of the connection
    // (engineio/socket.py). The Procfile runs `gunicorn -w 1 ... wsgi:app`:
    // one sync worker, one connection at a time, notifying the arbiter only
    // at the top of its accept loop. A parked worker therefore stops
    // notifying and the arbiter SIGKILLs it at the default 30s timeout — and
    // `src/api/services/session_manager.py` holds sessions in memory, so that
    // kill drops every live session and force-logs-out every connected
    // player. Polling keeps each request short, so the worker keeps returning
    // to its accept loop.
    //
    // CAVEAT, stated plainly because the previous two rationales were
    // confidently wrong: `gunicorn` appears in NO requirements file in this
    // repo, so the Procfile invokes a binary we never install, and CLAUDE.md
    // says production hosting is configured outside this repo. The process
    // model above is read off the Procfile, not verified against a running
    // deployment. If production turns out to run something else — several
    // workers, a threaded worker class, a real async worker — this reasoning
    // has to be re-derived rather than patched.
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
    // tests/test_socket_transport_pin_contract.py ties this line to the two
    // facts that actually live in this repo, so the two cannot drift apart
    // unnoticed.
    transports: ['polling'],
  });
}
