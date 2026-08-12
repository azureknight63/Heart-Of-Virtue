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
    // The API runs Flask-SocketIO on Werkzeug's threaded development server.
    // That server can log a spurious 500 ("write() before start_response")
    // when a browser closes a WebSocket. Polling keeps Socket.IO real-time
    // without sending the request through that fragile disconnect path.
    transports: ['polling'],
  });
}
