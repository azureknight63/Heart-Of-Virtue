# Heart of Virtue — CLAUDE.md

## Project Overview

Text-based Adventure RPG (ASCII/retro aesthetic) following a crusader named Jean Claire. The game is played **entirely via the web app** — a Flask REST API wrapping the Python game engine, with a React SPA frontend. (The original terminal/CLI play mode has been removed; see "Terminal-mode removal" below.)

The Python game engine is the source of truth. The web layer wraps it without rewriting it. Engine output flows through the **narration sink** (`src/narration.py`) as structured messages rather than terminal `print`; the API reads those messages directly instead of scraping stdout.

## Tech Stack

| Layer | Technology |
|---|---|
| Game engine | Python (Flask 3.1.2, Flask-CORS, Flask-SocketIO) |
| Frontend | React 18, Vite, Tailwind CSS, Axios, Socket.IO client |
| Database | LibSQL (Turso) via `libsql-client` |
| Testing (backend) | pytest, pytest-cov |
| Testing (frontend) | Vitest, React Testing Library |
| Code quality | flake8 (linter) |
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
├── moves/                  # Combat abilities/moves — package (was moves.py, ~252KB)
│   ├── __init__.py         # Re-exports all 73+ classes; callers use `import moves` unchanged
│   ├── _base.py            # Move, PassiveMove base classes; _ensure_weapon_exp, default_animations
│   ├── _utility.py         # StrategicInsight, Check, Wait, Rest, UseItem, Attack
│   ├── _movement.py        # Dodge, Parry, Advance, Withdraw, BullCharge, TacticalRetreat, …
│   ├── _unarmed.py         # PowerStrike, Jab; passives: IronFist, CleaveInstinct, HeavyHanded
│   ├── _dagger.py          # Slash, Backstab, FeintAndPivot; passive: ShadowStep
│   ├── _sword.py           # PommelStrike, Thrust, DisarmingSlash, Riposte, …
│   ├── _scythe.py          # Reap, ReapersMark, DeathsHarvest; passives: GrimPersistence, …
│   ├── _spear.py           # KeepAway, Lunge, Impale, ArmorPierce; passive: SentinelsVigil
│   ├── _pick.py            # ChipAway, ExploitWeakness, Stupefy, WorkTheGap
│   ├── _ranged.py          # ShootBow, ShootCrossbow, AimedShot, …; passives: EagleEye, …
│   ├── _polearm.py         # OverheadSmash, Sweep, BracePosition, HalberdSpin; passive: ReachMastery
│   └── _npc.py             # NpcAttack, NpcRest, TelegraphedSurge, SlimeVolley, TidalSurge, …
├── states.py               # Status effects (buffs/debuffs)
├── player.py               # Player class (~90KB), inherits Combatant
├── npc.py                  # NPC class (~49KB), inherits Combatant
├── items.py                # Item definitions (~98KB)
├── game.py                 # Main game loop (CLI)
├── universe.py             # World/map system
└── interface.py            # Terminal UI/display

frontend/src/
├── pages/                  # LoginPage, MainMenuPage, GamePage
├── components/             # Battlefield, WorldMap, CombatLog, PlayerStatus, MobileTabBar, CollapsibleRoomDescription, ...
├── hooks/                  # useApi, useCombat, useFetchCombatStatus, useMobile, ...
├── api/                    # Axios client + endpoint definitions
└── context/                # AudioContext
```

Root:
```
config_combat_testing.ini   # Combat testing config (agent-only; pass CONFIG_FILE= to activate)
```

## Running the Project

```bash
# API server (localhost:5000) — the game runs entirely through this
python tools/run_api.py

# Frontend dev server (localhost:3000)
cd frontend && npm install && npm run dev
```

## Running Tests

```bash
# Backend (fast — excludes tests/api, tests/broken, tests/uat per pytest.ini)
python -m pytest -q

# Backend with coverage
python -m pytest --cov=src --cov=ai --cov-report=term-missing

# Backend with HTML coverage report
python -m pytest --cov=src --cov=ai --cov-report=html
# Then open htmlcov/index.html

# Frontend
cd frontend && npm test

# Frontend with coverage
cd frontend && npm test -- --run --coverage
# View at frontend/coverage/index.html
```

Use `python -m pytest` rather than bare `pytest` — the virtualenv may not expose the
`pytest` binary on PATH, causing silent import failures.

The `tests/api/`, `tests/broken/`, and `tests/uat/` directories are excluded from the default run. Don't add them to standard test runs. **Full-app integration tests that build a real session/universe** (via `create_app(TestingConfig)` + `/api/test/session`) belong in `tests/api/` — creating a real session mutates module-level item/merchant registries and pollutes downstream shop/spawn tests in the default suite. The other route tests avoid this by using a *mocked* `session_manager`.

**Test-pollution gotcha:** stray root-level scripts (`test_*_fix.py`, `reproduce_*.py`, etc.) that do `sys.modules['flask'] = MagicMock()` at import will poison every Flask test in a full run — pytest collects them from the rootdir, so each later route/serializer test sees a `MagicMock` app and fails (while passing in isolation). `pytest.ini`'s `addopts` ignore-list neutralizes the known ones; add new such scripts there. To find a collection-time culprit, hook `pytest_collection_finish` and check `type(sys.modules['flask'])`.

## Test Coverage Strategy

### Coverage Targets

| Layer | Current | Target | CI Minimum |
|-------|---------|--------|-----------|
| Backend (Python) | 47% | 85% | 85% |
| Frontend (React) | ~75% | 95% | 95% |
| Total Tests | 1,308 | 1,500+ | - |

### Backend Coverage Enforcement

**CI/CD Rule**: Every PR and push to `master`, `develop`, or `web-api` must pass coverage checks:
- Minimum 85% coverage (via `--cov-fail-under=85`)
- All tests must pass
- Coverage must not decrease from the previous commit

Run locally before pushing:
```bash
python -m pytest \
  --cov=src \
  --cov=ai \
  --cov-report=term-missing \
  --cov-fail-under=85 \
  -q
