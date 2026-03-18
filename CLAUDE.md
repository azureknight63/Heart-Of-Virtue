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

### GameService patterns (critical gotchas)
- `GameService.__init__` is `pass` — no `self.universe`. Universe lives on `player.universe`.
- To access universe data from a service method, use the static helpers: `self._story(player)` (returns `player.universe.story` or `{}`) and `self._game_tick(player)` (returns `player.universe.game_tick` or `0`). Never reference `self.universe.*` directly.
- Routes must not reach into player internals. Use `game_service.some_method(player)` — not `getattr(player, "attribute", default)` in routes. Player attribute traps: `player.attack` is a combat action method (not a stat); `player.health` doesn't exist (it's `player.hp`); `player.stamina`, `player.defense`, `player.accuracy`, `player.evasion` are also absent. When in doubt, add a method to GameService.
- `player.reputation` doesn't exist initially. Methods that write to it initialize `player.reputation = {}` first. Read-only uses should do `getattr(player, 'reputation', {})`.

## Current Branch: `web-api`

Active work extracting the Python combat system into a stateless REST API consumed by React. Key completed work:
- `Combatant` base class introduced (eliminates Player/NPC resistance duplication)
- Blueprint URL prefixes fixed (reputation, npc, quests, quest-chains were all misrouted)
- `GameService._story(player)` / `_game_tick(player)` helpers added (universe attribute fix)
- Automated bug-hunt harness live in `tools/` with 11 scenarios

## Bug-Hunt Harness

An automated in-process harness that plays the game via Flask test client and reports bugs.

```bash
# Run all scenarios
python tools/bug_hunt.py

# Run one scenario
python tools/bug_hunt.py --scenario phase3

# Machine-readable output (for CI / Option B)
python tools/bug_hunt.py --headless --output bugs.json
```

Scenarios live in `tools/harness/scenarios/`. Each extends `Scenario` (ABC) and implements `run(client) -> List[BugReport]`. Available helpers on the base class:
- `_check_status(resp, expected, ...)` — flags wrong HTTP status
- `_check_no_crash(resp, ...)` — flags 5xx only (use for bad-input probes)
- `_check_fields(data, fields, ...)` — flags missing JSON fields
- `_bug(...)` — construct a raw BugReport

Fix-agent prompt is at `tools/harness/prompts/bug_hunt_prompt.txt`. GitHub Actions stub at `.github/workflows/bug-hunt.yml`.

## Inquisitor — Browser Mode

The Inquisitor harness drives the real React + Flask stack through a headless
Chromium browser, catching UI rendering bugs and JS errors the API layer can't see.
The harness runs a deterministic probe sequence — no Anthropic API key needed.

```bash
# Browser run (default — catches JS/rendering bugs)
python tools/inquisitor.py --headless --output tools/browser_findings.json

# Headed run (shows the browser window — useful for debugging)
python tools/inquisitor.py

# API-only (faster, no servers needed, misses UI bugs)
python tools/inquisitor.py --no-browser
```

### Prerequisites

```bash
pip install playwright asgiref          # asgiref makes async Flask routes work
python -m playwright install chromium   # downloads ~150 MB browser binary
```

**If the Playwright CDN is blocked** (CI/Docker): the harness auto-detects cached
Chromium builds in `~/.cache/ms-playwright/` and uses the highest available one
via `executable_path`. If Node.js Playwright is installed separately (e.g. for
frontend tests), its cached browser will be reused.

### How auth works (no database required)

The browser layer starts Flask with `FLASK_ENV=testing`. In test mode, the app
registers a `/api/test/session` endpoint (never active in production) that calls
`session_manager.create_session()` directly — no Turso DB needed. The login flow
tries the real registration form first; on failure it falls back to this endpoint.

### Known browser noise (filtered automatically)

These events appear in every run and are **not bugs**:
- `fonts.googleapis.com` / `fonts.gstatic.com` network failures — CDN is
  unreachable in offline environments; harmless in production.
- React Router future-flag warnings — v6→v7 migration notices, tracked upstream.

`get_page_errors` separates these into a `known_noise` key so the agent focuses
only on `console_errors` and `network_failures` (the significant ones).

### Gotchas

- `asgiref` must be installed or all `async def` Flask routes (auth, saves) will
  crash with a 500 — they silently work in-process via the test client but fail
  under a real Werkzeug server. It is listed in `requirements-api.txt`.
