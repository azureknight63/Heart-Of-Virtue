import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const BASE = '/games/HeartOfVirtue/'

// Content-Security-Policy for anything the Vite dev/preview server serves
// (issue #492). The Flask API emits the same policy for its own responses
// (src/api/security_headers.py), and both read their directives from the same
// JSON file so the two cannot drift. The dev document is the surface that
// actually matters for observing violations: the SPA's HTML never passes
// through Flask.
//
// Report-only, and delivered as a header rather than a <meta> tag — browsers
// ignore a report-only policy delivered in markup and log a console error for
// the attempt.
const CSP_POLICY = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../src/resources/csp-policy.json', import.meta.url)),
    'utf-8'
  )
)
const CSP_REPORT_URI = `${BASE}api/logs/csp-report`

/**
 * Compose the report-only policy string.
 *
 * Mirrors build_csp() in src/api/security_headers.py — same merge order, same
 * dedupe, same report directives — over the shared directive data. The dev
 * relaxations are opt-in per surface: the dev server needs them (React Refresh
 * injects an inline preamble no build step can hash), `vite preview` does not,
 * because it serves the built bundle that production serves.
 */
function cspHeaders({ dev }) {
  const directives = Object.fromEntries(
    Object.entries(CSP_POLICY.base).map(([name, values]) => [name, [...values]])
  )
  if (dev) {
    for (const [name, extra] of Object.entries(CSP_POLICY.dev_additions ?? {})) {
      const merged = (directives[name] ??= [])
      merged.push(...extra.filter((value) => !merged.includes(value)))
    }
  }
  const policy = [
    ...Object.entries(directives).map(([name, values]) => `${name} ${values.join(' ')}`),
    // `report-uri` only. Pairing it with the newer `report-to` silently kills
    // reporting in Chromium: `report-to` wins whenever both are present, and
    // its queued delivery never fires for a plain-HTTP origin. Measured — see
    // the module docstring in src/api/security_headers.py.
    `report-uri ${CSP_REPORT_URI}`
  ].join('; ')

  return { 'Content-Security-Policy-Report-Only': policy }
}

// The API is same-origin with the SPA in every environment (VITE_API_URL is the
// relative path `/games/HeartOfVirtue/api`), which is what lets `connect-src`
// stay at 'self'. Both local servers therefore proxy it rather than sending the
// browser cross-origin.
const apiProxy = {
  '/games/HeartOfVirtue/api': {
    target: 'http://localhost:5000',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/games\/HeartOfVirtue/, '')
  },
  // Keep this for any hardcoded /api paths just in case
  '/api': {
    target: 'http://localhost:5000',
    changeOrigin: true
  },
  // Socket.IO is served from the app root, outside the SPA base path, so it
  // needs its own entry. Without it the cookie-authenticated handshake cannot
  // be exercised locally at all — the socket 404s against Vite — which is
  // exactly why a credential leak in the join ack went unnoticed.
  '/socket.io': {
    target: 'http://localhost:5000',
    changeOrigin: true,
    ws: true
  }
}

export default defineConfig({
  base: BASE,
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'json-summary', 'html'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/main.jsx', 'src/test/**'],
      thresholds: {
        lines: 95,
        statements: 95,
        functions: 95,
        branches: 95
      }
    }
  },
  server: {
    port: 3000,
    hmr: false,
    headers: cspHeaders({ dev: true }),
    proxy: apiProxy
  },
  // `vite preview` serves the built bundle — the same assets production serves,
  // with no dev server in front of them. It therefore carries the PRODUCTION
  // policy (no 'unsafe-inline' in script-src), which makes `npm run build &&
  // npm run preview` the rehearsal that step 3 of docs/development/csp-rollout.md
  // asks for. The API is proxied so it stays same-origin under connect-src 'self'.
  preview: {
    port: 3100,
    headers: cspHeaders({ dev: false }),
    proxy: apiProxy
  }
})
