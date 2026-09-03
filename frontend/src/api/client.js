import axios from 'axios'
import { clearLocalSession } from '../utils/session'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // The session credential is an HttpOnly cookie the API issues at login
  // (issue #493), not a token this code can read, so every request has to opt
  // into sending cookies. Same-origin requests would carry it anyway; this
  // matters for a dev setup that points VITE_API_URL straight at the API port,
  // which is cross-origin and drops cookies without it. The server side of the
  // same contract is Flask-CORS `supports_credentials=True` against a concrete
  // origin list — a credentialed request is refused outright against `*`.
  withCredentials: true,
})

// No request interceptor attaches a credential any more. The session used to
// live in localStorage under `authToken` and be replayed as
// `Authorization: Bearer <session_id>`, which made it readable by any script on
// the origin; it is now a cookie the browser attaches and JavaScript cannot
// touch. The API still accepts the Bearer form for non-browser callers (the QA
// harnesses) — see `session_token` in src/api/middleware/auth.py.

// Handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Only redirect if we get a 401 and we're NOT on the login page
    // This allows the login page to handle its own 401s (bad credentials)
    // without triggering a circular redirect/reload.
    if (error.response?.status === 401 && !window.location.pathname.includes('/login')) {
      // Clears the client-side *markers* of a session (and any legacy
      // `authToken` left over from before #493). The credential itself is the
      // HttpOnly cookie, which only the server can expire — logout does that;
      // a 401 means it is already dead.
      clearLocalSession()
      window.location.href = `${import.meta.env.BASE_URL}login`
    }
    return Promise.reject(error)
  }
)

export default apiClient
