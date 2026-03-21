# DevOps Audit Report
**Branch:** master | **Commit:** 29c9488 | **Date:** 2026-03-18 | **Scope:** Full audit

Working tree has 4 modified worktree entries in `.claude/worktrees/` — not production code, but see DEVOPS-11.

---

## Executive Summary

Heart of Virtue's API layer is structurally sound with no committed secrets and sensible CORS lockdown, but it has **zero CI gates on pull requests** — the only automated workflow runs weekly. Combined with a missing `.env.example`, an unsafe `DEBUG` default that's a string-coercion footgun, and no production-grade server configured, the project would be unsafe to deploy as-is. Most gaps are small-team-appropriate fixes, not enterprise overengineering.

---

## Critical Findings (Fix Before Next Deploy)

**1. No CI on pull requests — zero automated gates**
The only workflow (`bug-hunt.yml`) runs on a weekly schedule or manual trigger. There is no `ci.yml` that runs tests or linting on PRs. Code lands in `master` with no automated checks.

**2. `DEBUG` defaults to `True` in base `Config` via string-coercion footgun**
`src/api/config.py:12`: `DEBUG = os.environ.get("FLASK_DEBUG", True)`. The default is boolean `True`. If the environment sets `FLASK_DEBUG=False`, `os.environ.get()` returns the **string** `"False"`, which is truthy — debug mode stays on. `ProductionConfig` overrides this correctly, but only if `ProductionConfig` is explicitly selected at startup. Any code path that falls through to the base `Config` (e.g., tests, ad-hoc runs) runs in debug mode by default.

**3. `SECRET_KEY` falls back to `os.urandom(24).hex()` — sessions die on restart**
`src/api/config.py:11`: `SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(24).hex()`. Every server restart generates a new key. All in-flight sessions are immediately invalidated. This is acceptable for dev but catastrophic in any persistent deployment.

