# Inquisitor — browser-mode QA harness

Moved out of `CLAUDE.md` on 2026-08-21. The commands stay in root `CLAUDE.md`; the setup and operating detail is here.

The Inquisitor harness (`tools/inquisitor.py`, `tools/inquisitor/`) drives the real React + Flask stack through a headless Chromium browser, catching UI rendering bugs and JS errors the API layer can't see. It runs a deterministic probe sequence — no Anthropic API key needed.

```bash
# Browser run (default — catches JS/rendering bugs)
python tools/inquisitor.py --headless --output tools/browser_findings.json

# Headed run (shows the browser window — useful for debugging)
python tools/inquisitor.py

# API-only (faster, no servers needed, misses UI bugs)
python tools/inquisitor.py --no-browser
```

## Prerequisites

```bash
pip install playwright asgiref          # asgiref makes async Flask routes work
python -m playwright install chromium   # downloads ~150 MB browser binary
```

**If the Playwright CDN is blocked** (CI/Docker): the harness auto-detects cached Chromium builds in `~/.cache/ms-playwright/` and uses the highest available one via `executable_path`. If Node.js Playwright is installed separately (e.g. for frontend tests), its cached browser will be reused.

## How auth works (no database required)

The browser layer starts Flask with `FLASK_ENV=testing`. In test mode, the app registers a `/api/test/session` endpoint (never active in production) that calls `session_manager.create_session()` directly — no Turso DB needed. The login flow tries the real registration form first; on failure it falls back to this endpoint.

**There is no guest mode.** Production requires registration; every real player session has a `db_user_id`. The "no db_user_id" path in the saves routes (which 403s cloud save operations) is only reachable via the test session bypass — i.e. QA/Inquisitor runs.

**There is no local autosave.** `hov_local_autosave` was retired in issue #489 — it was write-only (nothing ever restored from it, see #487) and added no real recovery. The cloud autosave (`is_autosave=TRUE` row per user, written every `AUTOSAVE_TICK_THRESHOLD` — 3 — movement/combat transitions) is the only save during active play, including QA runs that use the test session bypass; a QA session with no `db_user_id` (see above) has no autosave recovery at all.

## Known browser noise (filtered automatically)

These events appear in every run and are **not bugs**:
- `fonts.googleapis.com` / `fonts.gstatic.com` network failures — CDN is unreachable in offline environments; harmless in production.
- React Router future-flag warnings — v6→v7 migration notices, tracked upstream.

`get_page_errors` separates these into a `known_noise` key so the agent focuses only on `console_errors` and `network_failures` (the significant ones).

## Gotchas

- `asgiref` must be installed or all `async def` Flask routes (auth, saves) will crash with a 500 — they silently work in-process via the test client but fail under a real Werkzeug server. It is listed in `requirements-api.txt`.
- The Vite dev server is slow to compile on first boot; the harness pre-warms it with an HTTP request before opening the browser, so navigation doesn't race.
- Screenshots land in `tools/inquisitor_screenshots/<timestamp>/` (gitignored).
- Before filing a UI bug about blocked movement, missing exits, or unresponsive objects, read the "QA — known intentional behaviors" section in root `CLAUDE.md` — this is an RPG and many apparent dead ends are puzzles.
