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
    // The deployment cannot serve a WebSocket upgrade at all. `src/api/app.py`
    // builds SocketIO with `async_mode="threading"`, `requirements-api.txt`
    // pulls in neither eventlet nor gevent, and `wsgi.py` documents production
    // as `gunicorn -w 1 ... wsgi:app` — gunicorn's sync worker has no async
    // machinery to hijack the connection with, so an upgrade attempt there
    // fails and the client is left retrying instead of streaming. wsgi.py's
    // own header says as much: WebSockets work under Werkzeug (dev) and "fall
    // back to long-polling behind gunicorn sync workers". Pinning polling asks
    // for the transport the server can actually serve, in dev and in prod
    // alike, so the two behave the same.
    // (It also avoids the spurious 500 — "write() before start_response" —
    // that Werkzeug's threaded dev server logs when a browser closes a
    // WebSocket. That was the original reason and it is the lesser one; the
    // deployment constraint is why the pin stays.)
    // NOTE: CSP is NOT the reason, whatever an older comment here claimed.
    // CSP Level 3 relaxed `connect-src 'self'` to match the ws/wss variants of
    // the page's own origin, and both Blink and Gecko implement that — so
    // `'self'` would permit a same-origin upgrade just fine.
    // tests/test_socket_transport_pin_contract.py ties this line to the
    // deployment so the two cannot drift apart unnoticed.
    transports: ['polling'],
  });
}