**4. No `.env.example`**
`.env` exists and is gitignored (correctly), but `.env.example` does not exist. A fresh clone gives the developer no guidance on what env vars are required. Required vars identified from source:
- `SECRET_KEY`
- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`
- `FLASK_ENV` / `FLASK_DEBUG`
- `ANTHROPIC_API_KEY` (Mynx NPC feature)
- `OPENAI_API_KEY` / `OPENROUTER_API_KEY` (AI integration)
- `MYNX_LLM_ENABLED`, `MYNX_LLM_PROVIDER`

---

## Important Findings (Fix This Sprint)

**5. Dev tools committed into production dependency files**
`requirements-api.txt` includes `pytest==9.0.2`, `pytest-asyncio==1.3.0`, `pytest-cov==7.0.0`, `black==25.12.0`, `flake8==7.3.0`. `requirements.txt` includes `playwright>=1.49.0`. There is no `requirements-dev.txt`. Every production install drags in the test and lint stack.

**6. `requirements.txt` has mostly unpinned or loosely-pinned Python deps**
`requirements.txt` uses `>=` ranges (e.g., `openai>=1.0.0,<2.0.0`, `Pillow>=12.0.0`, `asciimatics>=1.15.0`, `bleach>=6.0.0`, `python-dotenv>=1.0.0`). Builds are non-reproducible. A future minor release of any of these could break the game silently. `requirements-api.txt` is properly pinned; `requirements.txt` is not.

**7. 664 MB of stale agent worktrees on disk**
Four abandoned agent worktrees in `.claude/worktrees/` total 664 MB. They are not gitignored (they appear as modified in `git status`). The `.gitignore` has no entry for `.claude/worktrees/`.

| Worktree | Size | Branch |
|---|---|---|
| agent-a05ca95b | ~170 MB | worktree-agent-a05ca95b |
| agent-a2c37b46 | ~165 MB | worktree-agent-a2c37b46 |
| agent-a52edf30 | ~165 MB | worktree-agent-a52edf30 |
| agent-ad1ffbe1 | ~165 MB | worktree-agent-ad1ffbe1 |

**8. No production web server configured**
`requirements-api.txt` has no `gunicorn`, `uwsgi`, `eventlet`, or `gevent`. SocketIO uses `async_mode='threading'`. Flask's dev server (`socketio.run(app)`) is single-threaded and not safe for production. There is no `Procfile` or deployment config.

**9. Audio archive files tracked in git — ~100+ MB of WAV files**
`frontend/public/assets/sounds/archive/` contains 8 WAV files totalling ~100 MB, tracked in git. The `.gitignore` has an entry `frontend/public/assets/sounds/archive` but these files predate it and are still tracked. Large binaries in git bloat every clone and slow CI.

**10. SocketIO verbose logging on by default — will flood production logs**
`src/api/app.py:37`: `SocketIO(app, ..., logger=True, engineio_logger=True)`. Every socket event produces verbose output. This should be gated behind `DEBUG` or a log-level config.

**11. `SESSION_COOKIE_SECURE = False` in base `Config`**
`src/api/config.py:16`. `ProductionConfig` sets this to `True`, but only if `ProductionConfig` is explicitly used. The base class should not default to insecure.

---

## Recommended Improvements (Backlog)

**12. GitHub Actions pinned by tag, not commit SHA**
`bug-hunt.yml` uses `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`. Tag-pinned actions can be redirected by a supply-chain compromise. For a small indie project this is low risk, but trivial to fix: pin to commit SHAs and comment the version.

**13. No health check endpoint**
There is no `/health` or `/ping` route. Any load balancer, uptime monitor, or Docker health check would need to hammer a real API endpoint.

**14. No `dependency-review.yml` or Dependabot config**
GitHub's built-in dependency review action is free and flags known CVEs on PRs automatically. Missing for both Python and Node deps.

**15. Frontend deps use `^` (caret) — not reproducible**
`package.json` uses caret ranges for all dependencies (e.g., `"react": "^18.2.0"`). `npm install` at different times may install different versions. Consider `npm ci` (with a committed `package-lock.json`) in CI.

**16. `item.exec()` on dynamic interaction strings**
`src/player/_inventory.py:339`: `item.exec(interaction + "(self)")`. This calls a method named by the string `interaction` on an item object — it's `getattr`-style dispatch, not `exec()` in the built-in sense. Low risk since `interactions` comes from internal item definitions, not user input. Still worth auditing if item data ever becomes user-editable.

**17. `subprocess.call(shell=True)` with f-string in `open_terminal.py`**
`src/open_terminal.py:13`: `subprocess.call(f"start /wait python animations.py {animation}", shell=True)`. If `animation` ever receives external input, this is a command injection vector. Currently `animation` comes from internal callers only. Low risk now; worth adding a safelist check.

**18. `quest_rewards` admin routes gated only by session, not by role**
`/api/quest-rewards/gold`, `/api/quest-rewards/experience`, `/api/quest-rewards/item` validate a session exists but do not check if the caller has admin/GM permissions. Any authenticated user can award themselves arbitrary gold, XP, or items by calling these endpoints directly. If these are dev/debug routes, they should be gated by `FLASK_ENV=testing` or removed from production builds.

---

## Dimension Grades

| Dimension | Grade | Notes |
|---|---|---|
| Secrets & Credentials | B | No committed secrets; .env gitignored correctly; missing .env.example is the main gap |
| Dependency Health | C | requirements.txt unpinned; dev tools in prod deps; no requirements-dev.txt |
| CI/CD Coverage | D | Zero PR gates; only a weekly bug-hunt workflow; no test, lint, or build-check on merge |
| Environment Management | C | DEBUG defaults True; SECRET_KEY regenerates on restart; SESSION_COOKIE_SECURE defaults False |
| Deployment Readiness | D | No production server; no health endpoint; verbose SocketIO logging; no Procfile |
| Security Posture | B | CORS locked to localhost; auth validated on all routes checked; quest_rewards role gap noted |
| Operational Hygiene | C | 664 MB stale worktrees; 100+ MB audio files in git; worktrees not gitignored |

---

## Findings Detail

### DEVOPS-1: No CI gates on pull requests
**Severity:** Critical
**Dimension:** CI/CD Coverage
**Location:** `.github/workflows/` (only `bug-hunt.yml` exists)

**Problem:**
Every commit to `master` lands without any automated test or lint verification. The bug-hunt workflow runs weekly on a schedule or via manual trigger — it does not run on push or PR. Regressions ship undetected until the next Monday morning run.

**Remediation:**
Create `.github/workflows/ci.yml`:
```yaml
name: CI
on:
  push:
    branches: [master, web-api]
  pull_request:
    branches: [master]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements-api.txt
      - run: pytest -q
      - run: black --check src/
      - run: flake8 src/
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci && npm test -- --run
```

**Effort:** Small (< 1 hr)

---

### DEVOPS-2: `DEBUG` defaults to `True` via `os.environ.get()` string-coercion footgun
**Severity:** Critical
**Dimension:** Environment Management
**Location:** `src/api/config.py:12`

**Problem:**
`DEBUG = os.environ.get("FLASK_DEBUG", True)` — the default is boolean `True`. If a developer sets `FLASK_DEBUG=False` in their `.env`, `os.environ.get()` returns the string `"False"`, which Python evaluates as truthy. Debug mode stays on silently.

**Remediation:**
```python
DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() not in ("0", "false", "no")
```
Or, simpler — remove the env-var override from the base class and rely on the subclass hierarchy (`DevelopmentConfig`, `ProductionConfig`) exclusively.

**Effort:** Small (< 1 hr)

---

### DEVOPS-3: `SECRET_KEY` falls back to ephemeral random value
**Severity:** Critical
**Dimension:** Environment Management / Deployment Readiness
**Location:** `src/api/config.py:11`

**Problem:**
Without `SECRET_KEY` in the environment, Flask generates a new random key on every startup. Flask sessions (signed cookies) are invalidated on restart. For a persistent deployment this makes sessions useless.

**Remediation:**
Generate a stable key for non-dev environments and document it in `.env.example`. Consider failing fast if `SECRET_KEY` is missing in production:
```python
_secret = os.environ.get("SECRET_KEY")
if not _secret and os.environ.get("FLASK_ENV") == "production":
    raise RuntimeError("SECRET_KEY must be set in production")