```

**High-coverage areas** (>70%):
- `src/api/routes/` — REST endpoints well-tested
- `src/api/services/` — Core game logic
- `src/universe.py` — World/map system

**Low-coverage areas** (<50%):
- `src/story/` — Narrative intentionally sparse (hard to test story paths)
- `ai/` — LLM integration, fallback behavior
- `src/states.py` — Status effects (needs 20+ new tests)
- `src/npc.py` — NPC AI behavior (needs edge case tests)

### Frontend Coverage Enforcement

**CI/CD Rule**: Frontend tests must pass with 95%+ coverage:
- Run via `npm test -- --run --coverage` in CI
- Enforced via `coverage.thresholds` (95% lines/statements/functions/branches) in `frontend/vite.config.js` — the build fails below this

High-coverage components (>80%):
- `pages/` — Login, menu, game pages
- `hooks/useApi` — API integration

Low-coverage components (<75%):
- `NpcChatPanel.jsx` — Complex async state (target: 80%)
- `MobileTabBar.jsx` — Touch interactions (target: 85%)

### Pre-Commit Hook (Local)

A pre-commit hook (`.git/hooks/pre-commit`) runs quick tests before each commit:
- Runs `python -m pytest -q` (~2-3 seconds)
- Fails commit if tests fail
- Bypass with `git commit --no-verify` (use sparingly)

The hook is installed automatically the first time you clone. If missing, manually set up:
```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
set -e
echo "🧪 Running pre-commit tests..."
python -m pytest -q --tb=line || exit 1
echo "✅ Tests passed!"
EOF
chmod +x .git/hooks/pre-commit
```

### Coverage Dashboard

See `docs/coverage/coverage-dashboard.md` for:
- Detailed coverage by module
- Monthly trend tracking
- Improvement plan with effort estimates
- Badge and reporting setup

### Why These Numbers?

- **85% backend minimum**: High confidence in core logic (combat, inventory, movement); catches regressions early
- **95%+ frontend**: User-facing code must be reliable
- **Story intentionally low**: Narrative branches are hard to test; we focus on mechanics

## Coding Conventions

### Python
- snake_case for functions/variables, PascalCase for classes
- Docstrings on public methods (existing style — don't strip them)
- Conventional Commits format: `refactor(backend):`, `feat(frontend):`, `fix(states):`, etc.
- Debug statements marked `###DEBUG###` — don't leave new ones in
- Error handling: try/except with logging; prefer silent recovery over crashing the game loop
- Do not add type annotations to files that don't already use them heavily
- **All local imports use the canonical `src.` path** (`from src.items import Item`, `import src.functions as functions`) — including dynamic ones (`importlib.import_module("src.tiles")`) and `patch()` target strings. Never import an engine module by bare name: bare imports create a *duplicate module object* (separate classes, separate module-level state) whenever `src/` lands on `sys.path`, silently breaking `isinstance` checks and registries across the API/engine boundary. Enforced by `tests/test_no_bare_local_imports.py` (static AST scan) and `tests/test_import_sync_production.py` (production-entry subprocess). Persisted data is the one exception: map JSON `__module__` fields and legacy pickles store bare names by contract — resolve them through `functions.canonical_module_name()` (used by `Universe._deserialize_saved_instance` and `SafeUnpickler`).
- When a test needs to stub an engine module that code imports via `import src.x as m`, patching `sys.modules["src.x"]` is not enough — that import form binds through `getattr(src, "x")`, so patch the `src` package attribute too (see `_fake_engine_modules` in `tests/test_session_manager_coverage.py`). To make a mock pass an engine `isinstance` check, assign the real class to `mock.__class__` or build the instance with `RealClass.__new__(RealClass)`.

