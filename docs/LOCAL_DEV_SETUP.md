# Local Development Setup — Heart of Virtue

This guide walks you through starting the Flask API backend and React frontend locally for
browser-based play and testing. The game is web-only; there is no terminal play mode.

## Prerequisites

- **Python 3.11** (installed and on PATH). CI runs 3.11 and `pyproject.toml` targets
  `py311`. It matters beyond convention: the save allow-list manifest is derived from
  `__module__`, which CPython moves between releases, so regenerating it on a newer
  interpreter fixes your box by breaking CI (`.claude/rules/saves-persistence.md`).
- **Node.js 22** (installed and on PATH, required for npm) — the version CI uses.
- **git** (installed)

Verify your setup:
```bash
python --version      # Python 3.11.x
node --version        # Node 22.x
npm --version
```

## Step 1: Install Python Dependencies

From the project root:

```bash
pip install -r requirements-dev.txt
```

`requirements-dev.txt` pulls in `requirements.txt` (engine) and `requirements-api.txt`
(Flask, Socket.IO, LibSQL, crypto) and adds pytest, flake8, black and the harness tooling.
**`requirements-api.txt` alone is not enough to run the game** — it is the production-API
set and omits the engine's own dependencies.

**Optional: if using a virtual environment**:
```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# Windows: .venv/Scripts/activate
pip install -r requirements-dev.txt
```

## Step 2: Configure Environment

Copy `.env.example` to `.env` and fill in what you need — it documents every variable:

```bash
cp .env.example .env
```

For a plain local run, `FLASK_ENV=development` and `PORT=5000` are enough.

There is deliberately **no `FLASK_DEBUG`**. Every config class pins `DEBUG` itself and
`tools/run_api.py` passes that value to `socketio.run()` explicitly, so the variable never
had any effect here — `FLASK_ENV` is the knob that actually selects development vs.
production behaviour.

`HOST` is optional and defaults to `127.0.0.1`, which is loopback only. If you need to
reach the dev server from another machine, a phone, or a container, set `HOST=0.0.0.0` —
but understand what you are exposing: with `DEBUG` on, Werkzeug serves an interactive
`/console` and a full source traceback on every 500, so `0.0.0.0` hands both to everything
on the network.

`.env` is loaded by `src/env_bootstrap.load_project_env()`, which resolves the path from
`__file__` rather than the working directory — so it is found no matter where you start
the process from. Never commit it.

## Step 3: Install Frontend Dependencies

From the `frontend/` directory:

```bash
cd frontend
npm install
```

## Step 4: Run API Server (Terminal 1)

```bash
python tools/run_api.py
```

You should see:
```
============================================================
Heart of Virtue API - DEVELOPMENT
============================================================
Environment: development
Debug: true
Host: 127.0.0.1
Port: 5000
URL: http://localhost:5000
Health: http://localhost:5000/health
API Info: http://localhost:5000/api/info
============================================================
```

### Starting with a different game config

```bash
python tools/run_api.py config_combat_testing.ini
# or:
CONFIG_FILE=config_combat_testing.ini python tools/run_api.py
```

The positional argument wins over the `CONFIG_FILE` env var, which wins over the
`config_dev.ini` default. The root `config_*.ini` files select the starting map, party,
equipment and combat flags. Test maps (the combat arena, shop and chest maps) have **no
link from the main world**, so a config that sets `startmap` is the only way to reach them
— the arena roster table is in root `CLAUDE.md`.

## Step 5: Run Frontend Dev Server (Terminal 2)

In another terminal, from the `frontend/` directory:

```bash
npm run dev
```

You should see:
```
VITE v6.x.x  ready in xxx ms

➜  Local:   http://localhost:3000/games/HeartOfVirtue/
```

The Vite dev server proxies API calls from `http://localhost:3000/api/*` to
`http://localhost:5000/api/*`.

## Step 6: Open Browser

Navigate to `http://localhost:3000/games/HeartOfVirtue/`. You'll see the login page —
create a test account, or use the auto-login if you're running in test mode.

---

## Debugging Tips

**Browser console** (F12): client-side errors, plus the Network tab for the actual API
request and response.

**Backend logs**: the terminal running `python tools/run_api.py`. Debug is on in
development, so exceptions print full tracebacks and code reloads on save. Structured
JSONL logs land under `logs/`.

**Werkzeug's reloader can drop environment variables** — if a feature flag
(`COMBAT_SOCKET_STREAMING`, say) appears not to take effect, re-run with the reloader off
before believing it.

## Stopping Servers

`Ctrl+C` in each terminal.

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'flask'"

→ Ensure you've run `pip install -r requirements-dev.txt`, and that the virtualenv you
installed into is the one that's active.

### "command not found: npm"

→ Node.js is not installed or not on PATH. Download from [nodejs.org](https://nodejs.org/)

### Frontend won't connect to backend

→ Confirm the API is up: visit `http://localhost:5000/health` in a browser.
→ Check the browser console (F12) for CORS errors or connection failures.

### "Port 5000 already in use"

→ Kill the process (`lsof -i :5000` on macOS/Linux, `netstat -ano | findstr :5000` on
Windows), or start elsewhere: `PORT=5001 python tools/run_api.py`

### "Port 3000 already in use"

→ Edit `frontend/vite.config.js` and change `port: 3000`.

---

## Next Steps

- Run the suites: `python -m pytest -q` and `cd frontend && npm test -- --run`.
- Exercise the real API in-process: `python tools/bug_hunt.py [--scenario NAME]`.
- Real-browser QA: `python tools/inquisitor.py` (setup in `docs/qa/inquisitor.md`).

---

## Environment Summary

| Component | Port | URL |
|-----------|------|-----|
| Flask API | 5000 | http://localhost:5000 |
| React Frontend | 3000 | http://localhost:3000/games/HeartOfVirtue/ |
| API Health Check | 5000 | http://localhost:5000/health |

The API binds `127.0.0.1` unless `HOST` says otherwise, so the URLs above work from this
machine only. See Step 2 for what `HOST=0.0.0.0` exposes.

`/health` returns `{"status": "healthy"}` plus a `sessions` gauge — but the gauge is only
present under a TESTING or DEBUG config. The route has no authentication, and on a public
deployment a live session count for a single-player game is an occupancy oracle: anyone
can poll it and watch the developer come and go. A production monitor that reads the
`sessions` key must tolerate its absence, or read the number from an authenticated route
instead.

Frontend proxy routes:
- `/api/*` → `http://localhost:5000/api/*`
- `/games/HeartOfVirtue/api/*` → `http://localhost:5000/api/*`