SECRET_KEY = _secret or os.urandom(24).hex()  # dev fallback only
```

**Effort:** Small (< 1 hr)

---

### DEVOPS-4: No `.env.example`
**Severity:** Critical (onboarding / operational)
**Dimension:** Environment Management
**Location:** project root

**Problem:**
`.env` is correctly gitignored, but there is no `.env.example` to document required variables. New developers (or a fresh CI environment) have no way to know what to set.

**Remediation:**
Create `.env.example`:
```
# Flask
SECRET_KEY=changeme-generate-with-python-secrets-token-hex
FLASK_ENV=development
FLASK_DEBUG=true

# Database (Turso/LibSQL)
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your-turso-token

# AI integration (optional — set MYNX_LLM_ENABLED=0 to disable)
MYNX_LLM_ENABLED=0
MYNX_LLM_PROVIDER=openrouter
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

**Effort:** Small (< 1 hr)

---

### DEVOPS-5: Dev tools in production dependency files
**Severity:** Important
**Dimension:** Dependency Health
**Location:** `requirements-api.txt`, `requirements.txt`

**Problem:**
`requirements-api.txt` includes `pytest==9.0.2`, `pytest-asyncio==1.3.0`, `pytest-cov==7.0.0`, `black==25.12.0`, `flake8==7.3.0`. `requirements.txt` includes `playwright>=1.49.0`. Production installs carry 150+ MB of test/lint tooling and a full Chromium browser binary.

**Remediation:**
Create `requirements-dev.txt`:
```
-r requirements-api.txt
pytest==9.0.2
pytest-asyncio==1.3.0
pytest-cov==7.0.0
black==25.12.0
flake8==7.3.0
playwright>=1.49.0
```
Remove those packages from `requirements-api.txt`. Production: `pip install -r requirements-api.txt`. Dev/CI: `pip install -r requirements-dev.txt`.

**Effort:** Small (< 1 hr)

---

### DEVOPS-6: `requirements.txt` has unpinned Python deps
**Severity:** Important
**Dimension:** Dependency Health
**Location:** `requirements.txt`

**Problem:**
`openai>=1.0.0,<2.0.0`, `Pillow>=12.0.0`, `asciimatics>=1.15.0`, `bleach>=6.0.0`, `python-dotenv>=1.0.0` — all unpinned to exact versions. Builds at different times may differ. `requirements-api.txt` is correctly pinned; `requirements.txt` is not.

**Remediation:**
After installing and verifying, pin via `pip freeze > requirements.txt` (then manually remove dev tools). Or add exact pins manually.

**Effort:** Small (< 1 hr)

---

### DEVOPS-7: 664 MB of stale agent worktrees consuming disk and polluting git status
**Severity:** Important
**Dimension:** Operational Hygiene
**Location:** `.claude/worktrees/`