### JavaScript/React
- camelCase variables/functions, PascalCase components
- Custom hooks for stateful logic (don't inline API calls in components)
- Tailwind CSS utility classes inline; retro terminal palette: lime `#00FF00`, cyan `#00FFFF`, orange `#FF8800` on `#0a0a0a`
- Functional components only

### Architecture rules
- Game logic lives in the Python engine. The API layer adapts; it does not reimplement.
- `CombatAdapter` is the bridge between terminal output and JSON — changes to combat serialization go there
- `Combatant` base class owns shared resistance/status-effect logic for Player and NPC. Do not duplicate this in subclasses.
- New passive moves (flag-only, never castable, `viable()→False`) must inherit `PassiveMove` from `src/moves/_base.py`, not `Move` directly. Subclasses only supply `name` and `description`.
- **Combat animations**: every castable move declares a `web_animation` class attribute (e.g. `web_animation = "pierce"`). Valid types are the keys of `ANIMATION_CONFIGS` in `frontend/src/utils/animationConfigs.js` (attack, quick_attack, heavy_attack, pierce, sweep, charge, projectile, shockwave, dash, defend, buff, debuff, drain, heal, pulse, death) — contract-tested by `tests/test_move_web_animations.py`. When adding a move, pick an existing type; when adding a type, define its config (phases/motion/effect/sfx) in the frontend first. Unknown types fall back to `pulse` client-side; a missing declaration falls back to attack/pulse in the adapter.
- `GameService` + `SessionManager` abstract the game loop for stateless API calls

### GameService patterns (critical gotchas)
- `GameService.__init__` is `pass` — no `self.universe`. Universe lives on `player.universe`.
- To access universe data from a service method, use the static helpers: `self._story(player)` (returns `player.universe.story` or `{}`) and `self._game_tick(player)` (returns `player.universe.game_tick` or `0`). Never reference `self.universe.*` directly.
- Routes must not reach into player internals. Use `game_service.some_method(player)` — not `getattr(player, "attribute", default)` in routes. Player attribute traps: `player.attack` is a combat action method (not a stat); `player.health` doesn't exist (it's `player.hp`); `player.stamina`, `player.defense`, `player.accuracy`, `player.evasion` are also absent. When in doubt, add a method to GameService.
- `player.reputation` doesn't exist initially. Methods that write to it initialize `player.reputation = {}` first. Read-only uses should do `getattr(player, 'reputation', {})`.
- **Cooldown timing trap**: cooldowns must only drain during active combat beats. Any code path that calls cooldown drain outside the combat loop (e.g., during rest, world movement, or save/load) will silently corrupt move availability. Guard all drain calls with an active-combat check.

### Frontend patterns (critical gotchas)
- **`ConversationStage` reset trap**: `ConversationStage.jsx` renders staged (portrait) dialogue and tracks its position with `beatIndex` (`useState`) and a `completedRef` (`useRef`) that gates `onComplete` to fire exactly once. `EventDialog.jsx` mounts it with no `key` prop, so React reuses the same instance across re-renders instead of remounting it when `segments`/`conversation` change. This was harmless as long as every event handed it exactly one `segments` array for its whole life — but any event that calls `begin_conversation()` more than once across separate stages (multiple `process_event_input` round-trips within a single event, e.g. `Ch02GuideToCitadel`, `AfterKingSlimeReturn`) hands the *same mounted instance* a fresh `segments` array per stage. Without a reset, the next stage resumes at the previous stage's stale `beatIndex` (skipping or blanking beats) and `completedRef.current` is already `true`, so `onComplete` never fires again — soft-locking the player with no way to advance. `ConversationStage.jsx` now has a `useEffect` keyed on `segments` that resets both `beatIndex` and `completedRef.current` on every new stage (each API response builds a fresh array, so reference-equality naturally fires this once per stage). Any new component that holds per-conversation/per-stage state across a `segments`/`conversation` prop change needs the same reset-on-prop-change guard.

## Completed Milestones

