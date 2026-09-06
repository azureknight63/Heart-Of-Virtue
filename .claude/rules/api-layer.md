---
paths:
  - "src/api/**"
  - "src/env_bootstrap.py"
  - "wsgi.py"
  - "tools/run_api.py"
---

# API layer rules (`src/api/`)

The engine is the source of truth; this layer adapts. Root CLAUDE.md carries the gating one-liners — this file carries the detail behind them.

## GameService / SessionManager
- `GameService.__init__` is `pass`. There is no `self.universe`; the universe lives on `player.universe`. Use the static helpers `self._story(player)` (→ `player.universe.story` or `{}`) and `self._game_tick(player)` (→ `player.universe.game_tick` or `0`).
- Routes must not reach into player internals. No `getattr(player, "attribute", default)` in routes — add a `GameService` method. Attribute traps: `player.attack` **does not exist** — it was a terminal verb and went out with `Player.take`/`Player.print_inventory` in the teardown, so it is not a stat *or* a method. Nor do `player.health` (it's `player.hp`), `player.stamina`, `player.defense`, `player.accuracy` or `player.evasion`. `GET /inventory/stats` once regressed exactly this way (bare `getattr` fallbacks rendered all-default stats) — it must call `game_service.get_player_stats()`.
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

## Wire ids — one opaque handle per object

- **Every wire id is an opaque handle, and there is exactly ONE per object.**
  `src/combatant.py::wire_handle(entity)` lazily mints a `uuid4().hex` into
  `entity.__dict__` via `setdefault` (atomic under the GIL, so two threads cannot ship
  two ids for one object), persists it through pickling, and falls back to a
  `WeakKeyDictionary` for objects that cannot hold an attribute. `combatant_handle` is
  an **alias**, not a parallel scheme (#511 minted combatants; #518 widened it to room
  NPCs, world objects, floor and inventory items, container contents, merchants, shop
  stock and events). The `Slime` in `tile.npcs_here` is the same instance as the one in
  `combat_list`, so the room id and the combat id name it identically — the combat
  payload just prefixes the same handle (`enemy_<handle>` via
  `CombatantSerializer.stream_id`).
- **Never mint a wire id from `str(id(x))`.** Heap addresses leak process layout and,
  worse, CPython **recycles** them, so a client-held id for a freed entity resolves to
  whatever was allocated at that address (`tests/test_entity_wire_handles.py` forces
  exactly that reuse). Resolve client ids through `src.combatant.find_by_handle`, never
  by comparing `id()`.
- **The trap when changing this**: the mint and the lookup live in *different files*,
  and moving only one half does not raise — `interact_with_target` simply answers
  "Target not found." for everything in the room.
  `tests/test_wire_field_contract.py::TestWireIdRoundTrip` feeds each real serializer's
  id back to its real resolver so that half-move fails loudly.
- **The buyback ledger is the only PERSISTED wire id.**
  `merchant._buyback_ledger[*]["item_id"]` lives on the merchant and pickles into
  saves; every other id is minted fresh per response, so a stale one at worst costs one
  failed lookup the client re-fetches past. `ShopSerializer.flush_stale_buyback` is the
  chokepoint every ledger read passes through, and it calls `repoint_stale_buyback_ids`
  to re-point an entry whose `item_id` no longer names a stocked item at the same-named
  stock item. That migrates pre-#518 saves and covers the identical live case of
  `stack_inv_items` merging the item away between the sale and the next request.
  Unmigrated, the symptom is not a crash but a **double listing**: the stock
  subtraction in `serialize_state` misses and the just-sold item is offered twice in
  the BUY tab, once at full price and once at the buyback price.

## Auth — the session cookie

- **The session credential is an `HttpOnly` cookie (`hov_session`), not
  `localStorage.authToken`** (#493). `session_token()` in `src/api/middleware/auth.py`
  is the single place that decides which credential a request carries — cookie first,
  `Authorization: Bearer <session_id>` second. The Bearer path is deliberate, not
  leftover: the bug-hunt harness, API-only Inquisitor mode and several hundred route
  tests hold a session id from `/api/test/session` and have no cookie jar. The cookie
  wins when both are present, so a stale header from a previous sign-in can never
  override the cookie the browser was just issued. Don't reintroduce a client-side
  token store — `AUTH_TOKEN_KEY` survives in `frontend/src/utils/session.js` only so a
  browser carrying a pre-#493 value gets it cleared on the next logout or 401.
- **`src/api/sockets.py` gates its payload fallback on `TESTING`**, unlike the HTTP
  Bearer path. Nothing outside the test suite needs it: the browser has sent `{}` since
  #493 and nothing in `tools/` speaks Socket.IO. Ungated it was an unauthenticated
  join — a caller with no cookie could name any session and receive that whole battle
  stream.
- **`Path=/` is load-bearing.** The Socket.IO handshake is served from the app root
  (`/socket.io/...`), outside the SPA's base path, and authenticates by reading this
  cookie. Scope the cookie to the base path and the browser simply does not send it on
  the handshake: the socket still connects, `join_combat` is refused, and nothing on
  the client listens for that `error` event — so the combat beat stream goes to nobody
  with no visible failure anywhere.
- **A route that issues the cookie needs `make_response(...)` + `set_session_cookie`**
  (`src/api/session_cookie.py`), and any clear must repeat the same
  path/secure/samesite: a browser matches a deletion against an existing cookie by name
  *and* attributes, so a bare `delete_cookie(name)` leaves it in place and logout
  returns 200 while the player stays signed in. Use `clear_session_cookie`.
- **Cookie-config traps.** Flask predefines `SESSION_COOKIE_SAMESITE` as `None` in
  *every* app config, so `config.get("SESSION_COOKIE_SAMESITE", "Lax")` returns `None`
  and the default is never reached — write `config.get(...) or "Lax"`. And
  `PERMANENT_SESSION_LIFETIME` may be an `int` of seconds or a `timedelta` depending on
  who wrote it; assuming the `timedelta` raises `AttributeError` on *every* response, a
  total outage caused by a config style choice.
- **`logout` is deliberately not `@require_auth`.** That decorator 401s before the body
  runs whenever the cookie names an expired or unknown session — so the cookie was
  never cleared, and since #493 the page cannot clear an `HttpOnly` cookie itself,
  leaving the browser pinned to a dead credential with no way out. Logout always clears
  and returns 200; only a genuine server fault returns an error. The knowing trade-off
  is that an unauthenticated cross-site POST can force a logout — a nuisance, not a
  disclosure, and `SameSite=Lax` withholds the cookie on cross-site POST anyway.

## Content-Security-Policy

- **New external origins go in `src/resources/csp-policy.json`, never into one
  emitter.** Both `src/api/security_headers.py` (`build_csp`) and
  `frontend/vite.config.js` (`cspHeaders`) read that file, and
  `tests/test_security_headers.py` fails if the Vite config ever inlines a directive
  copy. Dev-server-only relaxations belong in `dev_additions`, which the production
  policy never merges.
- **Two policies, because there are two kinds of response.** The shared JSON is the
  *document* policy and ships report-only during the rollout. A response that does not
  declare itself a document via `serves_html_document` gets `_API_CSP`
  (`default-src 'none'; … sandbox`), **enforced** — a JSON body has nothing to break,
  and report-only on `/api/*` would be a header that blocks nothing.
  `X-Frame-Options: DENY` travels with that policy and only with it, so it cannot
  contradict the document policy's `frame-ancestors 'self'`.
- **The production SPA *document* receives no CSP from this repo.** Vite's
  `server`/`preview` headers cover the document in development and QA; production
  static hosting is not configured from here — the document's policy is a
  hand-maintained nginx snippet in `docs/development/csp-rollout.md`. Editing the JSON
  does not update production: the snippet has to be regenerated and redeployed, and
  nothing enforces this today.
- **`CSP_REPORT_ONLY` as an environment variable is inert.** `_flag` reads
  `app.config.get(key, os.environ.get(key))`, and the base `Config` defines
  `CSP_ENABLED`/`CSP_REPORT_ONLY`/`CSP_REPORT_URI`/`CSP_DEV_RELAXATIONS`, so every
  subclass carries the key and config always wins. Flipping report-only to enforcing is
  an edit in `src/api/config.py`, not a deploy-time env var.

## Routes
- `/api/debug/*` (`routes/debug.py`, `debug_bp`) registers only when `app.config["TESTING"]`. It exposes the Adjutant's parametrized ops (`set_hp`, `set_level`, `set_attributes`, `set_heat`, `restore`, `learn_all_skills`, `list_skills`, `player_state`, `arena_rosters`, `add_combatant`, `remove_combatant`, `clear_room`, `set_combatant_stats`). Never register a debug/test route outside that gate.
- `/api/test/session` (TESTING only) creates a session with no `db_user_id`. There is **no guest mode** in production — every real session has a `db_user_id`; the "no db_user_id" 403 branch in the saves routes is only reachable through this bypass.
- `async def` routes (auth, saves) need `asgiref` or they 500 under a real Werkzeug server while passing with the in-process test client. It's in `requirements-api.txt`.
- `feedback.py`'s `_create_github_issue()` files **real** GitHub issues whenever `GITHUB_TOKEN` is set — there is no TESTING guard by design. Any harness or test that exercises the feedback route must neutralize the env var (`os.environ["GITHUB_TOKEN"] = ""`, **not** `.pop()` — `load_project_env()` runs `load_dotenv(override=False)`, which refills a key that is *absent* and leaves an assigned blank one alone).
- Saves: cloud autosave is one `is_autosave=TRUE` row per user (UPSERT) written every `AUTOSAVE_TICK_THRESHOLD` (3) movement/combat transitions; there is no local autosave. `list_saves` emits `timestamp_ms` (epoch, computed *before* `astimezone(user_tz)`) — the client sorts on it, never on the display string. Failed cloud saves surface to the player via toast.
- Shop pricing lives on the `Merchant` (`buy_modifier`, `sell_modifier`, `shop_name`) and is read by `GameService.shop_buy/sell` and `ShopSerializer` — don't re-derive prices in a route.
- Blueprint URL prefixes have been misrouted before (reputation, npc, quests, quest-chains). When adding a blueprint, add a route test that hits the full prefixed path.
- Env: `ENCRYPTION_KEY` is required in production (fail-closed at import). `db.py` does **not** own the `.env` load — `src/env_bootstrap.load_project_env()` does; `db.py` is one of its callers, resolving the path from `__file__` so a process started outside the repo root still finds it. Five modules call it at their own import time: `src/api/rate_limiter.py`, `src/api/db.py`, `ai/llm_client.py`, `wsgi.py`, `tools/run_api.py`. In the API the load happens during `create_app()`'s blueprint imports, and `rate_limiter.py` calls it in its module body precisely so import order can't matter — every limiter is built by `limiter_from_env()` before `create_app()` returns. Consequences worth knowing: anything importing the app (pytest included) picks up the real `.env`, and **importing `ai.llm_client` alone does too**, with no Flask app anywhere. `load_dotenv(override=False)` (`env_bootstrap.py`) fills only *absent* keys, so neutralize a live secret by assigning `""`, never by `.pop()`.
