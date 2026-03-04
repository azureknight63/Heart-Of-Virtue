# Heart of Virtue — CLAUDE.md

## Project Overview

Text-based Adventure RPG (ASCII/retro aesthetic) following a crusader named Jean Claire. The project has two modes of play:
- **Terminal/CLI**: Original Python implementation
- **Web**: Flask REST API + React SPA (current focus on `web-api` branch)

The Python game engine is the source of truth. The web layer wraps it without rewriting it.

## Tech Stack

| Layer | Technology |
|---|---|
| Game engine | Python (Flask 3.1.2, Flask-CORS, Flask-SocketIO) |
| Frontend | React 18, Vite, Tailwind CSS, Axios, Socket.IO client |
| Database | LibSQL (Turso) via `libsql-client` |
| Testing (backend) | pytest, pytest-cov |
| Testing (frontend) | Vitest, React Testing Library |
| Code quality | black (formatter), flake8 (linter) |
| AI integration | OpenAI/OpenRouter for Mynx NPC ambient behavior |

## Project Structure

```
src/
├── api/                    # Flask API layer (web-api branch focus)
│   ├── app.py              # Flask factory (create_app)
│   ├── combat_adapter.py   # Wraps terminal combat → JSON
│   ├── routes/             # REST endpoints (auth, combat, world, inventory, ...)
│   ├── services/           # Business logic (game_service, session_manager, ...)
│   ├── serializers/        # Entity → JSON serialization
│   ├── handlers/           # Error/event handlers
│   ├── middleware/         # Auth middleware
│   └── schemas/            # OpenAPI definitions
├── combat.py               # Core turn-based combat engine
├── combatant.py            # Base class for Player + NPC (shared resistance/state logic)
├── moves.py                # Combat abilities/moves (large file, ~152KB)
├── states.py               # Status effects (buffs/debuffs)
├── player.py               # Player class (~90KB), inherits Combatant
├── npc.py                  # NPC class (~92KB), inherits Combatant
├── items.py                # Item definitions (~98KB)
├── game.py                 # Main game loop (CLI)
├── universe.py             # World/map system
└── interface.py            # Terminal UI/display

frontend/src/
├── pages/                  # LoginPage, MainMenuPage, GamePage
├── components/             # Battlefield, WorldMap, CombatLog, PlayerStatus, ...
├── hooks/                  # useApi, useCombat, useFetchCombatStatus, ...
├── api/                    # Axios client + endpoint definitions
└── context/                # AudioContext
```

## Running the Project

```bash
# Terminal game
python src/game.py

# API server (localhost:5000)
python tools/run_api.py

# Frontend dev server (localhost:3000)
cd frontend && npm install && npm run dev
```

## Running Tests

```bash
# Backend (fast — excludes tests/api, tests/broken, tests/uat per pytest.ini)
pytest -q

# Backend with coverage
pytest --cov=src --cov=ai --cov-report=term-missing

# Frontend
cd frontend && npm test
```

The `tests/api/`, `tests/broken/`, and `tests/uat/` directories are excluded from the default run. Don't add them to standard test runs.

## Coding Conventions

### Python
- snake_case for functions/variables, PascalCase for classes
- Docstrings on public methods (existing style — don't strip them)
- Conventional Commits format: `refactor(backend):`, `feat(frontend):`, `fix(states):`, etc.
- Debug statements marked `###DEBUG###` — don't leave new ones in
- Error handling: try/except with logging; prefer silent recovery over crashing the game loop
- Do not add type annotations to files that don't already use them heavily

### JavaScript/React
- camelCase variables/functions, PascalCase components
- Custom hooks for stateful logic (don't inline API calls in components)
- Tailwind CSS utility classes inline; retro terminal palette: lime `#00FF00`, cyan `#00FFFF`, orange `#FF8800` on `#0a0a0a`
- Functional components only

### Architecture rules
- Game logic lives in the Python engine. The API layer adapts; it does not reimplement.
- `CombatAdapter` is the bridge between terminal output and JSON — changes to combat serialization go there
- `Combatant` base class owns shared resistance/status-effect logic for Player and NPC. Do not duplicate this in subclasses.
- `GameService` + `SessionManager` abstract the game loop for stateless API calls

## Current Branch: `web-api`

Active work extracting the Python combat system into a stateless REST API consumed by React. Key recent changes:
- `Combatant` base class introduced (eliminates Player/NPC resistance duplication)
- `Move.get_effective_range_max()` for dynamic ranged weapon range calculation
- `fetchCombatStatus` hook refactored to return transformed combat data

Uncommitted changes currently in: `combat_adapter.py`, `moves.py`, `states.py`.

## Session Workflow

At the end of every task, suggest the appropriate overhead steps before moving on. The goal is to ship and maintain a complete game — treat housekeeping as part of the work, not an afterthought.

Standard closing checklist (use judgment on which apply):
- **`/commit`** — if there are uncommitted changes worth preserving
- **`/revise-claude-md`** — if the session revealed something about the project that isn't in CLAUDE.md (new patterns, gotchas, decisions made)
- **Tests** — remind to run `pytest -q` or `cd frontend && npm test` if the changes touch testable code
- **Pending improvements** — flag any items from `~/.claude/projects/.../pending-improvements.md` that became newly relevant

Don't suggest all of these robotically after every small change. Use judgment: a two-line fix doesn't need a full debrief. A significant architectural change does.

## Licenses

- Code: PolyForm Noncommercial
- Story/assets: CC BY-NC-ND 4.0

Do not suggest or add open-source-incompatible dependencies without flagging it.