- The Vite dev server is slow to compile on first boot; the harness pre-warms it
  with an HTTP request before opening the browser, so navigation doesn't race.
- Screenshots land in `tools/inquisitor_screenshots/<timestamp>/` (gitignored).

## Map Design Skill

**Expert map designer for generating or auditing game maps.** The `map-design` skill creates hierarchical, lore-integrated map design documents or audits existing maps for improvements. Outputs are actionable jump-off points for implementation agents to create maps quickly and effectively.

### New Map Design

Generate a complete map design document from concept, constraints, and lore hooks:

```bash
/map-design
theme: "a sacred spring corrupted by infection"
size: "medium (40-50 tiles)"
chapter: 2
key_encounters: ["The Infestation Queen", "Geode Puzzle Chamber"]
npcs: ["Gorran", "Conclave Searchers"]
narrative_moment: "Jean discovers the extent of the corruption"
```

Or conversationally:
```bash
/map-design
Design a map for Chapter 2 where Jean enters a Golemite sacred space corrupted by slime.
```

**Output**: Markdown design document (automatically saved to `docs/lore/environments/{region}/{region}-map-design.md`) containing:
- Executive summary & design philosophy
- Hierarchical zone breakdown (3–5 zones with ASCII diagrams)
- Room-by-room specifications (coordinates, prose descriptions, exits, encounters, items, NPCs, objects)
- **Asset needs & dependencies** (what items/NPCs/enemies/objects must be created)
- Implementation notes for agents (JSON patterns, mechanics, testing gates)
- Lore integration checklist

### Map Upgrade/Audit

Analyze an existing map and recommend improvements:

```bash
/map-design --upgrade
map: "dark-grotto"
focus: "deepen lore integration and add secrets"
```

**Output**: Markdown audit report (saved to `docs/lore/environments/{region}/{map}-audit-report.md`) containing:
- Current state analysis (tile count, zone structure, NPC/item inventory)
- Six-dimension audit: thematic coherence, environmental storytelling, NPC balance, puzzle quality, pacing, lore depth
- Categorized improvement suggestions (High Priority / Medium / Nice-to-Have)
- Specific placements and effort estimates
- Before/after ASCII comparisons (where helpful)

### Design Principles

The skill follows these principles:
- **Lore first, mechanics second**: Every tile has a reason rooted in the world
- **Sensory prose**: Descriptions invoke touch, sound, smell, not just sight
- **Environmental storytelling**: Objects, items, NPCs tell history
- **Progressive complexity**: Early zones tight and readable; later zones layer mechanics
- **Secrets reward curiosity**: At least one genuinely discoverable secret
- **Narrative beats embedded**: Story moments anchor to tiles, not separate cutscenes

### Output Behavior

By default, the skill **saves output as a markdown file** in the appropriate lore directory:
- New maps → `docs/lore/environments/{region}/{region}-map-design.md`
- Map audits → `docs/lore/environments/{region}/{map-name}-audit-report.md`

If you need the output in the conversation instead of as a file, explicitly request it: `"just show me the design"` or `"display the audit report in chat"`.

### Example Output

