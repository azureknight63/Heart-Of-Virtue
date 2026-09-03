# Content-Security-Policy rollout (issue #492)

Status: **Report-Only.** Nothing is blocked yet. The policy is emitted, browsers
report what *would* have been blocked, and the reports land in the normal debug
log feed. Flipping it to enforcing is a separate, checklisted change — see
[Follow-up: switching to enforcing](#follow-up-switching-to-enforcing).

## Where the policy lives

`src/resources/csp-policy.json` is the single source of truth for the directive
data. Three servers read it and emit the header; none of them restates the
directive list:

| Surface | Emitter | Covers |
|---|---|---|
| Vite dev server | `frontend/vite.config.js` (`server.headers`, dev relaxations on) | the SPA **document** during development and QA runs |
| `vite preview` (port 3100) | `frontend/vite.config.js` (`preview.headers`, **production** policy) | the *built* bundle — the local rehearsal for production |
| Flask API | `src/api/security_headers.py` (`after_request`) | every `/api/*` response, plus any HTML Werkzeug renders |
| Production static host | not configured from this repo — snippet below | the SPA document in production |

### Why a header and not a `<meta>` tag

A `<meta http-equiv="Content-Security-Policy-Report-Only">` element is ignored
by browsers: the CSP spec permits only the enforcing header name in markup, and
Chrome logs a console error when a report-only policy arrives that way. Since
the rollout starts report-only, a meta tag is not an option today. It becomes
the natural fallback for the production document once the policy is enforcing.

### Why the Flask header alone isn't sufficient

`deploy.ps1` untars `frontend/dist` into the web server's document root; Flask
only serves `/api`. So the Flask `after_request` header never reaches the HTML
document in production. It is still the right home for the API's own responses,
it is where the policy moves wholesale if Flask ever serves the SPA, and it
keeps the policy composition tested in Python. The production document needs the
web-server snippet below.

## The directives, and why each one is what it is

```
default-src 'self'
base-uri 'self'
object-src 'none'
frame-src 'none'
frame-ancestors 'self'
form-action 'self'
script-src 'self'
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com
img-src 'self' data:
font-src 'self' https://fonts.gstatic.com
media-src 'self'
connect-src 'self'
report-uri /api/logs/csp-report
```

| Directive | Rationale |
|---|---|
| `default-src 'self'` | Backstop for anything not named below. |
| `base-uri 'self'` | Blocks an injected `<base>` from repointing every relative URL in the app. |
| `object-src 'none'` | No plugins, ever. |
| `frame-src 'none'` | The SPA renders no iframes. |
| `frame-ancestors 'self'` | The build is deployed under `nexusfidei.dev` alongside WordPress, so a same-origin page embedding the game must keep working. Third-party framing (clickjacking) is blocked. Deliberately not `'none'`. |
| `form-action 'self'` | The login/register forms submit through XHR; nothing posts off-origin. |
| `script-src 'self'` | Vite's production build emits external module bundles only — no inline scripts, no `eval`. This is the directive that actually matters, and it carries no `unsafe-*` in production. |
| `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com` | See below. |
| `img-src 'self' data:` | `data:` is required by the lantern SVG inlined in `frontend/src/styles/landing.css`. |
| `font-src 'self' https://fonts.gstatic.com` | Google Fonts serves the font files; `@fontsource` faces are bundled and same-origin. No `data:` faces exist. |
| `media-src 'self'` | All SFX/BGM are same-origin files under `public/assets/sounds/`. |
| `connect-src 'self'` | `VITE_API_URL` is a same-origin path (`/games/HeartOfVirtue/api`), so REST and the Socket.IO polling transport are both same-origin. |

### Retained `unsafe-*`, and the case for each

**`style-src 'unsafe-inline'` — retained, production included. Unavoidable.**
Two independent reasons:

1. The codebase's house style is React inline `style={{...}}` props, used in
   essentially every component. Those become element `style` attributes, which
   CSP governs through `style-src-attr`; nonces and hashes do not apply to
   attributes, so the only ways out are `'unsafe-hashes'` (which is weaker and
   needs a hash per distinct attribute value) or rewriting every component.
2. Tailwind and Vite inject `<style>` elements at runtime in development.

Risk accepted: style injection is a materially weaker primitive than script
injection — it cannot execute code — and the app's only HTML sink
(`CombatLog.jsx`) is DOMPurify-sanitised, which strips scriptable attributes.
`script-src` stays clean, which is where the real exposure would be.

**`script-src 'unsafe-inline'` — development only. Never in production.**
`@vitejs/plugin-react` injects the React Refresh preamble into the dev
document as an inline module script, and the dev server has no build step that
could hash it. This lives in `dev_additions` in the policy JSON, gated on
`CSP_DEV_RELAXATIONS`, which `ProductionConfig` pins to `False`.

**`connect-src ws: wss: http://localhost:5000 http://127.0.0.1:5000` —
development only.** For the Vite client and for a dev setup that points
`VITE_API_URL` straight at the API port instead of through the proxy.

**No `unsafe-eval` anywhere,** in any mode.

## Where violation reports go

`report-uri` points at `POST /api/logs/csp-report` (`src/api/routes/logs.py`) —
spelled with the deployment's base path
(`/games/HeartOfVirtue/api/logs/csp-report`) everywhere the *browser* resolves
it, since a report URI is resolved against the document, not against whatever
path Flask happens to see behind the proxy. `ProductionConfig.CSP_REPORT_URI`
and `frontend/vite.config.js` both carry the prefixed form; only the local
`Config` default is the bare `/api/...` a directly-addressed dev API answers on.

### Why `report-uri` alone, and not also `report-to`

`report-uri` is deprecated, so advertising the newer Reporting API group
alongside it looks like the obvious hedge against split browser support. It is
not: **shipping both delivers nothing.** `report-to` takes precedence over
`report-uri` whenever both are present, and Chromium then hands the report to
the Reporting API, which batches delivery and does not treat a plain-HTTP origin
as an eligible endpoint at all.

Measured in headless Chromium against this app — one forced violation
(an `<img>` pointing off-origin), 25 s of wait, counting POSTs to the sink:

| Policy | Report POSTs |
|---|---|
| `report-uri` only | **1** |
| `report-to` only | 0 |
| both | 0 |

A report-only rollout whose reports never arrive is worse than no rollout at
all: an empty log reads as "clean policy" and nothing is learned, which would
have made step 2 of the checklist below vacuous. `report-uri` is also the only
transport Firefox and Safari implement. So it ships alone; re-adding `report-to`
is a follow-up, gated on re-running that A/B over HTTPS.

The route still normalises **both** payload shapes — the legacy
`application/csp-report` envelope and the Reporting API's
`application/reports+json` list — so a future `report-to` flip needs no
server-side change.

Reports are written into the existing browser-log JSONL stream with
`event: csp.violation`, reusing that route's sanitisation, field caps and
per-day file bucketing — so a violation shows up in the same feed as the console
output from the page load that produced it:

```bash
python tools/logcat.py --tail --grep csp.violation
```

The route is unauthenticated, as it must be: the browser sends these, not the
app, and it attaches no credentials. It always answers `204` — there is no
client left to act on an error, and arguing with the browser only produces
console noise. Both the report count per request and the retained fields are
bounded so the endpoint cannot be used as arbitrary log storage.

Note the client-side browser logger (`frontend/src/utils/logger.js`) is
DEV-gated and unrelated: CSP reports are sent by the browser itself and arrive
in every environment where the header is set.

## Production web-server snippet

Add to the `location` block that serves `/games/HeartOfVirtue/`:

```nginx
add_header Content-Security-Policy-Report-Only "default-src 'self'; base-uri 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'self'; form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data:; font-src 'self' https://fonts.gstatic.com; media-src 'self'; connect-src 'self'; report-uri /games/HeartOfVirtue/api/logs/csp-report" always;
```

Regenerate that string rather than hand-editing it — it is the output of:

```bash
python -c "from src.api.security_headers import build_csp; print(build_csp(dev=False, report_uri='/games/HeartOfVirtue/api/logs/csp-report'))"
```

## What has actually been measured in a browser

Recorded so a later reader can tell verification from assertion. Headless
Chromium 141 (a cached Playwright build; the Playwright CDN is blocked in this
environment, so `python -m playwright install chromium` fails and
`tools/inquisitor.py` was driven manually rather than through its own launcher).
Plain-HTTP origins, real Vite dev server on :3000 proxying a real Flask API on
:5000.

**Confirmed:**

* The report-only header is present on the Vite **document** and on Flask API
  responses, and the two directive sets are identical apart from the report-URI
  prefix each surface needs.
* Loading the SPA landing page produces **no violations from the app itself** —
  the only report in the run was one deliberately forced by appending an
  off-origin `<img>`.
* That forced violation round-trips end to end: browser → `report-uri` →
  `POST /api/logs/csp-report` → one `event: csp.violation` line in
  `logs/browser/<date>_bucket34.jsonl`, carrying `violated-directive: img-src`
  and `disposition: report`.
* The transport A/B was re-run independently and reproduces exactly: one forced
  violation, 25 s of wait, `report-uri` only → **1** POST, `report-to` only →
  **0**, both → **0**.
* No console error about an ignored policy, which is the symptom a `<meta>`
  report-only tag would have produced.
* A signed-in walkthrough — session established, `/game` loaded, a real room
  rendered with its audio, HUD and event queue running — produced **no new
  violations at all**: the sink still held only the forced `img-src` report from
  earlier in the same run. That covers the landing page, the authenticated
  exploration view and the API calls behind it under `connect-src 'self'`.

**Not yet measured — what step 1 of the checklist below still asks for:** the
rest of the walkthrough (combat with the Socket.IO beat stream, shop, inventory,
save/load), and the `npm run build && npm run preview` rehearsal against the
production `script-src`. Nothing observed so far predicts a violation there, but
nothing observed so far *rules one out* either, and combat is the only surface
that exercises the Socket.IO transport under `connect-src`.

The registration form itself was not exercised: it needs the Turso database,
which is not reachable from this environment. The session was established
through the `/api/test/session` bypass instead, which drives the same client
code past the login screen.

## FOLLOW-UP: switching to enforcing

**This is not done. Do not flip it without working through the list.**

1. Run the app in a real browser under the report-only policy — the dev server
   already sets it — and exercise: landing → register/login → main menu →
   exploration → combat (including the Socket.IO beat stream) → shop →
   inventory → save/load → logout.
2. `python tools/logcat.py --grep csp.violation` must be empty for that run.
   Every violation is either a directive that needs widening or a genuine
   finding — resolve each one before continuing.
3. Repeat against a production build (`npm run build && npm run preview`, port
   3100), which is the only configuration that exercises the *production*
   `script-src` (no `'unsafe-inline'`). `preview` proxies the API the same way
   the dev server does, so `connect-src 'self'` holds there too.
4. Flip the switches:
   - Flask: `CSP_REPORT_ONLY = False` in `src/api/config.py` (or the
     `CSP_REPORT_ONLY=false` environment variable).
   - Vite: change the header name in `cspHeaders()` in
     `frontend/vite.config.js`.
   - The production web server: change `Content-Security-Policy-Report-Only` to
     `Content-Security-Policy` in the snippet above.
5. Only once enforcing, a `<meta http-equiv="Content-Security-Policy">` tag in
   `frontend/index.html` becomes a worthwhile belt-and-braces fallback for the
   case where the web-server header is lost in a config change. Note the meta
   form silently ignores `frame-ancestors`, `report-uri` and `sandbox`, so it is
   a fallback and not a replacement.
6. Consider `upgrade-insecure-requests` at the same time. It is omitted today
   because it breaks plain-HTTP local development.
7. Re-run the transport A/B over HTTPS before considering `report-to` again.
   The measurement above was taken on a plain-HTTP origin, where Chromium
   refuses Reporting-API endpoints outright; over HTTPS the result may differ.
   Until it is re-measured and shown to deliver, adding `report-to` back would
   silence reporting entirely.
