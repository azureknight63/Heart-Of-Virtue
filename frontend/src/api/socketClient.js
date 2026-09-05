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
    // The app's Content-Security-Policy (src/resources/csp-policy.json) grants
    // `connect-src 'self'` in `base` and lists `ws:`/`wss:` only under
    // `dev_additions`. A WebSocket upgrade is a connect-src check, and
    // `'self'` does not cover the ws(s) scheme, so under the enforcing
    // production policy the browser blocks the upgrade outright: a socket
    // allowed to upgrade works in dev and dies in production, where the
    // failure is a silently dead combat stream. Pinning polling keeps the
    // transport inside what the policy actually permits.
    // (It also avoids the spurious 500 — "write() before start_response" —
    // that Werkzeug's threaded dev server logs when a browser closes a
    // WebSocket. That was the original reason and it is the lesser one; the
    // CSP constraint is why the pin stays.)
    // tests/test_socket_transport_csp_contract.py ties this line to the policy
    // file so the two cannot drift apart unnoticed.
    transports: ['polling'],
  });
}