See [docs/lore/environments/wailing-badlands/wailing-badlands-map-design.md](docs/lore/environments/wailing-badlands/wailing-badlands-map-design.md) for a complete map design document (87 tiles, 5 zones, Anger stage of Jean's grief arc).

---

## Code Review Gate

**Always use the `code_reviewer` skill** whenever code changes are made. After any task that introduces code changes, invoke the skill to perform an automated review, then manually verify critical dimensions if needed.

The code_reviewer skill automatically analyzes code changes and grades them. For non-trivial changes, the agent should review the feedback and correct any issues until all dimensions reach A or above.

### Confidence filter
Before grading, score each potential issue 0–100. Only count issues with confidence ≥ 80 toward a grade — don't let unverified nitpicks drag a dimension down.

- **0–24**: False positive or pre-existing. Ignore.
- **25–49**: Possible issue but unverified. Flag for awareness only; does not affect grade.
- **50–74**: Real but minor. Mention; does not fail a dimension alone.
- **75–100**: Verified, impactful, or explicitly required by this file. Counts toward grade.

### Dimensions

| Dimension | What to check |
|---|---|
| **Correctness** | Does the change solve the stated problem? Logic errors, null/undefined handling, race conditions, memory leaks, edge cases, regressions |
| **Architecture** | Follows rules in this file — engine/API separation, no duplication of Combatant logic, adapter pattern respected, GameService/SessionManager boundaries |
| **Convention** | Naming, error handling style, docstrings on public methods, no stray `###DEBUG###`, import grouping, logging patterns, platform compatibility |
| **Code Quality** | DRY — no repeated logic that belongs in a shared location; clean, purposeful code; missing critical error handling; adequate test coverage for changed behavior |
| **Simplicity** | Minimum complexity for the task; no premature abstraction, no speculative features, no backwards-compat shims for unused code |
| **Security** | No new vulnerabilities; inputs validated at system boundaries; no secrets in code; SQL/XSS/injection safe |
| **Maintainability** | Readable at a glance; low cognitive load; names convey intent; changes are localized and don't create hidden coupling; future modifications are not made harder |
| **Stability** | Graceful error recovery in hot paths; no unhandled exceptions that crash the game loop; silent failures logged; degraded-mode behavior is acceptable |
| **AI-friendliness** | Structure is navigable without global context; naming makes intent clear without requiring comments to decode; logic is locally coherent rather than scattered across distant files |
| **Performance** | No unnecessary computation in hot paths (especially combat loop); efficient data structures; no repeated work that could be cached; no obvious memory leaks |

### Rules
- Report issues grouped by severity: **Critical** (must fix) then **Important** (should fix).
- Do not suggest `/commit` until all dimensions are at A.
- If a dimension can't reach A without a decision from the user, stop and ask — don't invent a resolution.
- For trivial changes (config edits, comment fixes), briefly confirm all dimensions are N/A or A and move on without a full table.

## Session Workflow

At the end of every task, suggest the appropriate overhead steps before moving on. The goal is to ship and maintain a complete game — treat housekeeping as part of the work, not an afterthought.

Standard closing checklist (use judgment on which apply):
- **`code_reviewer` skill** — use the skill to review all code changes (mandatory for any non-trivial changes)
- **`/commit`** — if there are uncommitted changes worth preserving
- **`/revise-claude-md`** — if the session revealed something about the project that isn't in CLAUDE.md (new patterns, gotchas, decisions made)
- **Tests** — remind to run `pytest -q` or `cd frontend && npm test` if the changes touch testable code
- **Pending improvements** — flag any items from `~/.claude/projects/.../pending-improvements.md` that became newly relevant

Don't suggest all of these robotically after every small change. Use judgment: a two-line fix doesn't need a full debrief. A significant architectural change does.

## QA — Known Intentional Behaviors

When running `/qa` or any exploratory testing, check this section before filing bugs
related to blocked movement, missing exits, unresponsive objects, or apparent dead ends.
This is an RPG — many things that look broken are puzzles.

### Explorer heuristic (apply before filing any game-interaction bug)

1. **Read first.** Tile descriptions, object descriptions, NPC dialogue, and environmental
   text are the game's UI. An object that "does nothing" on click may have description text
   hinting at how to use it.
2. **Interact before concluding an exit is missing.** If a tile has no exit in some direction
   but contains interactive objects (depressions, levers, inscriptions, switches), attempt
   interaction before filing a missing-exit bug.
3. **Track leads.** "Dead end with an interactive object" is a lead, not a confirmed bug.
   Note it, try interacting, revisit if new context (a key, clue, or NPC hint) emerges.
4. **Flag ambiguity correctly.** If still uncertain, file as "possible intentional mechanic —
   needs verification" rather than a confirmed bug. Ask the user before closing it out.

### Confirmed intentional mechanics

| Location | Apparent issue | Actual behavior |
|---|---|---|
| Wall Depression (Dark Grotto) | No eastward exit | Interacting triggers "Jean hears a faint 'click.'" and unlocks the eastern passage — hidden passage mechanic |

### General patterns (apply to all maps)

- **Dead ends with nearby interactables** — try the object before concluding it's a dead end
- **Locked doors** — may require a key item, quest state, or NPC interaction to open
- **Empty rooms** — some are intentionally sparse; absence of content is only a bug if the room also lacks a description
- **One-way passages** — some exits are directional by design
- **Gated content** — areas/items/NPCs may only appear after story progress; early absence is not a bug

## Licenses

- Code: PolyForm Noncommercial
- Story/assets: CC BY-NC-ND 4.0

Do not suggest or add open-source-incompatible dependencies without flagging it.
