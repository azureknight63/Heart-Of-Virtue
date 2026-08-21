---
paths:
  - "src/api/**"
---

# API layer rules (`src/api/`)

The engine is the source of truth; this layer adapts. Root CLAUDE.md carries the gating one-liners — this file carries the detail behind them.

## GameService / SessionManager
- `GameService.__init__` is `pass`. There is no `self.universe`; the universe lives on `player.universe`. Use the static helpers `self._story(player)` (→ `player.universe.story` or `{}`) and `self._game_tick(player)` (→ `player.universe.game_tick` or `0`).
- Routes must not reach into player internals. No `getattr(player, "attribute", default)` in routes — add a `GameService` method. Attribute traps: `player.attack` is a combat action method, not a stat; `player.health` doesn't exist (it's `player.hp`); `player.stamina`, `player.defense`, `player.accuracy`, `player.evasion` are absent. `GET /inventory/stats` once regressed exactly this way (bare `getattr` fallbacks rendered all-default stats) — it must call `game_service.get_player_stats()`.
- `player.reputation` doesn't exist on a fresh player. Writers do `player.reputation = {}` first; readers use `getattr(player, 'reputation', {})`.
- **Cooldown timing trap**: cooldowns drain only during active combat beats. A drain on rest, world movement, or save/load silently corrupts move availability — guard every drain call with an active-combat check.
- `GameService.move_player` calls `player.universe.game_tick_events()` on every move (mirrors the old terminal loop) — required for map-entry spawners (`NPCSpawnerEvent`) to fire.
- `trigger_tile_events` / `trigger_combat_events` must set `event.tile` from the `tile` they were given, never from `player.current_room` (often `None` early in a session → `AttributeError: 'NoneType' object has no attribute 'events_here'` inside `NPCSpawnerEvent.check_conditions()`). Exceptions inside tile events are swallowed — when an event silently doesn't fire, read the logs before assuming its conditions failed.
- Event capture runs on `capture_narration()` (context-local buffer). `_build_event_patches` patches only `await_input`/`animate`/`time.sleep`; there is no `input()` mocking net any more and nothing in the engine may call `input()`.
- Direct calls to `game_service` methods mutate `session.data` in memory; API calls re-fetch the session from storage. After mutating directly (tests, tools), call `session_manager.save_session()` or the next request won't see it.
- `process_event_input` mints a **new** `event_id` when an event transitions to another stage that still `needs_input`, and drops the old one from `pending_events`. Clients and tests must use the id from the latest response.

## Combat adapter (`combat_adapter.py`)
- `ApiCombatAdapter` drives moves via `cast()`/`advance()`; player selections arrive as structured commands (`select_number` / `select_direction` / `select_target`) that set `duration` / `distance` / `target_direction` / `target` on the move *before* its stage runs. Never prompt.
- `combat_id` identifies a fight, not a call. It is minted in `initialize_combat`'s `not reinit` branch alongside the beat/log reset, so it survives wave transitions and reinforcement spawns and changes only for a genuinely new fight. `get_combat_state` publishes it inside `battle_state`. Don't mint one per call — the client uses it to tell "new fight" from "same fight, next beat".
- Put new per-poll combat fields **inside `battle_state`**: the frontend's `transformCombatData` spreads `battle_state` but whitelists top-level keys, so a new top-level field never reaches the client (two shipped bugs came from this).
- The adapter reads the narration buffer through a live listener (`_capture_output`), not stdout scraping. Combat starts are always `combat_start` (no terminal fallback).
- Combat initialization is deferred while the player has unspent attribute points (level-up dialog); waiting enemies are stashed on the player and the next `GET /combat/status` resumes. Keep that invariant when touching combat init. After victory/defeat, `awaiting_input`, `current_stage`, and `pending_move_index` must be reset — all three went stale once.
- Socket streaming: backend flag `COMBAT_SOCKET_STREAMING`, frontend `VITE_COMBAT_SOCKET`; events `join_combat` → `joined_combat`, `combat:suggestions_ready`. Werkzeug's reloader can drop env vars — verify flags with the reloader off.

## Serializers — the contract
A serializer **never raises on a degraded object** (missing/None/wrong-typed attributes, `_legacy_placeholder` shapes) and its output is always JSON-serializable. `tools/serializer_fuzzer.py` + `tests/test_serializer_fuzz.py` enforce it — add new serializer entry points there. The frontend reads wire field *names*: any field the client will read also goes into `tests/test_wire_field_contract.py`.

## Routes
- `/api/debug/*` (`routes/debug.py`, `debug_bp`) registers only when `app.config["TESTING"]`. It exposes the Adjutant's parametrized ops (`set_hp`, `set_level`, `set_attributes`, `set_heat`, `restore`, `learn_all_skills`, `list_skills`, `player_state`, `arena_rosters`, `add_combatant`, `remove_combatant`, `clear_room`, `set_combatant_stats`). Never register a debug/test route outside that gate.
- `/api/test/session` (TESTING only) creates a session with no `db_user_id`. There is **no guest mode** in production — every real session has a `db_user_id`; the "no db_user_id" 403 branch in the saves routes is only reachable through this bypass.
- `async def` routes (auth, saves) need `asgiref` or they 500 under a real Werkzeug server while passing with the in-process test client. It's in `requirements-api.txt`.
- `feedback.py`'s `_create_github_issue()` files **real** GitHub issues whenever `GITHUB_TOKEN` is set — there is no TESTING guard by design. Any harness or test that exercises the feedback route must neutralize the env var (`os.environ["GITHUB_TOKEN"] = ""`, not `.pop()` — `load_dotenv(override=False)` in `db.py` refills missing keys).
- Saves: cloud autosave is one `is_autosave=TRUE` row per user (UPSERT) written every `AUTOSAVE_TICK_THRESHOLD` (3) movement/combat transitions; there is no local autosave. `list_saves` emits `timestamp_ms` (epoch, computed *before* `astimezone(user_tz)`) — the client sorts on it, never on the display string. Failed cloud saves surface to the player via toast.
- Shop pricing lives on the `Merchant` (`buy_modifier`, `sell_modifier`, `shop_name`) and is read by `GameService.shop_buy/sell` and `ShopSerializer` — don't re-derive prices in a route.
- Blueprint URL prefixes have been misrouted before (reputation, npc, quests, quest-chains). When adding a blueprint, add a route test that hits the full prefixed path.
- Env: `ENCRYPTION_KEY` is required in production (fail-closed at import). `.env` is loaded by `src/api/db.py` at `create_app()` import time, so anything importing the app — including pytest — picks up the real `.env`.
