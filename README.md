# Heart of Virtue

[![CI](https://github.com/azureknight63/heart-of-virtue/actions/workflows/ci.yml/badge.svg)](https://github.com/azureknight63/heart-of-virtue/actions/workflows/ci.yml)
[![Backend Coverage](https://img.shields.io/badge/backend--coverage-96%25-brightgreen?style=flat-square)](docs/coverage/coverage-dashboard.md)
[![Frontend Coverage](https://img.shields.io/badge/frontend--coverage-99%25-brightgreen?style=flat-square)](docs/coverage/coverage-dashboard.md)
[![License: PolyForm NC](https://img.shields.io/badge/code-PolyForm%20NC-blue?style=flat-square)](LICENSE-CODE)

Adventure RPG. Follow former crusader Jean Claire into a strange and dangerous world
as he tries to make sense of his situation and piece together the fragments of his
tragic past.

This is a text RPG — all graphics are represented using text characters! The human
mind is far better at producing images than any pixel editor.

If you like this project and are interested in contributing, please drop me a message.

## How the game runs

**Heart of Virtue is played entirely in the browser.** A Flask REST API wraps the
Python game engine, and a React single-page app is the client. The original
terminal/CLI play mode has been removed — there is no `python src/game.py` entry
point any more.

```
┌─────────────────────┐   HTTP/JSON    ┌──────────────────────┐
│  React SPA (Vite)   │ ─────────────► │  Flask API (:5000)   │
│  localhost:3000     │ ◄───────────── │  src/api/            │
└─────────────────────┘   Socket.IO    └──────────┬───────────┘
                                                  │ in-process
                                       ┌──────────▼───────────┐
                                       │  Python game engine  │
                                       │  src/ (source of     │
                                       │  truth for all logic)│
                                       └──────────┬───────────┘
                                                  │
                                       ┌──────────▼───────────┐
                                       │  LibSQL / Turso      │
                                       │  accounts + saves    │
                                       └──────────────────────┘
```

The engine is the source of truth; the API layer adapts it and never reimplements
game logic. Engine output flows through a **narration sink** (`src/narration.py`) as
structured `{text, color, type}` messages rather than terminal `print`, and the API
reads those messages directly instead of scraping stdout.

## Requirements

| Component | Version |
|---|---|
| Python | 3.13 (see `.python-version`; CI runs 3.11, so keep code 3.11-compatible) |
| Node.js | 22 (per CI) |

Dependency manifests:

| File | Contents |
|---|---|
| `requirements.txt` | Engine + harness runtime deps |
| `requirements-api.txt` | Production API deps (Flask, Socket.IO, LibSQL, crypto) |
| `requirements-dev.txt` | Everything above plus pytest, flake8, Playwright |

```bash
pip install -r requirements-dev.txt     # development
pip install -r requirements-api.txt     # production API only
```

## Quick Start

**1. Configure the environment**

```bash
cp .env.example .env
```

Then edit `.env`. Nothing is required for local play except a `SECRET_KEY`;
`TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` are needed for accounts and cloud saves,
and `GITHUB_TOKEN` for the in-game feedback button. See `.env.example` for the full,
commented list. `ENCRYPTION_KEY` **is** required when `FLASK_ENV=production` — the
app fails closed without it.

**2. Start the backend API**

```bash
python tools/run_api.py            # http://localhost:5000
```

Pass a config file to override the starting map, position, equipment, and story flags:

```bash
python tools/run_api.py config_eastern_descent_test.ini
```

Omitting the argument falls back to `CONFIG_FILE` from `.env`, and then to the
engine's built-in defaults. The configs tracked in the repo root are
`config_ch01_combat_testing.ini`, `config_combat_testing.ini`,
`config_eastern_descent_test.ini`, `config_grondia_beta.ini`, and
`config_shop_testing.ini`.

**3. Start the frontend dev server**

```bash
cd frontend
npm install
npm run dev                        # http://localhost:3000
```

Open **http://localhost:3000** and register an account to play. There is no guest
mode — every real session is backed by a registered user.

**One-shot (Windows/PowerShell):** `.\tools\start_servers.ps1 [CONFIG_FILE]` launches
the API, the frontend, and the log viewer together (opt out of the last with
`-NoLogcat`).

See [`docs/LOCAL_DEV_SETUP.md`](docs/LOCAL_DEV_SETUP.md) for a longer walkthrough.

## Project Layout

```
src/                       # Python game engine — source of truth
├── api/                   # Flask API layer
│   ├── app.py             #   create_app() factory
│   ├── routes/            #   REST blueprints (auth, world, combat, inventory, …)
│   ├── services/          #   GameService, SessionManager, AuthService
│   ├── serializers/       #   entity → JSON
│   ├── combat_adapter.py  #   engine combat → JSON bridge
│   └── middleware/        #   auth
├── moves/                 # Combat abilities, split by weapon class (93 classes)
├── player/, npc/          # Player and NPC packages (share the Combatant base)
├── combatant.py           # Shared resistance / status-effect logic
├── states.py              # Status effects
├── items.py, objects.py   # Item and world-object definitions
├── universe.py, tiles.py  # World / map system
├── narration.py           # Structured narration sink (replaces terminal print)
├── secure_pickle.py       # Hardened save deserialization
└── resources/maps/        # 17 map definitions (JSON)

frontend/src/
├── pages/                 # Landing, Login, MainMenu, Game
├── components/            # Battlefield, WorldMap, CombatLog, PlayerStatus, …
├── hooks/                 # useApi, useCombat, useMobile, useCombatSocket, …
├── api/                   # Axios client + endpoint definitions
└── context/               # Auth, Audio

tools/                     # Dev tooling: run_api, logcat, bug_hunt, inquisitor, fuzzers
docs/                      # Architecture, API reference, lore, coverage
```

API blueprints mount under `/api` (`/api/combat`, `/api/shop`, `/api/npc/chat`,
`/api/feedback`, `/api/logs`, …). A `/api/debug` blueprint exists but registers
**only** when `app.config["TESTING"]` is set, so it is unreachable in production.

## Development

### Tests

```bash
python -m pytest -q                                   # backend (fast)
python -m pytest --cov=src --cov=ai --cov-report=term-missing
cd frontend && npm test -- --run                      # frontend
cd frontend && npm test -- --run --coverage
```

Use `python -m pytest`, not bare `pytest` — the virtualenv may not expose the
`pytest` binary on PATH, which causes silent import failures.

`pytest.ini` sets `-n auto --dist loadfile`, so the backend suite runs in parallel;
pass `-n0` when debugging a single test. The `tests/api/`, `tests/broken/`, and
`tests/uat/` directories are excluded from the default run — full-app integration
tests that build a real session/universe belong in `tests/api/`, because creating a
real session mutates module-level registries and pollutes downstream tests.

### Coverage

| Layer | Current | CI minimum |
|---|---|---|
| Backend (Python) | 96% | 85% (`--cov-fail-under=85`) |
| Frontend (React) | 99% lines, ~95.3% branches | 95% (lines/statements/functions/branches) |

Frontend thresholds are enforced by `coverage.thresholds` in
`frontend/vite.config.js`; the build fails below them. See
[`docs/coverage/coverage-dashboard.md`](docs/coverage/coverage-dashboard.md).

### Linting

```bash
flake8 --extend-ignore=E501 src/       # backend (as CI runs it)
cd frontend && npm run lint            # frontend
```

`black` formats `src/` only — never run it across `tests/`.

### Debug logging

Backend and browser logs share one JSONL envelope
(schema authority: `src/api/structured_log.py`). `tools/run_api.py` writes
`logs/backend/<utc-date>.jsonl`; the browser console ships to `logs/browser/*.jsonl`.

```bash
python tools/logcat.py --tail          # merged, colorized live feed
# --json  --errors  --grep X  --since 5m  --session <id>  --src be|fe  --level  --limit N
```

New frontend debug output goes through `logger.event(name, data)` /
`logger.eventOnChange` (`frontend/src/utils/logger.js`), not bare `console.log`.

### Automated QA harnesses

```bash
python tools/bug_hunt.py                                    # in-process, all scenarios
python tools/bug_hunt.py --scenario phase3                  # one scenario
python tools/bug_hunt.py --headless --output bugs.json      # machine-readable

python tools/inquisitor.py --headless --output findings.json  # real browser (Playwright)
python tools/inquisitor.py --no-browser                       # API only, faster
```

The Inquisitor drives the real React + Flask stack through headless Chromium to catch
rendering bugs and JS errors the API layer can't see. It needs
`pip install playwright asgiref` and `python -m playwright install chromium`.
`asgiref` is required for the `async def` Flask routes (auth, saves) to work under a
real server. Additional fuzzers live in `tools/` (save, map, config, serializer,
inventory, combat-command, API).

### CI

| Workflow | What it does |
|---|---|
| `.github/workflows/ci.yml` | pytest + flake8 (backend), vitest (frontend) |
| `.github/workflows/test-coverage.yml` | Coverage with `--cov-fail-under=85` |
| `.github/workflows/bug-hunt.yml` | Automated bug-hunt harness |

## Save Files & Security

> **Deprecation notice:** the current `.sav` / cloud save format is Python
> **pickle**. Loading a pickle executes arbitrary code by design, so save files
> are only safe as **trusted local artifacts belonging to the player who
> created them** — never load a `.sav` obtained from an untrusted source.
>
> Deserialization is hardened by `src/secure_pickle.py`: an allow-list of engine
> classes, opt-in strict mode (`HOV_STRICT_UNPICKLE`), a size cap, a
> magic-bytes + sha256 integrity header on new saves, structured event logging,
> and an optional sandboxed-subprocess loader. A data-only (JSON) save format
> that removes the pickle exec risk entirely exists in prototype behind the
> `HOV_SAVE_V2` flag (`src/save_format.py`) — see [`SECURITY.md`](SECURITY.md)
> and issue #13 for the full trust model and migration roadmap. The pickle
> format will be reduced to legacy import only.

There is no local autosave. The cloud autosave (a single `is_autosave=TRUE` row per
user, written every 3 movement/combat transitions) is the only save during active play.

## Optional AI Integration (Mynx LLM Adapter)

The in-game creature "mynx" can optionally be driven by an LLM for richer ambient
behavior. Two provider modes are supported:

1. Remote [OpenRouter](https://openrouter.ai/) API
2. Local [Ollama](https://ollama.com/) model

By default the adapter is **disabled** (`MYNX_LLM_ENABLED=0`) and the game uses
deterministic stub responses.

### Enabling the adapter

Set these in `.env` (or export them before launching):

```
MYNX_LLM_ENABLED=1                 # Enable LLM integration
MYNX_LLM_PROVIDER=ollama|openrouter
MYNX_LLM_MODEL=<model_id>          # Optional; provider-specific default if omitted
MYNX_LLM_DEBUG=1                   # Optional; print availability + fallback reasons
```

**OpenRouter (remote):**

```
MYNX_LLM_PROVIDER=openrouter
MYNX_LLM_MODEL=x-ai/grok-4-fast:free   # Default if unset
OPENROUTER_API_KEY=sk_or_...           # Required — keep secret
OPENROUTER_SITE=https://your-site.example    # Optional ranking metadata
OPENROUTER_SITE_TITLE=Your Site Name         # Optional ranking metadata
```

`available()` reports True for OpenRouter as soon as an API key is present; the
adapter does not send a network probe (keeps tests fast and avoids surprise calls).
API calls happen only when you request a mynx interaction in-game.

**Ollama (local):**

```
MYNX_LLM_PROVIDER=ollama
MYNX_LLM_MODEL=llama3.1:7b         # Example (default if unset)
MYNX_LLM_URL=http://localhost:11434
```

Pull the model first: `ollama pull llama3.1:7b`.

### Behavior modes

- **Plain text** — concise present-tense nonverbal action description.
- **Structured JSON** — an action object with keys `action, intensity, description,
  duration_seconds, audible`.

The prompt-building logic strongly constrains output and post-parses/repairs minimal
schema issues. If the provider is unavailable (no API key, server down), the game
falls back to stubbed deterministic descriptions — it never crashes.

### Quick local check

```python
import os
os.environ["MYNX_LLM_ENABLED"] = "1"
os.environ["MYNX_LLM_PROVIDER"] = "openrouter"
os.environ["OPENROUTER_API_KEY"] = "sk_or_your_key"

from ai.llm_client import MynxLLMAdapter
adapter = MynxLLMAdapter()
print(adapter.debug_status())     # 'available' plus a 'reason' when False
print(adapter.generate_plain("The mynx notices a dangling thread on the player's cloak."))
```

### Troubleshooting

If the mynx keeps returning deterministic fallbacks:

1. Set `MYNX_LLM_DEBUG=1` and interact again; watch the console.
2. Confirm `MYNX_LLM_ENABLED=1` and `MYNX_LLM_PROVIDER` are set.
3. For OpenRouter, ensure `OPENROUTER_API_KEY` is present and the `openai` package is
   installed (it's in `requirements.txt`).
4. For Ollama, ensure the daemon is running and the model is pulled.
5. Ollama timeouts: verify `MYNX_LLM_URL` (default `http://localhost:11434`).
6. Structured generations failing? The adapter enforces a strict JSON schema — check
   the model emits valid JSON with no code fences.
7. `adapter.debug_status()` reports the exact `reason` when `available` is False.

### Costs & rate limits

The `x-ai/grok-4-fast:free` tier may impose rate limits or queue delays. Keep prompts
succinct; the adapter already constrains output length and max tokens. For OpenRouter,
switching models is just a matter of setting `MYNX_LLM_MODEL` to any model ID they
expose — the rest of the adapter flow is unchanged.

## Documentation

Start at [`docs/README.md`](docs/README.md) for the full index. Key documents:

| Document | Contents |
|---|---|
| [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) | Complete REST API reference |
| [`docs/ARCHITECTURE_DIAGRAM.md`](docs/ARCHITECTURE_DIAGRAM.md) | System architecture |
| [`docs/BACKEND_API_ARCHITECTURE.md`](docs/BACKEND_API_ARCHITECTURE.md) | Backend internals |
| [`docs/FRONTEND_DOCUMENTATION.md`](docs/FRONTEND_DOCUMENTATION.md) | Frontend architecture and components |
| [`docs/LOCAL_DEV_SETUP.md`](docs/LOCAL_DEV_SETUP.md) | Detailed local setup walkthrough |
| [`frontend/README.md`](frontend/README.md) | Frontend development guide |
| [`docs/lore/`](docs/lore/) | World-building, character profiles, map designs |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history |
| [`SECURITY.md`](SECURITY.md) | Save-file trust model and hardening |

## Contributing

1. Fork or create a feature branch
2. Add tests for new behavior — CI enforces 85% backend / 95% frontend coverage
3. Keep changes focused and documented
4. Run `python -m pytest -q`, `flake8 --extend-ignore=E501 src/`, and
   `cd frontend && npm test -- --run` before pushing
5. Follow [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat(frontend):`, `fix(states):`, `refactor(backend):`)
6. Open a PR

Please flag any dependency that isn't compatible with the project's noncommercial
licenses.

## License

This project uses a dual-license approach.

### Code

Licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE-CODE).

You are free to:
- ✅ Use, modify, and distribute the code for **non-commercial purposes**
- ✅ Learn from and build upon the codebase
- ✅ Share your modifications

You may NOT:
- ❌ Use the code for commercial purposes without permission
- ❌ Hold the author liable for any issues

### Story, Lore & Creative Assets

Licensed under [CC BY-NC-ND 4.0](LICENSE-ASSETS) (Creative Commons
Attribution-NonCommercial-NoDerivatives 4.0 International).

This applies to:
- Character profiles and stories (`docs/lore/character-profiles/`)
- World-building content and lore (`docs/lore/`)
- Story content (`src/story/`)
- Art, music, and sound assets (`frontend/public/assets/`)

You are free to:
- ✅ Share and redistribute the creative content for **non-commercial purposes**
- ✅ Use the content for personal enjoyment and study

You must:
- 📌 Provide attribution to the original author

You may NOT:
- ❌ Use the content for commercial purposes
- ❌ Create derivative works or adaptations
- ❌ Remix or transform the creative content

For full license texts, see [LICENSE-CODE](LICENSE-CODE) and
[LICENSE-ASSETS](LICENSE-ASSETS).

Copyright (c) 2025 Alexander Egbert