Key architectural work already merged into the codebase:
- `Combatant` base class introduced (eliminates Player/NPC resistance duplication)
- Blueprint URL prefixes fixed (reputation, npc, quests, quest-chains were all misrouted)
- `GameService._story(player)` / `_game_tick(player)` helpers added (universe attribute fix)
- Automated bug-hunt harness live in `tools/` with 11 scenarios
- Combat testing arena added (`src/resources/maps/combat-testing-arena.json`) with `/combat-test` skill
- Cooldown drain bug fixed: cooldowns now only tick during active combat beats, not during resting/non-combat states
- Beta QA pass complete (v0.0.4.0): 5 combat API bugs fixed (`awaiting_input` stale after victory/defeat, proximity gap on reinforcement spawn, `current_stage` deadlock on mid-beat event, `pending_move_index` stale on wave transition)
- `NPCSpawnerEvent.evaluate_for_map_entry` tile fallback added — uses `self.tile` when `spawn_tile` is `None` (JSON deserialization issue), fixing Lurker and map-entry spawners via the API
- `GameService.move_player` calls `player.universe.game_tick_events()` on every move — required for map-entry spawners (NPCSpawnerEvents) to fire; mirrors the terminal game loop
- `src/moves.py` split into `src/moves/` package (13 submodules, 73 classes) — `PassiveMove` base class added to eliminate ~200 lines of repeated passive-move boilerplate; all callers unchanged via `__init__.py` re-exports
- Terminal-mode teardown (Phase 2): all four `interface.py` menu classes removed, dead `combat()` loop deleted, `TheAdjutant` menu converted to the `/api/debug` blueprint, event capture moved fully onto the narration sink + structured protocol (see "Terminal-mode removal" below for details and what remains)
- Portrait-dialog rollout (Phase 2, ch02.py): staged `say()`/`narrate()`/`begin_conversation()` conversion extended to `ch02.py`'s `self.description`-driven events (Votha Krr introduction/farewell, King Slime memory flash, `AfterDefeatingKingSlime`). Uncovered and fixed the `ConversationStage` reset trap above, a Gorran/Votha-Krr name-reveal spoiler (canonical speaker id leaking onto the portrait before the in-fiction naming beat), a missing fade `span` on a stage-exit op, and a dropped narration sentence from a `narrate()` split.
- Save-deserialization hardening (issue #13, all phases): `SafeUnpickler` + legacy-module resolution extracted into `src/secure_pickle.py`. It adds an auto-derived engine **class allow-list**, opt-in **strict mode** (`HOV_STRICT_UNPICKLE` env var) that rejects off-list classes and disables placeholder synthesis, a `HOVS` magic+version+**sha256 integrity header** on new saves (`serialize_for_save()`; loader validates and still reads legacy headerless saves), a 5 MB **size cap**, tagged legacy placeholders (`_legacy_placeholder=True`) with per-class fresh mutable containers, structured **event logging** + process **telemetry**, and an optional **sandboxed-subprocess** loader (`load_in_subprocess` → `src/_unpickle_worker.py`). `functions.py` re-exports the moved names for backward compat and routes `_safe_pickle_load`/`save` through it; `game_service.save_game` writes headered saves. Phase 3 data-only JSON prototype (`src/save_format.py`, behind `HOV_SAVE_V2`): `player_to_data`/schema validation/version negotiation/one-shot sidecar conversion, capturing a documented player+world **subset** (not yet the full world graph — pickle stays source of truth). Allow-list drift guarded by `tools/gen_allowlist_manifest.py` + `docs/development/save-allowlist-manifest.json`. Strict-mode enforcement is **engine-module-based** (any global from an `src.<engine module>` is trusted — classes *and* functions/methods — plus a curated `_SAFE_STDLIB` set; `os`/`subprocess`/`builtins.eval`/`getattr` are blocked). A save fuzzer (`tools/save_fuzzer.py` + `tests/test_save_fuzz.py`) populates saves with random real classes/values and adversarial payloads (disallowed globals, malicious `__reduce__`, tampered headers, oversize, garbage) and asserts zero **security** invariant breaches while treating benign strict-mode rejections as informational **coverage gaps**. It surfaced (and drove fixes for) the engine-method/`_SAFE_STDLIB` gaps, a malformed-module-path crash (`find_class` now catches `ImportError/AttributeError/ValueError/TypeError`), and an allocation-DoS (sandbox now sets `RLIMIT_AS`). See `SECURITY.md`. **Any new top-level `src/` module must be added to `LEGACY_BARE_MODULES` in `src/secure_pickle.py`** (enforced by `tests/test_no_bare_local_imports.py`).

### Terminal-mode removal (mostly complete)

The game is web-API-only; the terminal play mode is being dismantled in phases:
- **Done:** CLI entry points deleted (`game.py`, `intro_scene.py`, `open_terminal.py`); inventory helpers extracted to `src/inventory_utils.py`; **narration sink** added (`src/narration.py`) — engine emits structured `{text, color, type}` messages via `cprint`/`narrate` into a context-local buffer (`capture_narration()`), echoing to stdout only when no capture is active (keeps `capsys` tests working). ~470 `print()` calls and ~35 modules repointed off `neotermcolor`. The combat adapter consumes the narration buffer via a live listener instead of scraping stdout (`_capture_output`).
- **Done:** all four terminal menu classes deleted from `interface.py` — `ContainerLootInterface` (loot verbs route through `events.LootEvent`), `ShopInterface` (+`ShopBuyMenu`/`ShopSellMenu`; pricing moved onto the `Merchant` — `buy_modifier`/`sell_modifier`/`shop_name` — read by `GameService.shop_buy/sell` + `ShopSerializer`), `RoomTakeInterface` (web uses `Item.take()` + `interact_with_target`), and `InventoryInterface`/`InventoryCategorySubmenu`/`BaseInterface` (web uses the `/inventory` routes). `interface.py` is now a thin shim re-exporting `get_gold`/`transfer_gold`/`transfer_item`. The dead `Player.take`/`Player.print_inventory`/`Player.attack` verbs and their `actions.py` action classes (`ViewInventory`/`Take`/`Attack`) were removed too.
- **Done:** dead terminal `combat()` loop deleted (`src/combat.py` removed; the web client drives combat through `ApiCombatAdapter`). `CombatEvent`'s terminal fallback removed (always `combat_start` in web).
- **Done:** `TheAdjutant` debug menu converted to a **test-only debug endpoint** (`src/api/routes/debug.py`, `debug_bp`, registered only when `app.config["TESTING"]`). The Adjutant's input() menu was replaced by parametrized operation methods (`set_hp`, `set_level`, `set_attributes`, `set_heat`, `restore`, `learn_all_skills`, `list_skills`, `player_state`, `arena_rosters`, `add_combatant`, `remove_combatant`, `clear_room`, `set_combatant_stats`).
- **Done:** event output capture fully on `capture_narration` (last `redirect_stdout` in `move_player` converted); `WhisperingStatue` — the only event that called `input()` directly — converted to the structured protocol.
- **Done:** de-terminal'd every `input()` in the event/interact-reachable engine modules (`functions.py`, `player/*`, `items.py`) — `Item.drop/take` default to the full stack, `Book.read` is non-interactive, `equip_item`/`use_item` take the first phrase match, `gain_exp` always uses `_level_up_api`; deleted the dead terminal helpers (`confirm`, `load_select`, `save_select`, `enumerate_for_interactions`, `equip_item_menu`, `skillmenu`, `level_up`) and the `SkillMenu` action. **The input-mocking net is removed**: `GameService._build_event_patches` no longer patches `input()` (only `await_input`/`animate`/`time.sleep`), and `_make_mock_input`/`_MOCK_INPUT_CYCLE` are gone.
- **Done:** removed the terminal `input()` from combat moves (`moves/*`). The adapter drives moves via `cast()`/`advance()` and supplies selections through structured commands (`select_number`/`select_direction`/`select_target`) that set attributes (`duration`/`distance`/`target_direction`/`target`) on the move *before* its stage runs; each move now reads that attribute (defaulting sensibly) instead of prompting. `Turn`'s terminal `_prompt_direction_selection`/`_calculate_direction_to_target` were deleted; `ShootBow` defaults to the preferred/first arrow; `UseItem`'s in-combat item use is the `/inventory/use` route. **`src/` is now free of engine `input()`** — only the `animations.py` `__main__` CLI guard remains.
- **Done:** removed the dead directional-movement/exploration terminal path — `Player.move`/`move_north`/`move_south`/`move_east`/`move_west`/`move_northeast`/`move_northwest`/`move_southeast`/`move_southwest`, `Player.look`/`view`, `Player.flee`, `Player.commands`, `functions.advise_player_actions`, the corresponding `Action` subclasses (`MoveNorth`…`MoveSouthwest`, `Look`, `View`) in `actions.py`, and `tiles.py`'s `adjacent_moves()` plus its `callerIsApi=False` branch in `available_actions()` (which always returns the API-mode action set now).
- **Remaining:** `Player.menu` lingers (still reachable outside the deleted paths) but is not API-invoked and no longer calls `input()`.

**Narration gotcha:** `narrate(*parts, color=None, ...)` joins parts like `print`; color must be passed as a keyword (`narrate(text, color="red")`), never positionally. `cprint(text, color)` keeps the old signature.

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

**There is no guest mode.** Production requires registration; every real player session
has a `db_user_id`. The "no db_user_id" path in the saves routes (which 403s cloud save
operations) is only reachable via the test session bypass — i.e. QA/Inquisitor runs.

**Local autosave (`hov_local_autosave` in localStorage)** is written on every player
state change during active play. It exists as a crash-recovery safety net for the current
session, not as a standalone save format. In production it is always superseded by the
cloud autosave (written every 20 ticks). The only scenario where it is the *only* save
is during QA runs that use the test session bypass.

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

## Combat Testing Skill

**Agent-focused combat scenario testing.** The `/combat-test` skill reads `config_combat_testing.ini`, applies any inline overrides, and runs the scenario. **Primary path: `python tools/bug_hunt.py`** (fast, in-process, no browser needed — use for logic/mechanics verification). Full browser `/qa` is the escalation path for UI-layer concerns only.

```bash
/combat-test                                      # run default scenario (fodder)
/combat-test scenario=boss                        # high-HP boss pressure test
/combat-test scenario=status_dummy hp=50          # status effect verification
/combat-test god_mode=True scenario=ally          # ally AI test, Jean cannot die
```

### Config file

`config_combat_testing.ini` (project root) is the single control surface. Edit it directly or pass inline overrides. **The game must be started with `CONFIG_FILE=config_combat_testing.ini`** for `startmap`, `testmode`, and `startposition` to take effect — otherwise the game boots on the default map and the arena is unreachable (it has no link to the main game world).

### Arena map

`src/resources/maps/combat-testing-arena.json` — a self-contained 2×2 grid of test tiles:

| Tile | Name | Combatants | Purpose |
|------|------|-----------|---------|
| `(0, 0)` | Proving Grounds | The Adjutant (ally) | Staging area — stat and roster configuration |
| `(1, 0)` | Fodder Pit | Slime + CaveBat | Basic move/damage testing |
| `(2, 0)` | The Crucible | KingSlime + Lurker | Boss-tier HP, complex move sets |
| `(0, 1)` | Ally Courtyard | Gorran (ally) + Slime | Ally AI, co-op mechanics, friend=True |
| `(1, 1)` | Status Chamber | Pell (StatusDummy) | Status effects — all resistances stripped to 0 |

### Key NPCs added in `npc.py`

- **`TheAdjutant`** — friendly NPC at `(0, 0)`. `talk` narrates flavor only; runtime configuration (Jean's HP/level/attributes/heat/skills and the per-tile NPC roster) is driven by the **test-only debug endpoint** (`/api/debug/*`, `src/api/routes/debug.py`), which calls the Adjutant's parametrized operation methods. The endpoint is registered only when `app.config["TESTING"]` is true, so it is never reachable in production. Changes take effect immediately — no restart needed.
- **`StatusDummy` / "Pell"** — test target at `(1, 1)`. Every status resistance is 0.0 and every damage resistance is 1.0 so effects land reliably. High HP (500), very low damage (3).

---

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
- **Descriptions are permanent**: Tile descriptions persist after NPCs are killed and items are picked up. Never write present-tense NPC behaviour ("The bats are aware of Jean", "Gorran places his hand on the crystal", "The Rumblers move through the water") or item references ("The supplies left here") into a description. Instead, describe durable environmental evidence — staining, claw marks, smells, worn stone, old fire rings — that remains true regardless of entity state.

### Output Behavior

By default, the skill **saves output as a markdown file** in the appropriate lore directory:
- New maps → `docs/lore/environments/{region}/{region}-map-design.md`
- Map audits → `docs/lore/environments/{region}/{map-name}-audit-report.md`

If you need the output in the conversation instead of as a file, explicitly request it: `"just show me the design"` or `"display the audit report in chat"`.

### Example Output

See [docs/lore/environments/wailing-badlands/wailing-badlands-map-design.md](docs/lore/environments/wailing-badlands/wailing-badlands-map-design.md) for a complete map design document (87 tiles, 5 zones, Anger stage of Jean's grief arc).

---

## DevOps Review Skill

**Infrastructure and deployment audit expert.** The `/devops-review` skill performs a comprehensive audit of CI/CD pipelines, dependency health, secrets management, deployment readiness, environment hygiene, and operational risk.

Use when you need to:
- Audit CI/CD pipeline configuration
- Review dependency health and security
- Assess secrets management and configuration
- Evaluate deployment readiness
- Identify operational risks and single points of failure
- Prepare for production deployment

```bash
/devops-review                                     # full audit (all systems)
/devops-review --ci-only                          # CI/CD pipelines only
/devops-review --dependencies-only                # dependency health only
/devops-review --secrets-only                     # secrets and configuration only
/devops-review --prod-only                        # production environment only
/devops-review --quick                            # critical issues only
```

**Output**: Markdown audit report (saved to `tools/devops-audit-{YYYY-MM-DD}.md`) containing:
- Executive summary of overall health and top risks
- CI/CD pipeline audit (grade A-F with findings)
- Dependency health report (CVE count, outdated packages)
- Secrets & configuration assessment
- Deployment readiness evaluation
- Environment hygiene analysis
- Operational risk matrix
- Critical and high-priority remediation steps with effort estimates

---

## Narrative Review Skill

**Expert indie game narrative audit.** The `/narrative-review` skill reviews lore, character consistency, and dialogue quality. It compares story implementation against lore documents, flags contradictions, and suggests fixes.

Use when you need to:
- Audit story coherence and lore consistency
- Review character voice and dialogue quality
- Check thematic alignment
- Verify narrative implementation matches design docs
- Identify plot holes or contradictions

```bash
/narrative-review                                  # full narrative audit
/narrative-review --chapter 1                      # Chapter 1 only
/narrative-review --character Jean                 # Jean Claire dialogue/voice only
/narrative-review --lore-only                      # lore documents only
/narrative-review --dialogue-only                  # dialogue and character voice
/narrative-review --quick                          # character consistency only
/narrative-review --deep                           # full audit with stylistic critique
```

**Output**: Markdown audit report (saved to `.gstack/narrative-reports/narrative-audit-{branch}-{YYYY-MM-DD}.md`) containing:
- Executive summary of narrative health
- Lore coherence audit (grade A-F with contradictions flagged)
- Character consistency analysis (per-character voice profiles and violations)
- Dialogue quality assessment (exposition, subtext, pacing issues)
- Thematic alignment evaluation
- Lore-implementation gaps
- Prioritized high-impact findings with suggested rewrites
- Ship-readiness narrative assessment

---

## Sound Designer Skill

**Expert indie game sound designer.** The `/sound-designer` skill audits the game's **procedural audio synthesis system**, designs new SFX by implementing Song classes, and works with the project's sound creation tools to generate and test audio.

The project uses a **Wave Synthesis Engine** (`tools/audio_engine/`) for all audio: no external AI generation. The skill writes Song class code that uses `generate_tone()`, `generate_tone_sweep()`, `generate_chord()`, `mix_layers()`, and `generate_percussion_pattern()` to create SFX.

Use when you need to:
- Audit existing sound design and identify gaps
- Design SFX for specific locations, events, or narrative moments
- Implement new Song classes using procedural synthesis
- Generate and test audio using the project's tools
- Analyze sonic lore integration (how audio reflects the world and Jean's arc)

```bash
/sound-designer                                    # full audio audit
/sound-designer --design
event: entering the corrupted sacred spring
emotional_goal: awe mixed with reverent dread

/sound-designer --audit
Review SFX coverage and identify weak spots
```

**Output**: Sound design audit reports, Song class implementations (Python code), testing instructions, and integration notes.

**Authority**: The sound designer has **full authority to improve the audio generation tools** (audio_engine, Song system) as needed to meet design goals. If synthesis capabilities are missing, add them.

**Project audio tools**:
- `tools/audio_engine/core.py` — synthesis functions (generate_tone, generate_tone_sweep, generate_chord, mix_layers) — *can be enhanced*
- `tools/songs/` — Song classes: `sfx.py`, `ambient.py`, `adventure.py`, `battle.py`, etc. — *can be templated/refactored*
- `python tools/generate_audio.py` — renders all songs to WAV files
- `python tools/audio_player.py` — interactive testing GUI (tempo, pitch, visualization)
- Output: `frontend/public/assets/sounds/`

**Engine capabilities (as of 2026-03):**
- `generate_tone`: ADSR envelope (attack/decay/sustain_level/release) + vibrato LFO (rate/depth)
- `generate_tone_sweep`: phase-accumulator sweep from `start_freq` → `end_freq` with full waveform support
- `generate_chord`: multi-frequency chord with ADSR envelope; ZeroDivision guards for very short envelopes
- `mix_layers`, `generate_percussion_pattern`: unchanged

**Existing Song classes:**
- `sfx.py` — combat/game SFX: AttackHitSFX, AttackMissSFX, AttackParrySFX, AttackSwipeSFX, EnemyDeathSFX, MoveSFX, LevelUpSFX, QuestCompleteSFX, ItemUseSFX, HealSFX, StatusHitSFX, PlayerDeathSFX
- `ambient.py` — ambient BGM: MineralPoolsSong, DreamSpaceSong
- `adventure.py`, `battle.py`, `dungeon.py` — BGM tracks

Key capabilities:
- Procedural wave synthesis (sine, square, sawtooth, triangle, noise)
- ADSR envelope shaping + vibrato LFO modulation
- Pitch-sweep synthesis (`generate_tone_sweep`) for expressive transients
- Frequency selection and layering strategies
- **Audio engine enhancement** (add new synthesis functions, helper classes, templates)
- Song class architecture and design patterns
- Audio generation and QA testing

---

## Music Designer Skill

**Expert indie game music designer.** The `/music-designer` skill analyzes maps, lore, and story beats to understand BGM needs. Works with AI music generation models with intimate understanding of how to extract exceptional music from each prompt.

Use when you need to:
- Create a music blueprint (thematic map, emotional arcs)
- Design music for specific chapters, locations, or narrative moments
- Generate detailed prompts for AI music generators (Suno, MusicGen, AIVA)
- Understand model capabilities and limitations
- Create music integration strategies and quality criteria

```bash
/music-designer                                    # full music design audit
/music-designer --blueprint
scope: chapter 2
focus: reflect the corruption theme and Jean's growing resolve

/music-designer --generate
location: dark-grotto
moment: discovering the sacred spring corrupted
generator: suno
```

**Output**: Music design blueprints, AI generation requests with settings, integration guides, and sonic palettes.

Key capabilities:
- Thematic composition (motifs for characters, locations, emotional states)
- Narrative pacing and emotional arc design
- AI music generation mastery (Suno, MusicGen, AIVA, etc.)
- Prompt engineering for music (model-specific language, iteration strategies)
- Game audio integration (looping, transitions, adaptive systems)

---

## UI Mockup Skill

**Retro terminal UI mockup designer.** The `/mockup` skill generates self-contained HTML mockup files that match the project's design language, saves them to `docs/development/`, and pushes to the remote branch so the user can view them immediately — without checking out code.

Use when you need to:
- Show what a new component looks like before implementation
- Explore state variations (collapsed/expanded, hover, empty, error)
- Get sign-off on a design before writing React code
- Document a UI design decision for the repo

```bash
/mockup
component: move cooldown card
states: collapsed, expanded
context: below HeroPanel in LeftPanel
issue: #127

/mockup
component: quest tracker panel
states: no quests, active quest, completed
```

**Output**: A single HTML file at `docs/development/<name>-mockup.html`, committed and pushed to the current remote branch. Screenshot shown inline if Playwright is available.

**Branch rule**: The skill always pushes before reporting done. A mockup the user cannot view on the remote is not finished.

Key capabilities:
- Reads `frontend/src/styles/theme.js` for live design tokens (colors, spacing, fonts)
- Reads adjacent components to match padding and border styles exactly
- Shows in-context placement, state variations, and annotated close-ups
- Covers all move category color variants (Attack, Maneuver, Special, Supernatural, Misc)

---

## Acceptance Test Skill

**Developer-focused test infrastructure generator.** The `/acceptance-test` skill generates minimal test setup (maps, scenarios, config, scripts) for rapid feature validation. Integrates with the bug-hunt harness (in-process) and browser testing (gstack /qa), letting you catch bugs fast without manual setup.

Use when you need to:
- Validate a new feature works end-to-end
- Create a reproducible test case for a bug
- Set up fast, automated feature regression tests
- Test combat mechanics, NPC behavior, quest logic, inventory systems, etc.

```bash
/acceptance-test
feature: "cooldown drain on passive moves"

/acceptance-test
feature: "quest completion triggers NPC dialogue"
worktree: true

/acceptance-test
feature: "combat status effect stacking"
worktree: false
```

**Output**: A complete test directory at `tests/acceptance/<feature-slug>/` containing:
1. **config.ini** — Game configuration (player stats, starting map, debug flags)
2. **run.sh** — Test runner script (in-process or browser modes)
3. **test_plan.json** — Browser test plan for gstack /qa
4. **acceptance-test-<slug>.json** — Minimal test map (2 tiles)
5. **acceptance_test_<slug>.py** — Scenario class (extends harness.scenarios.Scenario)
6. **README.md** — Usage guide and customization instructions

### Running the Test

**In-process (fast, no servers needed):**
```bash
cd tests/acceptance/<feature-slug>
./run.sh
```
Output: Console report with any bugs found. Uses the existing bug-hunt harness.

**Browser-based (full UI testing):**
```bash
cd tests/acceptance/<feature-slug>
./run.sh --browser
```
Starts API + frontend servers, then runs via gstack /qa. Catches JS errors, rendering bugs, console noise.

**Manual dev testing:**
Edit `config.ini` to customize player stats, starting map, debug flags. Then:
```bash
CONFIG_FILE=tests/acceptance/<feature-slug>/config.ini python tools/run_api.py
```

### Customization

**Edit the scenario class** to add feature-specific assertions:
- `tools/harness/scenarios/acceptance_test_<slug>.py`
- The `run(client)` method is where you add test logic
- Use `self._bug(...)` to flag issues; return `List[BugReport]`

**Edit the config file** to adjust:
- Player starting stats (hp, strength, finesse, speed, etc.)
- Debug logging (debug_mode, log_combat_moves, etc.)
- NPC AI difficulty, arena size, starting positions

**Edit the test map** (if needed):
- `src/resources/maps/acceptance-test-<slug>.json`
- Default: 2-tile arena (staging area + test zone)
- Add NPCs, items, objects as needed for your feature

### Integration with bug-hunt harness

Once your scenario is tested and working, register it in:
**tools/harness/scenarios/__init__.py**

Add:
```python
from .acceptance_test_<slug> import SomeFeatureNameScenario

_ALL_SCENARIOS = [
    ...
    SomeFeatureNameScenario(),
]
```

Then it becomes part of the standard harness:
```bash
python tools/bug_hunt.py --scenario <slug>
python tools/bug_hunt.py --headless --output bugs.json
```

### Example Workflow

1. **Generate test infrastructure:**
   ```bash
   /acceptance-test
   feature: "interrupt move during cast"
   ```

2. **Run in-process to catch basic bugs:**
   ```bash
   cd tests/acceptance/interrupt-move-during-cast
   ./run.sh
   ```

3. **Fix config.ini and scenario logic:**
   - Adjust player stats, NPC placement
   - Add assertions for interrupt mechanics
   - Test locally with the runner script

4. **Run browser tests to catch UI bugs:**
   ```bash
   ./run.sh --browser
   ```

5. **Register in harness for regression testing:**
   - Add to `tools/harness/scenarios/__init__.py`
   - Now part of `python tools/bug_hunt.py`

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
- **Tests** — remind to run `python -m pytest -q` or `cd frontend && npm test` if the changes touch testable code
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

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. The
skill has multi-step workflows, checklists, and quality gates that produce better
results than an ad-hoc answer. When in doubt, invoke the skill. A false positive is
cheaper than a false negative.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke /office-hours
- Strategy, scope, "think bigger", "what should we build" → invoke /plan-ceo-review
- Architecture, "does this design make sense" → invoke /plan-eng-review
- Design system, brand, "how should this look" → invoke /design-consultation
- Design review of a plan → invoke /plan-design-review
- Developer experience of a plan → invoke /plan-devex-review
- "Review everything", full review pipeline → invoke /autoplan
- Bugs, errors, "why is this broken", "wtf", "this doesn't work" → invoke /investigate
- Test the site, find bugs, "does this work" → invoke /qa (or /qa-only for report only)
- Code review, check the diff, "look at my changes" → invoke /review
- Visual polish, design audit, "this looks off" → invoke /design-review
- Developer experience audit, try onboarding → invoke /devex-review
- Ship, deploy, create a PR, "send it" → invoke /ship
- Merge + deploy + verify → invoke /land-and-deploy
- Configure deployment → invoke /setup-deploy
- Post-deploy monitoring → invoke /canary
- Update docs after shipping → invoke /document-release
- Weekly retro, "how'd we do" → invoke /retro
- Second opinion, codex review → invoke /codex
- Safety mode, careful mode, lock it down → invoke /careful or /guard
- Restrict edits to a directory → invoke /freeze or /unfreeze
- Upgrade gstack → invoke /gstack-upgrade
- Save progress, "save my work" → invoke /context-save
- Resume, restore, "where was I" → invoke /context-restore
- Security audit, OWASP, "is this secure" → invoke /cso
- Make a PDF, document, publication → invoke /make-pdf
- Launch real browser for QA → invoke /open-gstack-browser
- Import cookies for authenticated testing → invoke /setup-browser-cookies
- Performance regression, page speed, benchmarks → invoke /benchmark
- Review what gstack has learned → invoke /learn
- Tune question sensitivity → invoke /plan-tune
- Code quality dashboard → invoke /health