**Problem:**
Four agent worktrees (`agent-a05ca95b`, `agent-a2c37b46`, `agent-a52edf30`, `agent-ad1ffbe1`) total 664 MB and appear as modified in `git status`. They are not gitignored. Bloats working tree, confuses `git status`.

**Remediation:**
```bash
# Remove all four worktrees
git worktree remove --force .claude/worktrees/agent-a05ca95b
git worktree remove --force .claude/worktrees/agent-a2c37b46
git worktree remove --force .claude/worktrees/agent-a52edf30
git worktrees remove --force .claude/worktrees/agent-ad1ffbe1
```
Then add to `.gitignore`:
```
.claude/worktrees/
```

**Effort:** Small (< 1 hr)

---

### DEVOPS-8: No production web server — Flask dev server only
**Severity:** Important
**Dimension:** Deployment Readiness
**Location:** `requirements-api.txt`, `tools/run_api.py`

**Problem:**
`run_api.py` calls `socketio.run(app, ...)` which uses Flask's Werkzeug dev server. It is not safe for production: single-threaded, no process management, no graceful restart. SocketIO's `async_mode='threading'` works with standard WSGI but needs gunicorn + eventlet or gevent for real concurrency.

**Remediation:**
Add `gunicorn` and `eventlet` (or `gevent`) to `requirements-api.txt`. Create a `Procfile`:
```
web: gunicorn --worker-class eventlet -w 1 "src.api.app:create_app()[0]"
```
Gate the dev server to `FLASK_ENV=development` only.

**Effort:** Medium (half-day)

---

### DEVOPS-9: ~100 MB of WAV files tracked in git
**Severity:** Important
**Dimension:** Operational Hygiene
**Location:** `frontend/public/assets/sounds/`

**Problem:**
20+ audio files (WAV and MP3) are tracked in git, including an `archive/` subdirectory with draft versions totalling ~100 MB. Every `git clone` downloads this. CI is slow. The `.gitignore` has `frontend/public/assets/sounds/archive` but the files were committed before this rule and are still tracked.

**Remediation:**
Remove archive files from tracking (not from disk):
```bash
git rm --cached frontend/public/assets/sounds/archive/*
```
For the non-archive sounds, consider git-lfs (`git lfs track "*.wav"`) or serving from a CDN/object store. Long-term: audio assets do not belong in a git repo.

**Effort:** Medium (half-day to evaluate and implement LFS or CDN)

---

### DEVOPS-10: `quest_rewards` admin endpoints not role-gated
**Severity:** Important
**Dimension:** Security Posture
**Location:** `src/api/routes/quest_rewards.py:141,178,215`

**Problem:**
`/api/quest-rewards/gold`, `/api/quest-rewards/experience`, `/api/quest-rewards/item` validate that a session exists but do not check whether the session belongs to an admin or GM role. Any authenticated player can call these endpoints directly (e.g., via curl) to award themselves arbitrary resources.

**Remediation:**
If these are dev/debug routes only, gate them behind `FLASK_ENV=testing|development`:
```python
if not app.config.get("TESTING") and not app.debug:
    raise abort(404)
```
If they serve a legitimate gameplay function, add a role check.

**Effort:** Small (< 1 hr)

---

### DEVOPS-11: SocketIO verbose logging on by default
**Severity:** Improvement
**Dimension:** Deployment Readiness
**Location:** `src/api/app.py:37`

**Problem:**
`logger=True, engineio_logger=True` emits a log line for every socket frame. At any real traffic volume this floods the log aggregator and makes actual errors hard to find.

**Remediation:**
```python
socketio = SocketIO(
    app,
    cors_allowed_origins=app.config["CORS_ORIGINS"],
    async_mode='threading',
    logger=app.debug,
    engineio_logger=app.debug,
)
```

**Effort:** Trivial (< 15 min)

---

### DEVOPS-12: Actions pinned by tag, not commit SHA
**Severity:** Improvement
**Dimension:** CI/CD Coverage
**Location:** `.github/workflows/bug-hunt.yml`

**Problem:**
`uses: actions/checkout@v4` — tag-pinned. A compromised `@v4` tag could inject malicious code into the CI pipeline.

**Remediation:**
Pin to commit SHAs:
```yaml
uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5.6.0
uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02  # v4.6.2
```

**Effort:** Trivial (< 15 min)
